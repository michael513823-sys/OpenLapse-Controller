import customtkinter as ctk
import random

class StagePositionViewer(ctk.CTkFrame):
    """
    镜头位置显示与拍摄点标记控件
    ✅ 外部通过 update_position(x, y) 更新镜头位置
    ✅ 点击“Mark”添加当前位置为拍摄点
    ✅ 右键单击删除单个拍摄点
    """

    def __init__(self, master, canvas_width=400, canvas_height=300, init_pos=(200, 150), **kwargs):
        super().__init__(master, **kwargs)

        # 参数
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.current_pos = list(init_pos)
        self.max_marks = 10
        self.marked_points = []

        # 创建画布
        self.canvas = ctk.CTkCanvas(
            self, width=self.canvas_width, height=self.canvas_height,
            bg="white", highlightthickness=1, highlightbackground="#999"
        )
        self.canvas.pack()

        # 绘制初始背景
        self.draw_background()
        self.draw_current_position()

        # 右键删除事件
        self.canvas.bind("<Button-3>", self.on_right_click)

    # ------------------- 绘图 -------------------
    def draw_background(self):
        """绘制网格背景"""
        self.canvas.delete("grid")
        step = 50
        for x in range(0, self.canvas_width, step):
            self.canvas.create_line(x, 0, x, self.canvas_height, fill="#E0E0E0", tags="grid")
        for y in range(0, self.canvas_height, step):
            self.canvas.create_line(0, y, self.canvas_width, y, fill="#E0E0E0", tags="grid")

    def draw_current_position(self):
        """绘制当前镜头位置"""
        self.canvas.delete("position")
        x, y = self.current_pos
        self.canvas.create_line(x - 10, y, x + 10, y, fill="red", width=2, tags="position")
        self.canvas.create_line(x, y - 10, x, y + 10, fill="red", width=2, tags="position")
        self.canvas.create_text(x + 20, y - 10, text=f"({x:.0f},{y:.0f})", fill="black", font=("Arial", 9), tags="position")

    def draw_marks(self):
        """绘制所有标记点"""
        self.canvas.delete("mark")
        for i, (x, y) in enumerate(self.marked_points):
            self.canvas.create_oval(x-5, y-5, x+5, y+5, fill="#0081D1", outline="", tags="mark")
            self.canvas.create_text(x, y-10, text=str(i+1), fill="#0081D1", font=("Arial", 8, "bold"), tags="mark")

    # ------------------- 功能 -------------------
    def mark_position(self):
        """将当前镜头位置标记为拍摄点"""
        if len(self.marked_points) >= self.max_marks:
            print("⚠️ 已达到10个拍摄点上限！")
            return
        self.marked_points.append(tuple(self.current_pos))
        self.draw_marks()

    def clear_marks(self):
        """清空所有标记"""
        self.marked_points.clear()
        self.canvas.delete("mark")

    def on_right_click(self, event):
        """右键单击删除单个拍摄点"""
        if not self.marked_points:
            return
        for i, (x, y) in enumerate(self.marked_points):
            dx, dy = event.x - x, event.y - y
            if dx**2 + dy**2 <= 6**2:  # 6 像素删除范围
                removed = self.marked_points.pop(i)
                print(f"🗑 删除拍摄点 {removed}")
                self.draw_marks()
                break

    # ------------------- 外部控制接口 -------------------
    def update_position(self, x, y):
        """外部调用：更新镜头位置显示"""
        self.current_pos = [x, y]
        self.draw_current_position()

    def random_move(self):
        """随机测试接口"""
        x = random.randint(20, self.canvas_width - 20)
        y = random.randint(20, self.canvas_height - 20)
        self.update_position(x, y)

    def get_marked_positions(self):
        """返回所有标记点"""
        return self.marked_points
