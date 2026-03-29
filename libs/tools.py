from datetime import datetime
import os


class Tools:
    def get_img_pfrefix(self):
        """获取图片文件名前缀"""
        timestamp = datetime.now().strftime("%m%d_%H%M%S_%f")[:-3]  # 去掉最后3位，保留毫秒
        return f"{timestamp}"
    

    def get_save_path(self,save_path,sub_folder="not_defined",well_name='all',ext="png",make_dir=True):
        """获取保存图片的完整路径"""
        path = os.path.join(save_path, sub_folder, well_name)
        if make_dir and not os.path.exists(path):
            print(f"📁 创建目录: {path}")
            os.makedirs(path)
        file_name = self.get_img_pfrefix() + f".{ext}"
        path_name = os.path.join(path, file_name)
        return path_name



if __name__ == "__main__":
    # print(Tools().get_img_pfrefix())
    print(Tools().get_save_path("./captures","t124est",'H12',"jpg"))