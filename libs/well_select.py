from PIL import Image, ImageTk
import customtkinter as ctk

class WellPlateViewer(ctk.CTkFrame):
    """
    自动孔距 96孔板显示器
    只需设置第一个孔(A1)和最后一个孔(H12)的坐标
    自动计算孔距与中间孔位
    """

    def __init__(self, master,
                 well_plate_type="96",
                 hole_diameter=20,
                 debug_mode=False,
                 **kwargs):
        super().__init__(master, **kwargs)

        # 预设孔板信息
        self.well_info_dict = {
            '96': {'rows': 8, 'cols': 12, 'top_left': (52, 50), 'bottom_right': (548, 335), 'hole_diameter': 35, 'clip_range': 5, 'image_path': "./plates/96well.png"},
            '24': {'rows': 4, 'cols': 6, 'top_left': (80, 73), 'bottom_right': (520, 312), 'hole_diameter': 56, 'clip_range': 5, 'image_path': "./plates/24well.png"},
            '12': {'rows': 3, 'cols': 4, 'top_left': (124, 88), 'bottom_right': (475, 298), 'hole_diameter':90, 'clip_range': 5, 'image_path': "./plates/12well.png"},
            '6': {'rows': 2, 'cols': 3, 'top_left': (123, 108), 'bottom_right': (477, 268), 'hole_diameter': 138, 'clip_range': 5, 'image_path': "./plates/6well.png"},
        }
        self.well_plate_type = well_plate_type

        # 孔板类型
        try:
            rows = self.well_info_dict[well_plate_type]['rows']
            cols = self.well_info_dict[well_plate_type]['cols']
            first_hole = self.well_info_dict[well_plate_type]['top_left']
            last_hole = self.well_info_dict[well_plate_type]['bottom_right']
            hole_diameter = self.well_info_dict[well_plate_type]['hole_diameter']
            clip_range = self.well_info_dict[well_plate_type]['clip_range']
            image_path = self.well_info_dict[well_plate_type]['image_path']
        except:
            raise ValueError(f"Unsupported well plate type: {well_plate_type}. Supported types: {list(self.well_info_dict.keys())}")



        self.rows = rows
        self.cols = cols
        self.first_hole = first_hole
        self.last_hole = last_hole
        self.hole_diameter = hole_diameter
        self.hole_diameter_clip = hole_diameter + clip_range  # 点击时的容差范围
        self.debug_mode = debug_mode
        self.selected = set()


        # 加载背景图
        self.bg_image = Image.open(image_path).convert("RGBA")
        self.tk_image = ImageTk.PhotoImage(self.bg_image)
        self.width, self.height = self.bg_image.size

        # 画布
        self.canvas = ctk.CTkCanvas(self, width=self.width, height=self.height, highlightthickness=0)
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")

        # 计算所有孔的坐标
        self.calculate_positions()
        self.draw_debug_overlay()
        self.draw_well_labels()

        # 鼠标交互
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_hover)
        self.hovered_well = None

    # -----------------------------
    def calculate_positions(self):
        """根据A1和H12自动计算孔坐标"""
        x1, y1 = self.first_hole
        x2, y2 = self.last_hole

        # 横向孔距、纵向孔距
        dx = (x2 - x1) / (self.cols - 1)
        dy = (y2 - y1) / (self.rows - 1)

        self.well_positions = []
        for r in range(self.rows):
            for c in range(self.cols):
                x = x1 + c * dx
                y = y1 + r * dy
                self.well_positions.append((x, y))

    # -----------------------------
    def on_click(self, event):
        """点击选中/取消选中孔"""
        for i, (x, y) in enumerate(self.well_positions):
            dx = event.x - x
            dy = event.y - y
            if dx**2 + dy**2 <= (self.hole_diameter_clip / 2)**2:
                row = i // self.cols
                col = i % self.cols
                well = f"{chr(65+row)}{col+1}"
                if well in self.selected:
                    self.selected.remove(well)
                else:
                    self.selected.add(well)
                self.redraw_overlay()
                break


    def on_hover(self, event):
        """鼠标悬浮高亮孔"""
        nearest_well = None
        for i, (x, y) in enumerate(self.well_positions):
            dx, dy = event.x - x, event.y - y
            if dx**2 + dy**2 <= (self.hole_diameter_clip / 2)**2:
                row = i // self.cols
                col = i % self.cols
                nearest_well = f"{chr(65 + row)}{col + 1}"
                break

        if nearest_well != self.hovered_well:
            self.hovered_well = nearest_well
            self.redraw_overlay()

    def redraw_overlay(self):
        """刷新选中孔显示"""
        self.canvas.delete("overlay")

        for well in list(self.selected):  # 用list复制以防删除时迭代出错
            r = ord(well[0]) - 65
            c = int(well[1:]) - 1
            index = r * self.cols + c
            # ✅ 防越界
            if index < 0 or index >= len(self.well_positions):
                continue  # 或者 self.selected.remove(well)
            x, y = self.well_positions[index]
            d = self.hole_diameter
            self.canvas.create_oval(
                x - d/2, y - d/2, x + d/2, y + d/2,
                outline="#0081D1", fill="#0081D1", width=3, tags="overlay"
            )
            self.canvas.create_text(x, y, text=well, fill="white", font=("Arial", 8), tags="overlay")

        # 悬浮高亮圈
        if self.hovered_well:
            r = ord(self.hovered_well[0]) - 65
            c = int(self.hovered_well[1:]) - 1
            index = r * self.cols + c
            if 0 <= index < len(self.well_positions):
                x, y = self.well_positions[index]
                d = self.hole_diameter
                self.canvas.create_oval(
                    x - d/2, y - d/2, x + d/2, y + d/2,
                    outline="#44A5FF", width=5, tags="overlay"
                )


    # 显示所有孔的编号
    def draw_well_labels(self):
        for i, (x, y) in enumerate(self.well_positions):
            row = i // self.cols
            col = i % self.cols
            well = f"{chr(65+row)}{col+1}"
            self.canvas.create_text(x, y, text=well, fill="black", font=("Arial", 8), tags="label")

    def draw_debug_overlay(self):
        """显示调试辅助：孔位+编号"""
        if not self.debug_mode:
            return

        self.canvas.delete("debug")

        if self.debug_mode:
            # 显示角孔标记
            x1, y1 = self.first_hole
            x2, y2 = self.last_hole
            self.canvas.create_oval(x1-6, y1-6, x1+6, y1+6, fill="red", tags="debug")
            self.canvas.create_text(x1, y1-10, text="A1", fill="red", font=("Arial", 8), tags="debug")

            self.canvas.create_oval(x2-6, y2-6, x2+6, y2+6, fill="cyan", tags="debug")
            self.canvas.create_text(x2, y2-10, text="H12", fill="red", font=("Arial", 8), tags="debug")

    def get_selected(self):
        # 先按字母排序，再按数字排序
        return self.well_plate_type, sorted(list(self.selected), key=lambda x: (x[0], int(x[1:])))

    def refresh_layout(self, first_hole=None, last_hole=None, hole_diameter=None):
        """实时刷新坐标"""
        if first_hole: self.first_hole = first_hole
        if last_hole: self.last_hole = last_hole
        if hole_diameter: self.hole_diameter = hole_diameter
        self.calculate_positions()
        self.draw_debug_overlay()
        self.redraw_overlay()

    # 更改孔板类型
    def change_well_plate_type(self, well_plate_type):
        self.selected.clear()  # 清空已选孔

        try:
            rows = self.well_info_dict[well_plate_type]['rows']
            cols = self.well_info_dict[well_plate_type]['cols']
            first_hole = self.well_info_dict[well_plate_type]['top_left']
            last_hole = self.well_info_dict[well_plate_type]['bottom_right']
            hole_diameter = self.well_info_dict[well_plate_type]['hole_diameter']
            clip_range = self.well_info_dict[well_plate_type]['clip_range']
            image_path = self.well_info_dict[well_plate_type]['image_path']
        except:
            raise ValueError(f"Unsupported well plate type: {well_plate_type}. Supported types: {list(self.well_info_dict.keys())}")

        self.rows = rows
        self.cols = cols
        self.first_hole = first_hole
        self.last_hole = last_hole
        self.hole_diameter = hole_diameter
        self.hole_diameter_clip = hole_diameter + clip_range  # 点击时的容差范围

        # 重新加载背景图
        self.bg_image = Image.open(image_path).convert("RGBA")
        self.tk_image = ImageTk.PhotoImage(self.bg_image)
        self.width, self.height = self.bg_image.size
        self.canvas.config(width=self.width, height=self.height)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")

        # 重新计算孔位
        self.calculate_positions()
        self.draw_debug_overlay()
        self.draw_well_labels()
        self.redraw_overlay()
        self.selected.clear()  # 清空已选孔

        self.well_plate_type = well_plate_type

    # 清空已选孔
    def clear_selection(self):
        self.selected.clear()
        self.redraw_overlay()


class WellPosition:
    def __init__(self, start=(19150, 3300), end=(97550, 53350),
                 rows='ABCDEFGH', cols=range(1, 13)):
        """
        生成 96 孔板孔号与坐标映射。
        参数：
            start: A1 的坐标 (x, y)
            end: H12 的坐标 (x, y)
            rows: 行名，默认 A-H
            cols: 列号，默认 1-12
        """
        self.start = start
        self.end = end
        self.rows = rows
        self.cols = cols
        self.mapping = self._generate_mapping()

    def _generate_mapping(self):
        x1, y1 = self.start
        x2, y2 = self.end
        n_rows = len(self.rows)
        n_cols = len(self.cols)

        # 每个方向的步距
        dx = (x2 - x1) / (n_cols - 1)
        dy = (y2 - y1) / (n_rows - 1)

        mapping = {}
        for i, row in enumerate(self.rows):
            for j, col in enumerate(self.cols):
                x = int(round(x1 + j * dx))
                y = int(round(y1 + i * dy))
                well = f"{row}{col}"
                mapping[well] = (x, y)
        return mapping

    def get_xy(self, well):
        """返回某个孔号的 (x, y) 坐标"""
        return self.mapping.get(well)

    def show_table(self):
        """以表格形式打印坐标"""
        for row in self.rows:
            row_data = [f"{row}{col}:{self.mapping[f'{row}{col}']}" for col in self.cols]
            print("\t".join(row_data))


# plate = WellPosition()
# print(plate.get_xy("A1"))   # (19150, 3300)
# print(plate.get_xy("H12"))  # (97550, 53350)
# plate.show_table()