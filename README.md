# OpenLapse Controller

A desktop GUI for operating a DIY, in-incubator time-lapse imaging platform. The app runs on macOS/Windows/Linux, connects to a Raspberry Pi–based stage/camera controller over the local network, and guides users from preview to long-term acquisition.

## English

### Overview
OpenLapse Controller is the upper-computer interface for live-cell and embryo imaging inside standard incubators. It discovers Raspberry Pi devices on the LAN, provides a real-time preview, offers manual X/Y/Z control, and schedules time-lapse capture across multi-well plates.

### Features
- Auto discovery and connection to the Raspberry Pi controller (UDP broadcast + TCP control).
- Real-time camera preview (USB capture) with single-image capture.
- Manual stage control for X/Y/Z with adjustable speed/step and homing.
- Multi-well plate selector (6/12/24/96) with clickable wells and coordinated moves.
- Time-lapse scheduler with per-well cycling, progress display, and auto saving.
- Lighting control (RGB/W) with quick on/off and configuration updates.
- Fast/precise autofocus routines based on Laplacian sharpness.
- Heartbeat monitoring, logs, and connection status indicators.
- Customizable save paths and auto-created folders for captured frames.

### System Architecture (brief)
- Desktop UI (Python + CustomTkinter) orchestrates camera, motion, and scheduling.
- Network layer: UDP broadcast for device discovery; TCP for commands/ACK/heartbeat.
- Imaging: USB camera pipeline with MJPEG support and Laplacian-based focus metrics.
- Motion & wells: Well-to-stage mapping and async move + capture workflow.

### Requirements
- Python 3.9+
- Suggested packages: `customtkinter`, `opencv-python`, `Pillow`, `requests`, `numpy`, `scapy`, `tk` (comes with most Python builds), plus `hashlib`, `threading`, `json`, `time` from stdlib.
- Raspberry Pi running the OpenLapse firmware that emits broadcasts and accepts TCP commands.

### Installation
1) Create and activate a virtual environment (recommended).
2) Install dependencies:
```
pip install customtkinter opencv-python pillow requests numpy scapy
```
3) Ensure the Raspberry Pi and the desktop are on the same LAN. Allow UDP broadcast and TCP on the negotiated port.

### Usage
1) Start the Raspberry Pi controller.
2) Run the desktop app:
```
python app.py
```
3) In the sidebar, use **Auto Search** or enter the Pi IP, then **Connect**. Connection status and heartbeat will be shown.
4) Use **Start Preview** to open the camera stream; adjust lighting under **Preview**.
5) For manual moves, set speed/step sliders and use the X/Y/Z controls or **Home** buttons.
6) In **Well Capture**, pick a plate type, click wells to select, set interval/duration/name, then **Start** to launch the time-lapse. Progress updates at the bottom.
7) Use **Fast Focus** or **Precise Focus** to autofocus around the current Z position.
8) Captured images are stored under `./preview_imgs/<experiment>/<well>/timestamp.png` (created automatically).

### Screenshots (placeholders)
- Preview tab
- Well Capture tab
- Manual capture / lighting controls

### Developer Notes
- Entry point: [app.py](app.py). UI components live in `libs/` (camera, Pi connection, well selection, tools).
- Network: see [libs/raspi_con.py](libs/raspi_con.py) for UDP discovery and TCP client with ACK/heartbeat handling.
- Camera & focus: see [libs/cam.py](libs/cam.py) for USB capture, MJPEG viewer, Laplacian focus metric, and timed capture utility.
- Well selection: see [libs/well_select.py](libs/well_select.py) for plate layouts and well-to-stage coordinate mapping.
- Stage position widget (optional): [libs/manul_select.py](libs/manul_select.py).
- Images for plates reside in `plates/` (96/24/12/6 well backgrounds).
- Default save root is `./preview_imgs`; paths are created on demand.
- Logging and heartbeat handling are in `UI.update_data()` with 60 Hz refresh.

---

## 中文

### 概述
OpenLapse Controller 是一款用于标准培养箱内活细胞 / 胚胎长时程成像的上位机控制软件。它在局域网内自动发现树莓派控制器，提供实时预览、三轴手动控制，并可针对多孔板进行时间序列采集。

### 功能亮点
- UDP 广播自动发现 + TCP 控制，快速建立连接并显示心跳状态。
- USB 摄像头实时预览，支持单帧截图。
- X/Y/Z 手动运动控制，可调速度、步长，支持回零。
- 多孔板选择（6/12/24/96），点击孔位即可移动到对应坐标。
- 时间序列拍摄：设定间隔、总时长和实验名称，循环遍历孔位并显示进度。
- 光源控制：RGB/W 可配置，一键开灯/关灯。
- 快速 / 精细自动对焦，基于 Laplacian 清晰度指标。
- 日志输出、连接状态与超时提示，便于长期实验监控。
- 自动创建保存目录，按照实验名 / 孔位整理图片。

### 系统架构（简要）
- 桌面端 UI（Python + CustomTkinter）统筹相机、运动与调度。
- 网络层：UDP 广播用于发现设备，TCP 用于命令、ACK 与心跳。
- 成像层：USB 相机管线（支持 MJPEG），实时计算 Laplacian 清晰度。
- 运动与孔板：孔位到舞台坐标映射，异步移动与拍照流程。

### 环境依赖
- Python 3.9+
- 推荐依赖：`customtkinter`, `opencv-python`, `Pillow`, `requests`, `numpy`, `scapy`。
- 树莓派需运行 OpenLapse 固件，能发送广播并接受 TCP 命令。

### 安装步骤
1) 建议创建虚拟环境并激活。
2) 安装依赖：
```
pip install customtkinter opencv-python pillow requests numpy scapy
```
3) 确保树莓派与桌面端处于同一局域网，允许 UDP 广播和 TCP 通信。

### 使用方法
1) 先启动树莓派控制端。
2) 运行桌面软件：
```
python app.py
```
3) 在侧栏点击 **Auto Search** 自动获取 IP，或手动输入后点击 **Connect**，观察连接与心跳状态。
4) 点击 **Start Preview** 开启预览，底部可调光源参数。
5) 手动控制：调整速度 / 步长滑块，使用 X/Y/Z 方向键或 **Home** 回零。
6) 在 **Well Capture** 选择孔板类型并点击孔位，设定间隔、时长和实验名称，点击 **Start** 开始时间序列拍摄，进度条实时更新。
7) 使用 **Fast Focus** / **Precise Focus** 在当前 Z 附近自动对焦。
8) 图像默认保存到 `./preview_imgs/<实验名>/<孔位>/timestamp.png`，路径自动创建。

### 截图（占位）
- 预览页面
- 孔板拍摄页面
- 手动拍摄 / 光源控制

### 开发者提示
- 入口： [app.py](app.py)。UI 组件在 `libs/` 下（相机、网络、孔板、工具）。
- 网络：参见 [libs/raspi_con.py](libs/raspi_con.py)，包含 UDP 发现与 TCP ACK/心跳处理。
- 成像与对焦：参见 [libs/cam.py](libs/cam.py)，含 USB 采集、MJPEG 拉流、Laplacian 清晰度与定时拍摄工具。
- 孔板选择与坐标：见 [libs/well_select.py](libs/well_select.py)。
- 舞台位置标记组件： [libs/manul_select.py](libs/manul_select.py)。
- 孔板背景图位于 `plates/`，默认提供 96/24/12/6 孔板。
- 默认保存根目录 `./preview_imgs`，自动创建子目录。
- `UI.update_data()` 以 60 Hz 刷新日志、心跳与拍摄调度逻辑。
