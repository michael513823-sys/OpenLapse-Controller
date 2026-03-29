import customtkinter as ctk
import cv2
from PIL import Image, ImageDraw, ImageFont,ImageTk
import io
import threading
import requests
import time
import re
from math import ceil
from typing import List, Tuple, Optional
import numpy as np


# HTTP传输画面
class HTTP_MJPEGViewer(ctk.CTkFrame):
    def __init__(self, parent, stream_url, width=640, height=480, fps=60):
        super().__init__(parent)
        self.stream_url = stream_url
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False

        # 显示区
        self.image_label = ctk.CTkLabel(self, text="")
        self.image_label.pack(expand=True, fill="both")

        self.thread = None
        self.session = None
        self.last_frame_time = 0

        # 初始状态显示
        self._show_placeholder("NOT STREAMING")

    # --------------------------------------------------
    #                 控制函数
    # --------------------------------------------------
    def start(self):
        if self.running:
            print("[WARN] Stream already running.")
            return
        self.running = True
        self.thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.thread.start()
        print("[INFO] MJPEG stream started.")

    def stop(self):
        """停止拉流并显示提示图"""
        if not self.running:
            self._show_placeholder("NOT STREAMING")
            return
        self.running = False
        if self.session:
            self.session.close()
        self._show_placeholder("NOT STREAMING")
        print("[INFO] MJPEG stream stopped.")

    # --------------------------------------------------
    #                流线程循环
    # --------------------------------------------------
    def _stream_loop(self):
        try:
            self.session = requests.Session()
            response = self.session.get(self.stream_url, stream=True, timeout=5)
            bytes_buffer = b""

            for chunk in response.iter_content(chunk_size=1024):
                if not self.running:
                    break
                bytes_buffer += chunk
                a = bytes_buffer.find(b'\xff\xd8')  # JPEG头
                b = bytes_buffer.find(b'\xff\xd9')  # JPEG尾
                if a != -1 and b != -1 and b > a:
                    jpg = bytes_buffer[a:b + 2]
                    bytes_buffer = bytes_buffer[b + 2:]

                    # 解码并显示
                    image = Image.open(io.BytesIO(jpg))
                    image = image.resize((self.width, self.height))
                    ctk_img = ctk.CTkImage(light_image=image, size=(self.width, self.height))
                    self.image_label.configure(image=ctk_img)
                    self.image_label.image = ctk_img

                    # 控制帧率
                    now = time.time()
                    elapsed = now - self.last_frame_time
                    if elapsed < 1 / self.fps:
                        time.sleep(1 / self.fps - elapsed)
                    self.last_frame_time = now

        except Exception as e:
            print(f"[ERROR] Stream error: {e}")
            self._show_placeholder("STREAM ERROR")
        finally:
            self.stop()

    # 捕获当前帧
    def capture_frame(self, save_path):
        if not self.image_label.image:
            print("[WARN] No frame to capture.")
            return
        self.image_label.image.light_image.save(save_path)
        print(f"[INFO] Frame captured to {save_path}")

    # --------------------------------------------------
    #              显示占位图像（提示文字）
    # --------------------------------------------------
    def _show_placeholder(self, text="NOT STREAMING"):
        """绘制灰底文字提示图"""
        img = Image.new("RGB", (self.width, self.height), (200, 200, 200))
        draw = ImageDraw.Draw(img)

        # 字体
        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except:
            font = ImageFont.load_default()

        # 计算文字尺寸（替代 textsize）
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

        # 居中绘制文字
        draw.text(
            ((self.width - text_w) / 2, (self.height - text_h) / 2),
            text,
            fill=(80, 80, 80),
            font=font,
        )

        ctk_img = ctk.CTkImage(light_image=img, size=(self.width, self.height))
        self.image_label.configure(image=ctk_img)
        self.image_label.image = ctk_img

# USB传输画面
class USBVideo():
    def __init__(self, device=0, 
                 pre_width=400, pre_height=225, fps=30, 
                 cap_width=3840, cap_height=2160,
                 use_mjpeg=True):
        """
        device: 摄像头索引或设备路径。0/1/2... 或 '/dev/video0'
        width, height: 目标显示尺寸
        fps: 目标显示帧率（显示节流；摄像头实际帧率以硬件为准）
        use_mjpeg: 尝试将摄像头 FOURCC 设为 MJPG，降低 USB 带宽和延迟
        """
        self.device = device
        self.pre_width = pre_width
        self.pre_height = pre_height
        self.fps = fps
        self.cap_width = cap_width
        self.cap_height = cap_height
        self.use_mjpeg = use_mjpeg

        self.running = None

        self.cap = None
        self.last_frame_time = 0.0
        self.last_pil = None   # 用于 capture_frame()
        self.pre_img = None     # 用于预览

        # 自动对焦相关
        self.fm_list = []
        self.pos_list = []

        # 读写锁
        self.lock = threading.Lock()

        # 初始状态
        self._show_placeholder("NOT STREAMING")

    # ---------------------- 控制 ----------------------
    def start(self):
        if self.running:
            print("[WARN] Camera already running.")
            return
        
        self.running = True

        # 打开摄像头
        backend = cv2.CAP_ANY
        self.cap = cv2.VideoCapture(self.device, backend)

        if not self.cap.isOpened():
            print(f"[ERROR] Cannot open camera: {self.device}")
            self._show_placeholder("OPEN CAMERA FAILED")
            return

        # 期望分辨率与帧率
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.cap_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cap_height)
        if self.fps:
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        # 设置 MJPG
        if self.use_mjpeg:
            try:
                fourcc = cv2.VideoWriter.fourcc(*"MJPG")
                self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
            except Exception:
                pass

        # 某些 USB 摄像头会缓存多帧，拉几帧清空缓冲
        for _ in range(5):
            self.cap.read()

        print("[INFO] USB camera started.")

    def stop(self):
        if not self.running:
            self._show_placeholder("NOT STREAMING")
            return

        self.running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        self._show_placeholder("NOT STREAMING")
        print("[INFO] USB camera stopped.")

    # ---------------------- 采集线程 ----------------------
    def capture_loop(self):
        if self.cap:
            try:
                ok, frame = self.cap.read()
                if not ok:
                    self._show_placeholder("Read frame failed.")

                # BGR -> RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # # 转 PIL 并按显示尺寸缩放
                # self.pre_img = Image.fromarray(frame_rgb).resize((self.pre_width, self.pre_height))
                # # 原始尺寸
                # self.last_pil = Image.fromarray(frame_rgb)

                pil_pre = Image.fromarray(frame_rgb).resize((self.pre_width, self.pre_height))
                pil_full = Image.fromarray(frame_rgb)

                # 加锁，更新最新帧
                with self.lock:
                    self.pre_img = pil_pre
                    self.last_pil = pil_full

            except Exception as e:
                print(f"[ERROR] Capture loop error: {e}")
                self._show_placeholder("CAPTURE ERROR")
            finally:
                # self.stop()
                pass

    # ---------------------- 工具 ----------------------
    def capture_frame(self, save_path):
        """保存最近一帧到文件"""
        with self.lock:
            if self.last_pil is None:
                print("[WARN] No frame to capture.")
                return
            try:
                self.last_pil.save(save_path)
                print(f"[INFO] Frame captured to {save_path}")
            except Exception as e:
                print(f"[ERROR] Save failed: {e}")

    # 计算清晰度
    def focus_measure_laplacian(self, roi_wh=None):
        """
        使用最近一帧 self.last_pil 计算清晰度指标（Laplacian 方差）
        roi: 可选 (w, h)，在 RGB 图像上的区域，只对中心区域w,h范围计算清晰度
        返回: float 或 None（如果当前没有帧）
        """
        # 先把最新帧取出来，避免长时间占用锁
        with self.lock:
            if self.last_pil is None:
                return None
            pil_img = self.last_pil.copy()

        # PIL(RGB) -> numpy 数组(RGB)
        frame = np.array(pil_img)

        # ROI 裁剪（如果给了）
        if roi_wh is not None:
            rw, rh = roi_wh

            H, W = frame.shape[:2]  # 高、宽

            cx, cy = W // 2, H // 2   # 中心点 (x,y)

            # ROI 左上角
            x1 = max(cx - rw // 2, 0)
            y1 = max(cy - rh // 2, 0)

            # ROI 右下角
            x2 = min(cx + rw // 2, W)
            y2 = min(cy + rh // 2, H)

            frame = frame[y1:y2, x1:x2]   # 注意：先 y 后 x

        # RGB -> 灰度
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        # Laplacian
        lap = cv2.Laplacian(gray, cv2.CV_64F)

        # 用方差作为清晰度指标
        fm = lap.var()
        return float(fm)
    
    def update_fm(self, pos, fm):
        # print(f"[update_fm] pos={pos}, fm={fm}, before len={len(self.fm_list)}")
        if (pos is not None) and (fm is not None):
            self.pos_list.append(pos)
            self.fm_list.append(fm)
            # print(f"[update_fm] appended. after len={len(self.fm_list)}")
        else:
            print("[update_fm] skipped append because pos or fm is None")

    def calcu_best_pos(self):
        # 调试：看看当前列表里到底有什么
        # print(f"[calcu_best_pos] len(pos_list)={len(self.pos_list)}, len(fm_list)={len(self.fm_list)}")
        # print(f"[calcu_best_pos] fm_list={self.fm_list}")
        
        if not self.fm_list:
            print("[calcu_best_pos] fm_list is empty, return None")
            return None

        # 找到最大 fm 对应的索引
        best_index = max(range(len(self.fm_list)), key=lambda i: self.fm_list[i])
        best_pos = self.pos_list[best_index]
        best_fm = self.fm_list[best_index]
        # print(f"[calcu_best_pos] best_index={best_index}, best_pos={best_pos}, best_fm={best_fm}")
        return best_pos
            
    def reset_fm_list(self):
        # print("[reset_fm_list] clear fm_list and pos_list")
        self.fm_list = []
        self.pos_list = []


    def change_camera(self, device):
        """切换摄像头（会自动重启）"""
        was_running = self.running
        self.stop()
        self.device = device
        if was_running:
            self.start()

    def get_img(self,master=None):
        _imgtk = ImageTk.PhotoImage(self.pre_img,master=master)
        return _imgtk

    # ---------------------- 占位图 ----------------------
    def _show_placeholder(self, text="NOT STREAMING"):
        img = Image.new("RGB", (self.pre_width, self.pre_height), (200, 200, 200))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((self.pre_width - text_w) / 2, (self.pre_height - text_h) / 2),
            text, fill=(80, 80, 80), font=font
        )

        self.pre_img =  img


# 定时拍照
class TimedCapture:
    ROWS = ['A','B','C','D','E','F','G','H']
    COLS = list(range(1, 13))  # 1..12

    def __init__(self,
                 interval_s: float,
                 duration_h: float,
                 wells: List[str],
                 *,
                 first_round_immediate: bool = True):
        """
        定时拍照（严格顺序 + 每孔独立间隔 + 启动可行性预检）

        :param interval_s: 每个孔两次拍照之间的最小间隔（分钟）
        :param duration_h:   总时长（小时）
        :param wells:        要按顺序循环的孔位名列表（最多96；如 ["A1","A2",...,"H12"]）
        :param consider_travel: 是否将相邻孔的移动时间计入触发判断（默认 True）
        :param first_round_immediate: 第一圈是否可立即拍（True=立即；False=首圈也需等待一个间隔）
        """
        if not wells:
            raise ValueError("wells 列表不能为空。")

        self.well_num = len(wells)
        self.interval_sec = float(interval_s) * 1
        self.duration_sec = float(duration_h) * 3600.0
        self.path = [self._norm_well(w) for w in wells]
        self.first_round_immediate = bool(first_round_immediate)

        # 运行态
        self.start_time: Optional[float] = None
        self.running: bool = False

        # 顺序指针与位置
        self.idx: int = 0                         # 当前要检查/触发的孔索引
        self.current_well: Optional[str] = None   # 上一次“实际拍照”的孔
        self.last_shot_time: Optional[float] = None

        # 每个孔的“下一次应拍时间”
        self.next_due = {w: None for w in self.path}

        # 启动前的可行性预检需要的数据
        self.loop_time_sec, self.legs = self._compute_loop_time_and_legs(self.path)

    # ========== 公共方法 ==========

    def start(self):
        """
        启动任务并进行可行性预检：
        - 计算整圈耗时（含回到起点）。若 interval < 整圈耗时，则任意孔都无法更快地再次被访问 → 直接报错。
        - 初始化 next_due / 指针 / 时间戳。
        """
        need_sec = int(ceil(self.loop_time_sec)*1.5)
        FOCUS_TIME_MIN = 60
        focus_time = self.well_num * FOCUS_TIME_MIN
        if self.interval_sec + focus_time < need_sec:
            worst = sorted(self.legs, key=lambda x: x[2], reverse=True)[:3]
            hint = "\n".join([f"  {a} → {b}: {int(d)} 秒" for a, b, d in worst])
            raise ValueError(
                "当前路线无法满足每孔的最小间隔要求：\n"
                f"- 设置的间隔：{int(self.interval_sec)} 秒（≈ {self.interval_sec/60:.2f} 分钟）\n"
                f"- 该路线每孔最小可实现间隔（整圈耗时）：{need_sec} 秒（≈ {need_sec/60:.2f} 分钟）\n"
                f"请将 interval ≥ {need_sec + focus_time} 秒，或减少孔位/优化路线。\n"
                f"路线中最长的几段为：\n{hint}"
            )

        now = time.time()
        self.start_time = now
        self.running = True
        self.idx = 0
        self.current_well = self.path[0]   # 起点即第一个孔
        self.last_shot_time = now          # 视为“刚拍完”，便于后续计算

        # 首圈是否立即可拍
        base_due = now if self.first_round_immediate else now + self.interval_sec
        for w in self.path:
            self.next_due[w] = base_due


    def stop(self):
        self.running = False

    def update(self) -> bool:
        """
        在主循环中调用：
        - 只检查当前指针 self.idx 指向的孔；
        - 触发条件：now >= max(next_due[target], last_shot_time + travel_time)；
        - 不扫表，不乱序。
        """
        if not self.running or self.start_time is None:
            return False

        now = time.time()
        if (now - self.start_time) > self.duration_sec:
            self.running = False
            return False

        if not self.path:
            return False

        target = self.path[self.idx]
        due = self.next_due.get(target, now) or now


        last = self.last_shot_time if self.last_shot_time is not None else self.start_time
        ready_at = max(due, last)

        return now >= ready_at

    def get_well(self) -> Optional[str]:
        """
        在 update() 返回 True 时调用：
        - 返回要拍的孔名；
        - 将该孔 next_due 往后推一个间隔；
        - 记录 last_shot_time / current_well；
        - 指针按顺序 +1（循环）。
        """
        if not self.running or not self.path:
            return None

        # 假定外部刚刚确保 update() 为 True
        now = time.time()
        well = self.path[self.idx]

        # 下次该孔可拍时间 = （已到的 due 与 now 取较晚者）+ interval
        curr_due = self.next_due.get(well, now) or now
        self.next_due[well] = max(curr_due, now) + self.interval_sec

        # 记录“本次拍照”
        self.last_shot_time = now
        self.current_well = well

        # 指针推进（严格顺序）
        self.idx = (self.idx + 1) % len(self.path)

        return well

    def progress(self) -> float:
        """按时间的进度百分比（0~100）"""
        if not self.start_time:
            return 0.0
        now = time.time()
        return min(max((now - self.start_time) / self.duration_sec * 100.0, 0.0), 100.0)

    # ========== 内部工具 ==========

    def _norm_well(self, w: str) -> str:
        w = w.strip().upper()
        m = re.fullmatch(r'([A-H])(1[0-2]|[1-9])', w)
        if not m:
            raise ValueError(f"非法孔位: {w}")
        return f"{m.group(1)}{int(m.group(2))}"

    def _rc(self, w: str) -> Tuple[int, int]:
        r = self.ROWS.index(w[0])
        c = int(w[1:]) - 1
        return r, c

    def _dist(self, a: str, b: str) -> int:
        ra, ca = self._rc(a)
        rb, cb = self._rc(b)
        return abs(ra - rb) + abs(ca - cb)

    def _travel_time(self, a: str, b: str) -> float:
        """移动时间估算（秒）：每跨一个孔位格=1秒，总耗时=|Δrow|+|Δcol|"""
        return float(self._dist(a, b))

    def _compute_loop_time_and_legs(self, path: List[str]) -> Tuple[float, List[Tuple[str, str, int]]]:
        """整圈耗时（含回到起点）与各段耗时列表"""
        legs = []
        n = len(path)
        for i in range(n):
            a, b = path[i], path[(i + 1) % n]
            d = self._dist(a, b)
            legs.append((a, b, d))
        loop_time = float(sum(d for _, _, d in legs))
        return loop_time, legs



if __name__ =='__main__':
    cam = USBVideo()

    cam.update_fm(1,2)
    cam.update_fm(2,3)
    cam.update_fm(3,1)
    print(cam.calcu_best_pos())