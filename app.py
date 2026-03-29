import tkinter as tk
import customtkinter as ctk
import threading
import time
import json
import os

from libs.raspi_con import RaspiConnector
from libs.well_select import WellPlateViewer,WellPosition
from libs.manul_select import StagePositionViewer
from libs.cam import HTTP_MJPEGViewer,USBVideo,TimedCapture
from libs.tools import Tools

# 设置主题
ctk.set_appearance_mode("light")  # Modes: system (default), light, dark
ctk.set_default_color_theme("dark-blue")
ctk.set_widget_scaling(1)


import hashlib


def stable_hash(dic: dict) -> str:
    json_str = json.dumps(dic, separators=(',', ':'), sort_keys=True)
    return hashlib.md5(json_str.encode()).hexdigest()

class UI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # ------------ 窗口设置 ------------
        self.title("OpenLapse Controller")
        self.geometry("1100x630")
        self.resizable(False, False)
        self.wm_attributes("-topmost", True)
        # time.sleep(0.1)
        # self.wm_attributes("-topmost", False)
        # self.attributes("-fullscreen", True)
        # self.root.overrideredirect(True)

        # ------------ 数据参数 ------------
        # 初始化连接器
        self.raspi_ip = None
        self.raspi_udp_port = 5005
        self.raspiConnector = RaspiConnector()

        # 工具方法
        self.tools = Tools()
        self.cam = USBVideo(device=0, 
                            cap_width=3840, cap_height=2160, 
                            pre_width=700,pre_height=380,
                            fps=60, use_mjpeg=True)

        # 最新数据
        self.after(100, self.update_data)

        self.cur_x = 0
        self.cur_y = 0
        self.cur_z = 0
        self.xy_is_homed = False
        self.z_is_homed = False
        self.is_focusing = False

        self.fm = None
        self.best_pos = None
        self.auto_focus_done = False

        self.tar_x = None
        self.tar_y = None
        self.cam_timer = None

        # # 对焦字典
        # self.focus_array = {
        #     'well':
        # }

        self.move_evt: threading.Event | None = None
        self.move_lock = threading.Lock()
        self.pending_well: str | None = None

        # 心跳检查
        self.heartbeat_after_id = None
        self.heartbeat_timeout_sec = 5
        self.start_check_heartbeat = False
        self.last_heartbeat_time = time.time()


        # UI参数
        self.xy_speed_slider_value = tk.DoubleVar(value=500)
        self.z_speed_slider_value = tk.DoubleVar(value=500)
        self.xy_step_slider_value = tk.DoubleVar(value=500)
        self.z_step_slider_value = tk.DoubleVar(value=500)

        self.light_r_slider_value = tk.DoubleVar(value=254)
        self.light_g_slider_value = tk.DoubleVar(value=254)
        self.light_b_slider_value = tk.DoubleVar(value=254)
        self.light_brt_slider_value = tk.DoubleVar(value=254)

        self.selected_plate_type = "96"  # 默认孔板类型
        self.x_limit = 1000
        self.y_limit = 1000

        # 保存地址
        self.preview_save_path = "./preview_imgs"

        # ------------ UI组件 ------------
        # 网格布局
        self.grid_columnconfigure(0, weight=0) # 侧边栏
        self.grid_columnconfigure(1, weight=1) # 主显示区
        self.grid_rowconfigure(0, weight=1) # 侧边栏和主显示区
        # self.grid_rowconfigure(1, weight=1)
        self.font_main = ctk.CTkFont(size=14)
        self.font_main_bold = ctk.CTkFont(size=14, weight="bold")
        self.font_mini = ctk.CTkFont(size=10)
        

        # ------------ 显示组件 ------------
        self.sidebar()
        self.main_display()
        self.log_display()

        self.start_check_heartbeat = False

    # 侧边栏UI
    def sidebar(self):
        # 侧边栏框架
        self.sidebar_frame = ctk.CTkFrame(self, width=160, corner_radius=5)
        self.sidebar_frame.grid(row=0, column=0, rowspan=10, sticky="nsew")
        # 侧边栏网格布局
        self.sidebar_frame.grid_rowconfigure(0, weight=0)
        self.sidebar_frame.grid_rowconfigure((1,2,3,4,5,6,7,8,9,10), weight=1)
        self.sidebar_frame.grid_columnconfigure((0,1), weight=0)

        # 侧边栏logo
        ctk.CTkLabel(self.sidebar_frame, text="OpenLapse", font=ctk.CTkFont(size=30, weight="bold")).grid(row=0, column=0, padx=20, pady=(10, 10), sticky="n")

        # 分割线
        ctk.CTkFrame(self.sidebar_frame, height=2, fg_color="gray", corner_radius=1).grid(row=1, column=0, padx=(5,5), pady=(10, 10), sticky="ew")
        # 连接状态
        ctk.CTkLabel(self.sidebar_frame, text="Connection Status:", font=self.font_main).grid(row=2, column=0, padx=5, pady=(0, 0), sticky="w")
        self.label_con_status = ctk.CTkLabel(self.sidebar_frame, text="Disconnected", font=self.font_main_bold, text_color="red")
        self.label_con_status.grid(row=3, column=0, padx=0, pady=(0, 0),sticky="ew")

         # 分割线
        ctk.CTkFrame(self.sidebar_frame, height=2, fg_color="gray", corner_radius=1).grid(row=4, column=0, padx=(5,5), pady=(10, 10), sticky="ew")
        # ip地址输入框
        ctk.CTkLabel(self.sidebar_frame, text="Raspberry Pi IP:", font=self.font_main).grid(row=5, column=0, padx=5, pady=(0, 0), sticky="w")
        self.ip_input = ctk.CTkEntry(self.sidebar_frame, placeholder_text="default: 10.42.0.1", font=self.font_main)
        self.ip_input.grid(row=6, column=0, padx=20, pady=(10, 0), sticky="ew")

        # 自动搜索
        # 创建一个水平子frame来放两个按钮
        button_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        button_frame.grid(row=7, column=0, padx=20, pady=(10, 0), sticky="ew")
        button_frame.grid_columnconfigure((0,1), weight=1)

        # 左按钮
        ctk.CTkButton(button_frame, text="Auto Search", font=self.font_main,width=80,
                    command=self.ip_auto_search).grid(row=0, column=0, padx=(0,5), sticky="ew")

        # 右按钮
        self.con_button = ctk.CTkButton(button_frame, text="Connect", font=self.font_main,width=80,
                    command=self.ip_connect)
        self.con_button.grid(row=0, column=1, padx=(5,0), sticky="ew")

         # 分割线
        # ctk.CTkFrame(self.sidebar_frame, height=2, fg_color="gray", corner_radius=1).grid(row=8, column=0, padx=(5,5), pady=(10, 10), sticky="ew")

        # 速度和步长调节tabview
        self.tabview = ctk.CTkTabview(self.sidebar_frame, width=160, height=60)
        self.tabview.grid(row=8, column=0, padx=5, pady=(5, 0), sticky="nsew")
        self.tabview.add("Speed")
        self.tabview.add("Step")
        self.tabview.tab("Speed").grid_columnconfigure(0, weight=0)
        self.tabview.tab("Step").grid_columnconfigure(0, weight=0)
        
        # 速度调节X-Y
        ctk.CTkLabel(self.tabview.tab("Speed"), text="XY Speed", font=self.font_main).grid(row=0, column=0, padx=(0,0), pady=(0, 0), sticky="ew")
        self.xy_speed_slider = ctk.CTkSlider(self.tabview.tab("Speed"), from_=100, to=2000, number_of_steps=100, width=140, variable=self.xy_speed_slider_value)
        self.xy_speed_slider.grid(row=0, column=1, padx=0, pady=(0, 0), sticky="ew")
        # 速度调节Z
        ctk.CTkLabel(self.tabview.tab("Speed"), text="Z- Speed", font=self.font_main).grid(row=1, column=0, padx=(0,0), pady=(0, 0), sticky="ew")
        self.z_speed_slider = ctk.CTkSlider(self.tabview.tab("Speed"), from_=100, to=2000, number_of_steps=100, width=140, variable=self.z_speed_slider_value)
        self.z_speed_slider.grid(row=1, column=1, padx=0, pady=(0, 0), sticky="ew")
        # 步长调节X-Y
        ctk.CTkLabel(self.tabview.tab("Step"), text="XY Steps", font=self.font_main).grid(row=0, column=0, padx=(0,0), pady=(0, 0), sticky="ew")
        self.xy_step_slider = ctk.CTkSlider(self.tabview.tab("Step"), from_=100, to=2000, number_of_steps=500, width=144, variable=self.xy_step_slider_value)
        self.xy_step_slider.grid(row=0, column=1, padx=0, pady=(0, 0), sticky="ew")
        # 步长调节Z
        ctk.CTkLabel(self.tabview.tab("Step"), text="Z- Steps", font=self.font_main).grid(row=1, column=0, padx=(0,0), pady=(0, 0), sticky="ew")
        self.z_step_slider = ctk.CTkSlider(self.tabview.tab("Step"), from_=10, to=2000, number_of_steps=500, width=144, variable=self.z_step_slider_value)
        self.z_step_slider.grid(row=1, column=1, padx=0, pady=(0, 0), sticky="ew")

        # 方向按钮框架
        self.button_frame = ctk.CTkFrame(self.sidebar_frame,height=100,)
        self.button_frame.grid(row=9, column=0, padx=5, pady=(10, 0), sticky="nsew")
        # X-按钮
        ctk.CTkButton(self.button_frame, text="←", font=self.font_main, width=30, command=self.button_x_minus_action).grid(row=1, column=0, padx=(15,5), pady=5)
        # X+按钮
        ctk.CTkButton(self.button_frame, text="→", font=self.font_main, width=30, command=self.button_x_plus_action).grid(row=1, column=2, padx=5, pady=5)
        # Y-按钮
        ctk.CTkButton(self.button_frame, text="↑", font=self.font_main, width=30, command=self.button_y_minus_action).grid(row=0, column=1, padx=5, pady=(15,5))
        # Y+按钮
        ctk.CTkButton(self.button_frame, text="↓", font=self.font_main, width=30, command=self.button_y_plus_action).grid(row=2, column=1, padx=5, pady=(5,15))
        # Z+按钮
        ctk.CTkButton(self.button_frame, text="↑", font=self.font_main, width=30, command=self.button_z_up_action).grid(row=0, column=3, padx=(30,15), pady=5)
        # Z-按钮
        ctk.CTkButton(self.button_frame, text="↓", font=self.font_main, width=30, command=self.button_z_down_action).grid(row=2, column=3, padx=(30,15), pady=5)
        # 零点标记
        ctk.CTkLabel(self.button_frame, text="🏠", font=ctk.CTkFont(size=10)).grid(row=0, column=0, padx=(5,5), pady=5)

        # 回零按钮frame
        button_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        button_frame.grid(row=10, column=0, padx=20, pady=(10, 0), sticky="ew")
        button_frame.grid_columnconfigure((0,1), weight=1)

        # 左按钮
        ctk.CTkButton(button_frame, text="XY home", font=self.font_main,width=80,
                    command=self.button_xy_home).grid(row=0, column=0, padx=(0,5), pady=(0,1),sticky="ew")

        # 右按钮
        ctk.CTkButton(button_frame, text="Z home", font=self.font_main,width=80,
                    command=self.button_z_home).grid(row=0, column=1, padx=(5,0), pady=(0,1), sticky="ew")

        # 版本号
        self.label_version = ctk.CTkLabel(self.sidebar_frame, text="only for research (v0.1)", font=self.font_mini)
        self.label_version.grid(row=11, column=0, padx=10, pady=(0, 0), sticky="s")

    # 主显示区UI
    # 主页面
    def main_display(self):
        # 选项卡切换：相机预览-拍摄任务-参数设置-校准
        self.main_tab = ctk.CTkTabview(self, width=800, height=600)
        self.main_tab.grid(row=0, column=1, rowspan=1, sticky="nsew", padx=(10,10), pady=(0,10))
        self.main_tab.add("Preview")
        self.main_tab.add("Well Capture")
        self.main_tab.add("Manual Capture")
        self.main_tab.add("Settings")
        # self.main_tab.add("Calibration")

        # ------------ Preview ------------ #
        # 设置 Preview tab 的网格权重（关键）
        preview_tab = self.main_tab.tab("Preview")
        preview_tab.grid_rowconfigure(0, weight=0)
        preview_tab.grid_rowconfigure(1, weight=1)
        preview_tab.grid_columnconfigure(0, weight=0)
        preview_tab.grid_columnconfigure(1, weight=1)
        

        # 相机预览tab：预览窗口
        self.video_frame = ctk.CTkFrame(preview_tab, corner_radius=5,width=700, height=394,bg_color='transparent',)
        self.video_frame.grid(row=0, column=0, rowspan=1, columnspan=1, sticky="nsew", padx=10, pady=10)
        self.video_frame.grid_rowconfigure(0, weight=1)
        self.video_frame.grid_columnconfigure(0, weight=1)

        # 创建嵌入的 MJPEG 流播放器
        # self.viewer = HTTP_MJPEGViewer(self.video_frame, stream_url="http://192.168.1.102:8081/stream.mjpg", width=400, height=300)
        self.viewer = ctk.CTkLabel(self.video_frame, text="")
        self.viewer.configure(image=self.cam.get_img(), text="")
        self.viewer.grid(row=0, column=0, sticky="nsew",padx=0, pady=0)
        
        # 位置显示器
        # self.manual_viewer = StagePositionViewer(preview_tab, canvas_height=300, init_pos=(150, 100))
        # self.manual_viewer.grid(row=0, column=1, padx=10, pady=10, sticky="nw")
        
        # 右侧操作区域frame
        self.right_operation_frame = ctk.CTkFrame(preview_tab, corner_radius=5,bg_color='transparent',border_color="#999",border_width=0)
        self.right_operation_frame.grid(row=0, column=1, columnspan=1, padx=0, pady=10, sticky="n")
        self.right_operation_frame.grid_rowconfigure((0,1),weight=1)
        self.right_operation_frame.grid_columnconfigure((0,1),weight=1)

        self.right_operation_frame.grid_rowconfigure(2,weight=1)
        

        # 开启/关闭预览按钮
        self.preview_button = ctk.CTkButton(self.right_operation_frame, text="Start Preview", font=self.font_main, command=self.start_preview)
        self.preview_button.grid(row=0, column=0, padx=(5,5), pady=(0,5), sticky="nsew")
        # 截图按钮
        self.capture_button = ctk.CTkButton(self.right_operation_frame, text="Capture Image", font=self.font_main, command=self.preview_capture_image)
        self.capture_button.grid(row=1, column=0, padx=(5,5), pady=(5,5), sticky="nsew")
        # 关灯
        self.off_light_button = ctk.CTkButton(self.right_operation_frame, text="Off Light", font=self.font_main, command=self.trun_off_light)
        self.off_light_button.grid(row=2, column=0, padx=(5,5), pady=(5,5), sticky="s")
        # 上传配置
        self.light_config_button = ctk.CTkButton(self.right_operation_frame, text="Update Config", font=self.font_main, command=self.update_light_config)
        self.light_config_button.grid(row=3, column=0, padx=(5,5), pady=(5,5), sticky="s")

        # 自动对焦
        self.focus_button = ctk.CTkButton(self.right_operation_frame, text="Fast Focus", font=self.font_main, command=self.fast_auto_focus)
        self.focus_button.grid(row=4, column=0, padx=(5,5), pady=(5,5), sticky="s")

        self.precise_focus_button = ctk.CTkButton(self.right_operation_frame, text="Precise Focus", font=self.font_main, command=self.precise_auto_focus)
        self.precise_focus_button.grid(row=5, column=0, padx=(5,5), pady=(5,5), sticky="s")


        # 显示位置
        self.pos_x_label = ctk.CTkLabel(self.right_operation_frame, text="X:", font=self.font_main)
        self.pos_x_label.grid(row=6, column=0, padx=5, pady=(20,0), sticky="w")

        self.pos_y_label = ctk.CTkLabel(self.right_operation_frame, text="Y:", font=self.font_main)
        self.pos_y_label.grid(row=7, column=0, padx=5, pady=(5,0), sticky="w")

        self.pos_z_label = ctk.CTkLabel(self.right_operation_frame, text="Z:", font=self.font_main)
        self.pos_z_label.grid(row=8, column=0, padx=5, pady=(5,5), sticky="w")

        # 显示清晰度
        self.fm_label = ctk.CTkLabel(self.right_operation_frame, text="F:", font=self.font_main)
        self.fm_label.grid(row=9, column=0, padx=5, pady=(5,5), sticky="w")

        # 底部操作区域
        self.bottom_operation_frame = ctk.CTkFrame(preview_tab, corner_radius=5,bg_color='transparent',border_color="#999",border_width=1)
        self.bottom_operation_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="nwes")
        
        # 背光rgb和亮度调节
        # 创建标签
        ctk.CTkLabel(self.bottom_operation_frame, text="light_R", font=self.font_main).grid(row=0, column=0, padx=5, pady=(3,0), sticky="w")
        self.light_r_input = ctk.CTkEntry(self.bottom_operation_frame, placeholder_text="0-255", font=self.font_main,width=60)
        self.light_r_input.grid(row=0, column=1, padx=5, pady=(5, 0), sticky="ew")

        ctk.CTkLabel(self.bottom_operation_frame, text="light_G", font=self.font_main).grid(row=1, column=0, padx=5, pady=(3,0), sticky="w")
        self.light_g_input = ctk.CTkEntry(self.bottom_operation_frame, placeholder_text="0-255", font=self.font_main,width=60)
        self.light_g_input.grid(row=1, column=1, padx=5, pady=(5, 0), sticky="ew")

        ctk.CTkLabel(self.bottom_operation_frame, text="light_B", font=self.font_main).grid(row=2, column=0, padx=5, pady=(3,0), sticky="w")
        self.light_b_input = ctk.CTkEntry(self.bottom_operation_frame, placeholder_text="0-255", font=self.font_main,width=60)
        self.light_b_input.grid(row=2, column=1, padx=5, pady=(5, 0), sticky="ew")

        ctk.CTkLabel(self.bottom_operation_frame, text="light_W", font=self.font_main).grid(row=0, column=2, padx=(20,5), pady=(3,0), sticky="w")
        self.light_w_input = ctk.CTkEntry(self.bottom_operation_frame, placeholder_text="0-255", font=self.font_main,width=60)
        self.light_w_input.grid(row=0, column=4, padx=5, pady=(5, 0), sticky="ew")

        # ctk.CTkLabel(self.bottom_operation_frame, text="light_G", font=self.font_main).grid(row=1, column=2, padx=(20,5), pady=(3,0), sticky="w")
        # self.light_g_input = ctk.CTkEntry(self.bottom_operation_frame, placeholder_text="0-255", font=self.font_main,width=60)
        # self.light_g_input.grid(row=1, column=4, padx=5, pady=(5, 0), sticky="ew")

        # ctk.CTkLabel(self.bottom_operation_frame, text="light_B", font=self.font_main).grid(row=2, column=2, padx=(20,5), pady=(3,0), sticky="w")
        # self.light_g_input = ctk.CTkEntry(self.bottom_operation_frame, placeholder_text="0-255", font=self.font_main,width=60)
        # self.light_g_input.grid(row=2, column=4, padx=5, pady=(5, 0), sticky="ew")


        # 初始值
        self.light_r_input.insert(0, "255")
        self.light_g_input.insert(0, "255")
        self.light_b_input.insert(0, "255")
        self.light_w_input.insert(0, "255")





        # ------------ Well Capture ------------ #
        capture_tab = self.main_tab.tab("Well Capture")
        # Capture tab 列宽配置
        capture_tab.grid_columnconfigure(0, weight=1)  # Well Plate Type
        capture_tab.grid_columnconfigure(1, weight=1)  # Interval
        capture_tab.grid_columnconfigure(2, weight=1)  # Duration
        capture_tab.grid_columnconfigure(3, weight=1)  # Prefix
        capture_tab.grid_columnconfigure(4, weight=0)  # Clear Button（固定宽）
        capture_tab.grid_columnconfigure(5, weight=0)  # Get Button（固定宽）

        # 创建孔板选择器
        self.plate_viewer = WellPlateViewer(capture_tab, well_plate_type=self.selected_plate_type, width=600, height=400)
        self.plate_viewer.grid(row=0, column=0, columnspan=6, padx=10, pady=10)

        # 创建标签
        ctk.CTkLabel(capture_tab, text="Plate Type:", font=self.font_main).grid(row=1, column=0, padx=0, pady=(0,0), sticky="w")
        # 拍摄间隔
        ctk.CTkLabel(capture_tab, text="Interval(s):", font=self.font_main).grid(row=1, column=1, padx=(10,0), pady=(0,0), sticky="w")
        # 拍摄时间长度
        ctk.CTkLabel(capture_tab, text="Duration(h):", font=self.font_main).grid(row=1, column=2, padx=(10,0), pady=(0,0), sticky="w")
        # 实验名称
        ctk.CTkLabel(capture_tab, text="Name:", font=self.font_main).grid(row=1, column=3, padx=(10,0), pady=(0,0), sticky="w")

        # 孔板类型选择下拉菜单
        self.plate_type_menu = ctk.CTkOptionMenu(capture_tab, values=["96", "24", "12", "6"], font=self.font_main, command=self.select_plate_type)
        self.plate_type_menu.set(self.selected_plate_type)  # 设置默认值
        self.plate_type_menu.grid(row=2, column=0, padx=0, pady=(0,10), sticky="ew")

        # 拍摄间隔
        self.interval_input = ctk.CTkEntry(capture_tab, placeholder_text="1-60", font=self.font_main)
        self.interval_input.grid(row=2, column=1, padx=(10,0), pady=(0,10), sticky="ew")

        # 拍摄时间长度
        self.capture_duration_input = ctk.CTkEntry(capture_tab, placeholder_text="1-96", font=self.font_main)
        self.capture_duration_input.grid(row=2, column=2, padx=(10,0), pady=(0,10), sticky="ew")

        # 实验名称
        self.prefix_name_input = ctk.CTkEntry(capture_tab, placeholder_text="e.g., Experiment1", font=self.font_main)
        self.prefix_name_input.grid(row=2, column=3, padx=(10,0), pady=(0,10), sticky="ew")


        # 清空选择按钮
        ctk.CTkButton(capture_tab, text="Clear", font=self.font_main, width=80, command=self.clear_selection).grid(row=2, column=4, pady=(0,10), padx=10, sticky="ew")

        # 移动按钮
        self.button_start = ctk.CTkButton(capture_tab, text="Move", font=self.font_main, command=self.move_to_well)
        self.button_start.grid(row=2, column=5, pady=(0,10), padx=10, sticky="ew")

        # 确定按钮
        self.button_start = ctk.CTkButton(capture_tab, text="Start", font=self.font_main, command=self.start_task)
        self.button_start.grid(row=2, column=6, pady=(0,10), padx=10, sticky="ew")

        # 显示进度条标签
        self.progress_label = ctk.CTkLabel(capture_tab, text="Progress(0%)", font=self.font_main)
        self.progress_label.grid(row=3, column=0, padx=(0,0), pady=(0,10), sticky="w")
        # 进度条
        self.progress_bar = ctk.CTkProgressBar(capture_tab, width=600)
        self.progress_bar.grid(row=3, column=1, columnspan=6, padx=(10,10), pady=(0,10), sticky="ew")
        self.progress_bar.set(0)  # 初始进度为0

        # ------------ Manual Capture ------------ #
        manual_capture_tab = self.main_tab.tab("Manual Capture")
        manual_capture_tab.grid_rowconfigure((0, 1), weight=1)
        manual_capture_tab.grid_columnconfigure((0, 1), weight=1)

        # 创建标签


    # 全局log
    def log_display(self):
        self.log_textbox = ctk.CTkTextbox(self, width=800, height=50, font=self.font_mini)
        self.log_textbox.grid(row=1, column=1, columnspan=1, sticky="nsew", padx=(10,10), pady=(0,10))
        self.log_textbox.insert("0.0", "Log Output:\n")
        self.log_textbox.configure(state="disabled")  # 设置为只读

    # 回调函数
    def ip_auto_search(self):
        self.log_message("Starting auto search for Raspberry Pi...")

        # 开始扫描
        new_ip = self.raspiConnector.get_rpi_ip()
        if new_ip:
            self.log_message(f"Found Raspberry Pi at IP: {new_ip}")
            # 更新输入框
            self.ip_input.delete(0, "end")  # 清空原内容
            self.ip_input.insert(0, new_ip)  # 插入新内容
        else:
            self.log_message("Raspberry Pi not found on the network.")
            # 更新输入框
            self.ip_input.delete(0, "end")  # 清空原内容
            self.ip_input.insert(0, '')  # 插入新内容

    def ip_connect(self):
        self.raspi_ip = self.ip_input.get()
        if not self.raspi_ip:
            self.log_message("未输入Raspberry Pi的IP地址")
            return
        # 若未连接则尝试建立TCP
        if not self.raspiConnector.connected and self.raspiConnector.rpi_ip:
            self.raspiConnector.connect_tcp()
            if self.raspiConnector.connected:
                self.label_con_status.configure(text="Connected", text_color="green")
                self.con_button.configure(text="Disconnect", command=self.dis_connect)
                self.log_message(f"Connected to Raspberry Pi at IP: {self.raspi_ip}")
                self.start_check_heartbeat = True
            else:
                self.label_con_status.configure(text="Disconnected", text_color="red")
                self.log_message("Failed to connect to Raspberry Pi.")
        else:
            self.log_message("Already connected or IP not set in connector.")
        
        # 启动心跳检查
        if self.raspiConnector.connected:
            self.start_check_heartbeat = True
            self.start_heartbeat_timer()

    def dis_connect(self):
        if self.raspiConnector.connected:
            self.raspiConnector.disconnect_tcp()
            # 关闭心跳检查
            self.stop_heartbeat_timer()
            self.start_check_heartbeat = False
            self.label_con_status.configure(text="Disconnected", text_color="red")
            self.con_button.configure(text="Connect", command=self.ip_connect)
            self.log_message("Disconnected from Raspberry Pi.")
        else:
            self.log_message("Not connected to any Raspberry Pi.")

    def button_x_minus_action(self):
        steps = int(self.xy_step_slider_value.get())
        speed = int(self.xy_speed_slider_value.get())
        data = {
            'type': 'MOVE',
            'axis': 'X',
            'direction': 0,  # 0代表负方向
            'steps': steps,
            'speed': speed
        }
        self.send_data(data)

    def button_x_plus_action(self):
        steps = int(self.xy_step_slider_value.get())
        speed = int(self.xy_speed_slider_value.get())
        data = {
            'type': 'MOVE',
            'axis': 'X',
            'direction': 1,  # 1代表正方向
            'steps': steps,
            'speed': speed
        }
        self.send_data(data)


    def button_y_minus_action(self):
        steps = int(self.xy_step_slider_value.get())
        speed = int(self.xy_speed_slider_value.get())
        data = {
            'type': 'MOVE',
            'axis': 'Y',
            'direction': 0,  # 0代表负方向
            'steps': steps,
            'speed': speed
        }
        self.send_data(data)
    
    def button_y_plus_action(self):
        steps = int(self.xy_step_slider_value.get())
        speed = int(self.xy_speed_slider_value.get())
        data = {
            'type': 'MOVE',
            'axis': 'Y',
            'direction': 1,  # 1代表正方向
            'steps': steps,
            'speed': speed
        }
        self.send_data(data)

    def button_z_up_action(self):
        steps = int(self.z_step_slider_value.get())
        speed = int(self.z_speed_slider_value.get())
        data = {
            'type': 'MOVE',
            'axis': 'Z',
            'direction': 0,
            'steps': steps,
            'speed': speed
        }
        self.send_data(data)

    def button_z_down_action(self):
        steps = int(self.z_step_slider_value.get())
        speed = int(self.z_speed_slider_value.get())
        data = {
            'type': 'MOVE',
            'axis': 'Z',
            'direction': 1,
            'steps': steps,
            'speed': speed
        }
        self.send_data(data)

    def button_xy_home(self):
        data = {
            'type': 'HOME',
            'axis': 'XY',
        }
        self.send_data(data)

    def button_z_home(self):
        data = {
            'type': 'HOME',
            'axis': 'Z',
        }
        self.send_data(data)

    def start_preview(self):
        """开始MJPEG流预览"""
        if not self.cam.running:
            self.cam.start()
            self.preview_button.configure(
                text="Stop Preview",
                fg_color="red",           # 主颜色
                hover_color="#cc0000",    # 悬停时颜色（可选）
                text_color="white",       # 字体颜色（可选）
                command=self.stop_preview
            )

            def trun_on_light():
                data = {
                    'type': 'LIGHT',
                    'r': int(self.light_r_input.get()),
                    'g': int(self.light_g_input.get()),
                    'b': int(self.light_b_input.get()),
                    'brt': int(self.light_w_input.get()),
                    'cmd': 'all',
                }
                self.send_data(data)

            trun_on_light()
            self.log_message("Started preview.")

        else:
            self.log_message("[INFO] Preview already running.")

    def stop_preview(self):
        """停止MJPEG流预览"""
        self.cam.stop()
        self.preview_button.configure(text="Start Preview", 
            fg_color="#3b7fbf",           # 主颜色
            hover_color="#325883",    # 悬停时颜色（可选）
            text_color="white",       # 字体颜色（可选）
            command=self.start_preview
        )
        # # 发送数据
        # data = {
        #     'type': 'CAM',
        #     'preview': 'False',
        # }
        # self.send_data(data)
        def trun_off_light():
            data = {
                'type': 'LIGHT',
                'r': int(self.light_r_input.get()),
                'g': int(self.light_g_input.get()),
                'b': int(self.light_b_input.get()),
                'brt': int(self.light_w_input.get()),
                'cmd': 'close',
            }
            self.send_data(data)
        trun_off_light()
        self.log_message("Stopped MJPEG stream preview.")

    def preview_capture_image(self):
        path = self.tools.get_save_path(self.preview_save_path,sub_folder='debug_preview',well_name='preview',ext='png')
        self.log_message(f"Capturing image to: {path}")
        # path = os.path.join(self.preview_save_path, self.tools.get_img_pfrefix(),
        self.cam.capture_frame(path)

    def trun_off_light(self):
        try:
            data = {
                'type': 'LIGHT',
                'r': None,
                'g': None,
                'b': None,
                'brt': None,   # 亮度或白光
                'cmd': 'close',
            }
        except ValueError:
            return

        # 发送数据
        self.send_data(data)


    def update_light_config(self):
        # 获取输入值
        r = self.light_r_input.get()
        g = self.light_g_input.get()
        b = self.light_b_input.get()
        w = self.light_w_input.get()

        # 检查非空
        if not all([r, g, b, w]):
            self.log_message("❗请填写完整 RGBW 数值")
            return


        try:
            data = {
                'type': 'LIGHT',
                'r': int(r),
                'g': int(g),
                'b': int(b),
                'brt': int(w),   # 亮度或白光
                'cmd': 'all',
            }
        except ValueError:
            self.log_message("❗请输入 0–255 的整数")
            return

        # 发送数据
        self.send_data(data)
        self.log_message(f"已更新灯光配置: R={r}, G={g}, B={b}, W={w}")

    def move_to_well(self):
        # 移动到指定位置
        well_type, wells = self.plate_viewer.get_selected()
        if wells:
            self.log_message(f"选中孔位: {', '.join(wells)}")
            self.move_to(well_type,wells[0])
    
    def move_to(self,well_type, well_name):
        # 移动到指定位置
        def move_to_pos(x,y,z,speed):
            data = {
                'type': 'MOVETO',
                'x': x,
                'y': y,
                'z': z,
                'speed': speed,
                'light': well_name,
                'well':well_type
            }
            self.send_data(data)
        speed = 5000
        # 检查孔板类型
        if well_type=='96':
            wellpos = WellPosition(start=(19150, 3300), end=(97550, 53350),
                                    rows='ABCDEFGH', cols=range(1, 13)
                                    )
            pos = wellpos.get_xy(well_name)
            if pos:
                move_to_pos(pos[0],pos[1],self.cur_z,speed)
                self.log_message(f'Move to {str(well_name)}:{pos[0]},{pos[1]},{self.cur_z},speed:{speed}')

                return pos[0],pos[1]
        
    def move_to_async(self, plate: str, well: str) -> threading.Event:
        """
        发起异步移动：后台线程负责调用 move_to 并等待到位；
        返回一个 Event，完成时 set()。
        """
        evt = threading.Event()
        FOCUS_TIMEOUT = 60
        def worker():
            # 1) 计算目标位，并移动到位
            tx, ty = self.move_to(plate, well)   # 你现有的同步函数
            # # 2) 启动自动对焦（内部开线程）
            # self.precise_auto_focus()  # 或 fast=False 视情况
            # # 等对焦完成
            # f_start_t = time.time()
            # while True:
            #     if self.auto_focus_done:
            #         break
            #     if time.time() - f_start_t > FOCUS_TIMEOUT:
            #         # 超时处理
            #         self.log_message("auto focus timeout, skip focus and continue shooting")
            #         try:
            #             self.cam.reset_fm_list()
            #         except Exception:
            #             pass
            #         # 直接跳出循环，继续后面的流程
            #         break
            #     time.sleep(0.1)
            #     # 如果对焦超时则继续

            with self.move_lock:
                self.tar_x, self.tar_y = tx, ty

            # 2) 等待到位（在后台线程里忙等/小睡，不占用主循环）
            while True:
                with self.move_lock:
                    done = (self.cur_x == self.tar_x and self.cur_y == self.tar_y)
                if done:
                    # 拍照
                    sub_folder = self.prefix_name_input.get()
                    if sub_folder:
                        path = self.tools.get_save_path(self.preview_save_path,sub_folder=sub_folder,well_name=well,ext='png')
                    else:
                        path = self.tools.get_save_path(self.preview_save_path,sub_folder='known_'+str(time.time()),well_name=well,ext='png')
                    self.log_message(f"Capturing image to: {path}")
                    # path = os.path.join(self.preview_save_path, self.tools.get_img_pfrefix(),
                    self.cam.capture_frame(path)

                    break

                
                time.sleep(0.01)  # 10ms 轮询

            evt.set()

        threading.Thread(target=worker, daemon=True).start()
        return evt

    def fast_auto_focus(self):
        self.auto_focus(fast = True)

    def precise_auto_focus(self):
        self.auto_focus(fast = False)

    def auto_focus(self,fast = False):

        self.precise_focus_button.configure(state="disabled")
        self.focus_button.configure(state="disabled")
        self.start_preview()

        # 每次对焦前重置标志
        self.auto_focus_done = False
        self.best_pos = None

        z_now_pos = self.cur_z

        try:
            # 设定对焦范围
            if fast:
                # 中心扫描
                data = {
                    'type': 'FOCUS',
                    'speed': 5000,  # 要足够的慢
                    'from': self.cur_z-20000,
                    'to': self.cur_z+20000,
                    'cur':self.cur_z
                }
            else:
                # 精细扫描
                data = {
                    'type': 'FOCUS',
                    'speed': 200,  # 要足够的慢
                    'from': self.cur_z-2000,
                    'to': self.cur_z+2000,
                    'cur':self.cur_z
                }
            # 发送
            self.send_data(data)
            self.best_pos = None

            # time.sleep(5)

            def _func():
                while True:
                    # self.log_message(f'{self.is_focusing},{self.is_focusing == True}')
                    print(f'{self.is_focusing},{self.is_focusing == True}')
                    # 是否处于对焦程序
                    if self.is_focusing:
                    # 计算清晰度
                        self.cam.update_fm(self.cur_z,self.fm)
                        print(f'更新fm,len={len(self.cam.fm_list)}')
                        # 计算
                        self.best_pos = self.cam.calcu_best_pos()
                        print(f'best_fm pos={self.best_pos}')
                    else:
                        time.sleep(1)
                        if not self.is_focusing:
                            self.cam.reset_fm_list()
                            break
                    time.sleep(0.01)
                
                # 对焦结束，哪怕没找到best_pos也要告诉外面“结束了”
                if self.best_pos is not None:
                    self.log_message(f'finish auto focus, Z pos={self.best_pos}')
                    self.log_message(f'move to, Z pos={self.best_pos}')
                    def move_to_pos():
                        data = {
                            'type': 'MOVETO',
                            'x': None,
                            'y': None,
                            'z': self.best_pos,
                            'speed': 6000,
                            # 'light': well_name,
                            # 'well':well_type
                        }
                        self.send_data(data)
                    move_to_pos()
                else:
                    self.log_message(f'auto focus finished but no best_pos found')
                    def move_to_pos():
                        data = {
                            'type': 'MOVETO',
                            'x': None,
                            'y': None,
                            'z': z_now_pos,  # 回到原来的位置
                            'speed': 6000,
                            # 'light': well_name,
                            # 'well':well_type
                        }
                        self.send_data(data)
                    move_to_pos()

                self.auto_focus_done = True

                self.precise_focus_button.configure(state="normal")
                self.focus_button.configure(state="normal")
            threading.Thread(target=_func, daemon=True).start()

                    

            

        except Exception as e:
            self.log_message(f'自动对焦出错: {e}')
            self.auto_focus_done = True  # 避免外面一直等

    # 开始拍照
    def start_task(self):
        _well_type, wells = self.plate_viewer.get_selected()
        if wells:
            self.log_message(f"选中孔位: {', '.join(wells)}")

            # 按钮变为停止
            self.button_start.configure(text="Stop", command=self.stop_task)

            # 开始拍摄任务
            well_type = _well_type
            interval = self.interval_input.get()
            duration = self.capture_duration_input.get()
            name = self.prefix_name_input.get()

            if interval and duration and name:
                self.log_message(f'interval={interval},duration={duration},name={name}')

                # 拍照时间监控
                try:
                    self.cam_timer = TimedCapture(
                        interval_s=int(interval), 
                        duration_h=int(duration),
                        wells=wells,
                        first_round_immediate=True
                        )
                    self.cam_timer.start()
                except ValueError as e:
                    self.log_message("❌ 配置不合理：")
                    self.log_message(str(e))

        else:
            self.log_message("未选择任何孔位")
    
    def stop_task(self):
        self.log_message("停止拍摄任务")
        # 关闭任务
        if self.cam_timer:
            self.cam_timer.stop()
        # 按钮变为开始
        self.button_start.configure(text="Start", command=self.start_task)
    
    def select_plate_type(self,value: str):
        self.selected_plate_type = value
        self.log_message(f"当前孔板类型: {self.selected_plate_type}")
        # 刷新孔板显示
        self.plate_viewer.change_well_plate_type(value)

    def clear_selection(self):
        self.plate_viewer.clear_selection()
        self.log_message("已清空已选孔位")

    # 更新进度条
    def update_progress_bar(self, progress: float):
        self.progress_bar.set(progress)
        percent = int(progress * 100)
        self.progress_label.configure(text=f"Progress({percent}%)")

    
    # 心跳检查
    def start_heartbeat_timer(self):
        if self.heartbeat_after_id is None:
            self.heartbeat_after_id = self.after(1000, self.check_heartbeat_timeout)
    
    def stop_heartbeat_timer(self):
        if self.heartbeat_after_id is not None:
            self.after_cancel(self.heartbeat_after_id)
            self.heartbeat_after_id = None

    # 处理心跳包
    def process_heartbeat(self):
        self.last_heartbeat_time = time.time()
        self.start_check_heartbeat = True
        if self.raspiConnector.connected:
            current_color = self.label_con_status.cget("text_color")
            new_color = "blue" if current_color == "green" else "green"
            self.label_con_status.configure(text_color=new_color, text="Connected")
        else:
            self.label_con_status.configure(text="Disconnected", text_color="red")

        # 确保心跳计时器在跑
        self.start_heartbeat_timer()

    # 检测心跳超时
    def check_heartbeat_timeout(self, timeout=5):
        # 这里只检查一次并重排自己；不要被外部频繁调用
        if self.start_check_heartbeat:
            now = time.time()
            if now - self.last_heartbeat_time > self.heartbeat_timeout_sec:
                self.label_con_status.configure(text="Timeout", text_color="red")
                self.log_message("Heartbeat timeout. Disconnected from Raspberry Pi.")
                self.start_check_heartbeat = False
        # 重排下一次
        self.heartbeat_after_id = self.after(1000, self.check_heartbeat_timeout)
    
    # 发送数据
    def send_data(self, msg: dict):
        """发送数据并等待正确ACK"""
        if self.rpi_status=='BUSY':
            self.log_message("Raspberry Pi is busy. Cannot send data now.")
            return
        
        if not self.raspiConnector.connected:
            self.log_message("Not connected. Cannot send data.")
            return

        msg_str = json.dumps(msg, separators=(',', ':'), sort_keys=True)
        msg_hash = stable_hash(msg)

        # 保存当前要确认的消息
        self.last_msg = msg_str
        self.last_hash = msg_hash
        self.waiting_ack = True
        self.max_retry = 3   # 最多重发3次
        self.retry_count = 0

        # 手动设置Raspberry Pi状态为忙碌
        self.raspi_status = 'BUSY'  # 发送数据后设置为忙碌状态

        self.raspiConnector.send(msg_str)
        # self.log_message(f"发送数据hash: {msg_hash}")

    def handle_incoming(self, msg: dict):
        """处理接收数据，包括ACK重发逻辑"""
        if msg.get('type') == 'ACK' and self.waiting_ack:
            recv_hash = msg.get('value')

            # ✅ 匹配成功
            if recv_hash == self.last_hash:
                # self.log_message(f"✅ ACK匹配成功: {recv_hash}")
                self.waiting_ack = False
                self.retry_count = 0
                return

            # ❌ 不匹配时重发
            else:
                self.retry_count += 1
                if self.retry_count <= self.max_retry:
                    self.log_message(
                        f"❌ ACK不匹配: {recv_hash} ≠ {self.last_hash}，第{self.retry_count}次重发..."
                    )
                    self.raspiConnector.send(self.last_msg)
                else:
                    self.log_message("[❌] 超过最大重发次数，放弃等待ACK")
                    self.waiting_ack = False

        elif msg.get('type') == 'HEARTBEAT':
            self.process_heartbeat()
        else:
            self.log_message(f"收到数据: {msg}")

    # 定时更新数据
    def update_data(self):
        # self.manual_viewer.update_position(self.cur_x, self.cur_y)

        # 处理UDP数据
        def process_udp():
            # 处理UDP广播消息
            udp_info = self.raspiConnector.process_broadcast_commands()
            # msg = dict(udp_info) # type: ignore
            
            
            # self.cur_y = 0
            # self.cur_z = 0
            if udp_info:
                msg = udp_info.get('msg')
                if msg:
                    print(msg)
                    try:
                        pos_xyz = json.loads(str(msg))
                        self.cur_x = pos_xyz.get('x')
                        self.cur_y = pos_xyz.get('y')
                        self.cur_z = pos_xyz.get('z')
                        self.xy_is_homed = pos_xyz.get('xy_home')
                        self.z_is_homed = pos_xyz.get('z_home')
                        self.is_focusing = pos_xyz.get('focusing')
                        # print(self.cur_x,self.cur_y,self.cur_z)

                        if self.xy_is_homed:
                            self.pos_x_label.configure(text=f"X: A{self.cur_x}")
                            self.pos_y_label.configure(text=f"Y: A{self.cur_y}")
                        else:
                            self.pos_x_label.configure(text=f"X: R{self.cur_x}")
                            self.pos_y_label.configure(text=f"Y: R{self.cur_y}")
                        
                        if self.z_is_homed:
                            self.pos_z_label.configure(text=f"Z: A{self.cur_z}")
                        else:
                            self.pos_z_label.configure(text=f"Z: R{self.cur_z}")
                    except Exception:
                        pass
            if udp_info and not self.raspiConnector.connected:
                self.log_message(udp_info)

        process_udp()

        # 接收TCP数据
        msg = self.raspiConnector.receive_data()
        if msg:
            # 处理心跳消息
            if msg.get('type')=='HEARTBEAT':
                self.process_heartbeat()
            # 处理ACK消息
            elif msg.get('type')=='ACK':
                self.handle_incoming(msg)
            # 其他消息
            else:
                self.log_message(f"收到数据: {msg}")
                pass

        # self.check_heartbeat_timeout()
        # 更新Raspberry Pi状态
        self.rpi_status = self.raspiConnector.get_rpi_status()
        print(self.rpi_status)

        # 刷新摄像头
        def cap_loop():
            # 采集图片
            # 1) 抓一帧到缓存
            self.cam.capture_loop()

            # 2) 取出可显示对象并更新 Label
            imgtk = self.cam.get_img(master=self.viewer)
            if imgtk is not None:
                self.viewer.configure(image=imgtk, text="")
                self._imgtk_ref = imgtk  # ⭐ 必须保存引用
        
        cap_loop()

                
        fm = self.cam.focus_measure_laplacian(roi_wh=(300,300))
        if fm is not None:
            self.fm_label.configure(text=(f'F: {round(fm,2)}'))
            self.fm = fm

        
        # 检查拍照任务
        if self.cam_timer and self.cam_timer.update():
            if (self.move_evt is None) or self.move_evt.is_set():
                well = self.cam_timer.get_well()
                if well:
                    self.log_message(f'拍照触发,{well}')
                    self.pending_well = well
                    # self.tar_x,self.tar_y = self.move_to('96',well) # type: ignore
                    self.move_evt = self.move_to_async('96', well)

        # 非阻塞地检查是否到位（到位后再做下一步，如拍照/对焦等）
        if self.move_evt and self.move_evt.is_set():
            # 清理事件，执行到位后的动作
            self.move_evt = None
            if self.pending_well:
                if self.cam_timer:
                    progress = self.cam_timer.progress()
                    self.log_message(f'到位完成, {self.pending_well} 执行拍照, {round(progress,2)}%')
                    self.progress_bar.set(self.cam_timer.progress()/100)
                    self.progress_label.configure(text=f'{round(progress,2)}%')
                # 清除
                self.pending_well = None




        # 循环
        self.after(int(1/60*1000), self.update_data)
        
    
    def log_message(self, message: str, max_lines: int = 100):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
        # 控制行数
        try:
            total_lines = int(self.log_textbox.index('end-1c').split('.')[0])
            if total_lines > max_lines:
                # 删除最早的若干行（一次删几十行避免频繁重排）
                self.log_textbox.delete("1.0", "50.0")
        except Exception:
            pass
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")


if __name__ == "__main__":

    app = UI()
    app.mainloop()