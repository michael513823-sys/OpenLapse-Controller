# raspi_detector.py
from scapy.all import ARP, Ether, srp, conf # type: ignore
import socket
import ipaddress
import platform
from typing import List, Dict, Optional
import time
import threading
import queue
import json

# UDP接收(非阻塞)
class UDPListener(threading.Thread):
    def __init__(self,  
                 port:int, # 只需要监听端口
                 host:str='0.0.0.0', # 监听本地所有地址
                 ):
        super().__init__(daemon=True)
        # 初始化UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        # 队列存放接收的命令
        self.queue = queue.Queue()
        # 控制运行标志
        self.running = True

    # 线程运行函数
    def run(self):
        # print(f"UDP监听启动：{self.sock.getsockname()}")
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)  # 阻塞等待
                msg = data.decode().strip()
                try:
                    cmd = json.loads(msg)
                except json.JSONDecodeError:
                    print(f"无法解析JSON: {msg}")
                    continue

                # 附加元信息
                cmd["from"] = addr
                cmd["recv_time"] = str(time.time())

                # 放入队列中
                self.queue.put(cmd)
            except Exception as e:
                print("接收异常:", e)
                time.sleep(0.5)

    # 停止监听
    def stop(self):
        self.running = False
        self.sock.close()

class TCPClient(threading.Thread):
    def __init__(self, host:str, port:int, reconnect_delay=3):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.reconnect_delay = reconnect_delay
        self.sock = None
        self.running = True
        self.connected = False
        self.lock = threading.Lock()

        # ✅ 新增部分
        self.recv_queue = queue.Queue()  # 消息队列
        self.callbacks = []              # 消息回调函数列表

    # -----------------------------
    # 主线程运行
    # -----------------------------
    def run(self):
        while self.running:
            if not self.connected:
                try:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(3)
                    self.sock.connect((self.host, self.port))
                    self.sock.setblocking(False)
                    self.connected = True
                    print(f"已连接到服务器 {self.host}:{self.port}")
                except Exception as e:
                    print(f"连接失败: {e}, {self.reconnect_delay}s后重试...")
                    time.sleep(self.reconnect_delay)
                    continue

            # 连接成功后开始监听数据
            try:
                data = self.sock.recv(1024)
                if not data:
                    print("服务器断开连接")
                    self._reset_connection()
                    continue

                msg = data.decode(errors='ignore').strip()
                # ✅ 放入队列
                self.recv_queue.put(msg)
                # ✅ 调用所有回调函数
                for cb in self.callbacks:
                    cb(msg)

            except BlockingIOError:
                # 没有数据，不阻塞
                time.sleep(0.05)
            except ConnectionResetError:
                print("连接被重置，重新连接中...")
                self._reset_connection()
            except Exception as e:
                print(f"接收异常: {e}")
                self._reset_connection()

    # -----------------------------
    # 主动读取消息（非阻塞）
    # -----------------------------
    def get_message(self):
        """非阻塞获取最新消息"""
        try:
            return self.recv_queue.get_nowait()
        except queue.Empty:
            return None

    # -----------------------------
    # 注册回调函数
    # -----------------------------
    def register_callback(self, func):
        """注册回调函数（收到新消息时调用）"""
        if callable(func):
            self.callbacks.append(func)

    # -----------------------------
    # 发送消息
    # -----------------------------
    def send(self, msg:str):
        if self.connected and self.sock:
            try:
                with self.lock:
                    self.sock.sendall(msg.encode())
            except Exception as e:
                print(f"发送失败: {e}")
                self._reset_connection()
        else:
            print("未连接服务器")

    # -----------------------------
    # 内部：重置连接
    # -----------------------------
    def _reset_connection(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.sock = None

    # -----------------------------
    # 停止客户端
    # -----------------------------
    def stop(self):
        self.running = False
        self._reset_connection()
        print("TCP客户端已停止")


# 连接树莓派
class RaspiConnector:
    def __init__(self,
                 rpi_name='OpenLapse',
                 controller_name='OpenLapse_Controller',
                 broadcast_listen_port=64565, # 提前协商好
                ):

        self.rpi_ip = None
        self.rpi_port = None
        
        # self.controller_ip = self._get_ip()
        # self.controller_port = self._find_free_udp_port()

        # 名称验证
        self.rpi_name = rpi_name
        self.controller_name = controller_name

        # 扫描监听端口
        self.broadcast_port = broadcast_listen_port
        self.connected = False

        # 启动广播监听线程
        self.broadcast_listener = UDPListener(port=self.broadcast_port)
        self.broadcast_listener.start()

        # TCP
        self.tcp_client = None

        # 自动重连
        self.auto_reconnect = False

        # rpi状态
        self.rpi_status = None


    # 从广播中提取ip和端口等信息
    def process_broadcast_commands(self):
        """从广播中提取Raspberry Pi IP和端口，并自动更新TCP连接"""
        try:
            cmd = self.broadcast_listener.queue.get_nowait()
            if cmd.get("name") != self.rpi_name:
                return

            new_ip = cmd.get("rpi_ip")
            new_port = cmd.get("rpi_port")
            self.rpi_status = cmd.get("status")

            # 检测到地址变化时，自动更新
            if new_ip and new_port:
                if (new_ip != self.rpi_ip) or (new_port != self.rpi_port):
                    self.rpi_ip = new_ip
                    self.rpi_port = new_port
            

            return cmd
        except queue.Empty:
            pass
        except Exception as e:
            print(f"⚠️ 广播处理异常: {e}")

    # 连接树莓派TCP
    def connect_tcp(self):
        """根据广播结果自动建立TCP连接"""
        if self.rpi_ip and self.rpi_port:
            if not self.tcp_client or not self.tcp_client.connected:
                print(f"尝试连接到树莓派: {self.rpi_ip}:{self.rpi_port}")
                self.tcp_client = TCPClient(self.rpi_ip, self.rpi_port)
                self.tcp_client.start()
                self.connected = True
        else:
            print("尚未获取Raspberry Pi的IP和端口，无法连接TCP")

    def send(self, msg:str):
        """发送命令到树莓派"""
        if self.tcp_client and self.tcp_client.connected:
            self.tcp_client.send(msg)

    # UI获取IP
    def get_rpi_ip(self):
        return self.rpi_ip

    def get_rpi_status(self):
        return self.rpi_status

    def receive_data(self):
        """从TCP客户端获取一条消息（非阻塞）"""
        if self.tcp_client and self.tcp_client.connected:
            msg = self.tcp_client.get_message()
            if msg:
                try:
                    # 自动解析JSON
                    data = json.loads(msg)
                    return data
                except json.JSONDecodeError:
                    return {"raw": msg}
        return None
    
    def disconnect_tcp(self):
        """断开TCP连接"""
        if self.tcp_client:
            self.tcp_client.stop()
            self.tcp_client = None
            self.connected = False
            print("✅ 已断开TCP连接")







if __name__ == "__main__":
    rpicon = RaspiConnector()

    while True:
        # 持续处理UDP广播
        rpicon.process_broadcast_commands()

        # 若未连接则尝试建立TCP
        if not rpicon.connected and rpicon.rpi_ip:
            rpicon.connect_tcp()

        # 获取TCP消息
        msg = rpicon.receive_data()
        if msg:
            print("📩 收到消息:", msg)

        time.sleep(0.1)

        print("...")

        send_data = {"cmd":"ping","time":str(time.time())}
        rpicon.send(json.dumps(send_data))
        time.sleep(5)
