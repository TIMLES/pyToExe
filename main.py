import os
import sys
import threading
from tkinter import messagebox, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import findPythonExe
from PIL import Image, ImageTk  # 需安装pillow库: pip install pillow
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import pyToEXE as pyE


dpi_value = 96  # Windows 默认DPI
if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        hdc = user32.GetDC(0)
        dpi_value = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        user32.ReleaseDC(0, hdc)
    except Exception:
        pass
# dpi_value 通常为 96/120/144/192/240/288
if dpi_value >= 240:  # 250%以上倍率-超高清4K小屏
    app_fontsize = 18
    win_geometry = "925x571"
elif dpi_value >= 192:  # 200%倍率-2K/4K高DPI
    app_fontsize = 15
    win_geometry = "740x457"
elif dpi_value >= 144:  # 150%倍率-FHD高DPI
    app_fontsize = 10
    win_geometry = "556x343"
elif dpi_value >= 120:  # 125%倍率-主流商务笔记本
    app_fontsize = 10
    win_geometry = "462x285"
else:  # 标准DPI 96
    app_fontsize = 10
    win_geometry = "370x228"
w, h = map(int, win_geometry.split("x"))
print(f"当前屏幕{w}X{h}")
vwin_geometry = f"{int(w / 1.5)}x{h // 3}"  # 子弹窗大小


tt = findPythonExe.Count_timeCost()
# 调用tt()查看与上次插入的时间
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES

    DNDOK = True
except ImportError:
    TkinterDnD = tb.Window
    DNDOK = False

class PackApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python代码打包工具")

        # 主题切换相关
        self.theme_names = list(tb.Style().theme_names())
        self.theme_var = tb.StringVar(value=tb.Style().theme_use())
        # 皮肤选择控件
        # 主题选择区放到Frame里，横向排列
        theme_frame = tb.Frame(self.root)
        theme_frame.pack(fill="x", padx=0, pady=(10, 0))
        self.always_on_top = tb.BooleanVar(value=False)
        chk_topmost = tb.Checkbutton(
            theme_frame,
            text="本窗口置顶",
            variable=self.always_on_top,
            command=lambda: self.root.wm_attributes(
                "-topmost", self.always_on_top.get()
            ),
            bootstyle="info-switch",
        )
        chk_topmost.pack(side=LEFT, padx=(10, 0))

        self.theme_combo = tb.Combobox(
            theme_frame,
            textvariable=self.theme_var,
            values=self.theme_names,
            width=16,
            state="readonly",
        )
        self.theme_combo.pack(side=RIGHT, padx=(4, 0))
        theme_label = tb.Label(theme_frame, text="主题：", bootstyle="info")
        theme_label.pack(side=RIGHT)
        self.theme_combo.bind("<<ComboboxSelected>>", self.change_theme)

        self.script_path = ""
        self.exe_name = ""
        self.icon_path = ""
        self.resource_path = ""
        self.dist_path = ""
        self.venvPython_exe = ""
        self.windowed = tb.BooleanVar(value=False) #是否开启命令行

        self.resource_into_exe= tb.BooleanVar(value=True) #是否资源内嵌exe
        self.widgets = []
        self.step1()

    def change_theme(self, event=None):
        new_theme = self.theme_var.get()
        tb.Style().theme_use(new_theme)

    def clear_widgets(self):
        for w in self.widgets:
            try:
                w.destroy()
            except:
                pass
        self.widgets.clear()

    # 第一步
    def step1(self):
        self.clear_widgets()
        fr = tb.Frame(self.root)
        fr.grid_propagate(False)
        fr.pack(pady=(16, 0), fill="both", expand=True, padx=8)
        self.widgets.append(fr)

        # 设定行权重，height比例大约4:1，也就是80%和20%
        fr.rowconfigure(0, weight=1)
        fr.rowconfigure(1, weight=0, minsize=int(h / 6.25))
        # 继续维持列均分
        for c in range(4):
            fr.columnconfigure(c, weight=1)

        self.lbl = tb.Label(
            fr,
            text="\t【1】拖入.py文件 或 点击...",
            bootstyle="info",
            anchor="w",
            relief="solid",
            borderwidth=2,
            cursor="hand2",
        )
        self.lbl.grid(
            row=0, column=0, columnspan=4, sticky="nsew", pady=(0, 10), padx=8
        )

        chk_windowed = tb.Checkbutton(
            fr,
            text="打包后cmd窗口",
            variable=self.windowed,
            bootstyle="success-round-toggle",
        )
        chk_windowed.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))

        chk_windowed = tb.Checkbutton(
            fr,
            text="资源内嵌",
            variable=self.resource_into_exe,
            bootstyle="success-round-toggle",
        )
        chk_windowed.grid(row=1, column=1, sticky="nsew", padx=(0, 10), pady=(0, 5))

        self.venvPython = tb.Button(
            fr,
            text="Python环境",
            command=lambda: self.choose_venvPython(),
            bootstyle="info-outline",
        )

        self.venvPython.grid(row=1, column=3, sticky="nsew", padx=(0, 0), pady=(0, 5))
        self.venvPython.grid_remove()  # 隐藏但记住布局参数，可之后还原

        # 绑定点击事件
        self.lbl.bind("<Button-1>", lambda e: self.choose_py())
        # 绑定拖拽
        if DNDOK:
            self.lbl.drop_target_register(DND_FILES)
            self.lbl.dnd_bind("<<Drop>>", lambda e: self.on_py_dropped(e))

        self.widgets += [self.lbl, chk_windowed, self.venvPython]

    def on_py_dropped(self, event):
        paths = self.root.tk.splitlist(event.data)
        if paths and paths[0].endswith(".py"):
            self.script_path = paths[0]

            self.exe_name = os.path.splitext(os.path.basename(paths[0]))[0]
            pythonLoad = findPythonExe.find_compatible_python(self.script_path)
            if pythonLoad is not None:
                self.venvPython_exe = pythonLoad
                self.step2()
            else:
                messagebox.showerror("错误", "未找到对应python解释器, 请手动选择！")
                self.lbl.config(text=f'已选择python文件:\n\t{self.script_path}\n\n\t请点击"python环境"选择解释器!')
                self.venvPython.grid()  # 恢复显示（如果用过 grid_remove()，布局参数会自动恢复；如果用过 grid_forget()，可能要加参数）
        else:
            messagebox.showerror("错误", "请拖入.py文件")

    def choose_py(self):
        f = filedialog.askopenfilename(
            title="请选择.py文件", filetypes=[("Python文件", "*.py")]
        )
        if f:
            self.script_path = f
            self.exe_name = os.path.splitext(os.path.basename(f))[0]
            pythonLoad = findPythonExe.find_compatible_python(self.script_path)
            if pythonLoad is not None:
                self.venvPython_exe = pythonLoad
                self.step2()
            else:
                messagebox.showerror("错误", "未找到对应python解释器, 请手动选择！")
                self.lbl.config(text=f'已选择python文件:\n\t{self.script_path}\n\n\t请点击"python环境"选择解释器!')
                self.venvPython.grid()

    def choose_venvPython(self):
        f = filedialog.askopenfilename(
            title="请选择所打包.py文件所属python环境",
            filetypes=[("Python解释器文件", "*.exe")],
        )
        if f:
            self.venvPython_exe = f
            missing = findPythonExe.check_imported_packages_in_target_python(
                self.script_path, self.venvPython_exe
            )
            if missing:
                messagebox.showerror(
                    "错误", f"以下包在目标解释器未安装:\n{', '.join(missing)}"
                )
            else:self.step2()


    # 第二步
    def step2(self):
        self.clear_widgets()
        fr = tb.Frame(self.root)
        fr.grid_propagate(False)
        fr.pack(pady=(16, 0), fill="both", expand=True, padx=8)
        self.widgets.append(fr)

        # 设定行权重，height比例大约4:1，也就是80%和20%
        fr.rowconfigure(0, weight=1)
        fr.rowconfigure(1, weight=0, minsize=int(h / 6.25))
        # 继续维持列均分
        for c in range(4):
            fr.columnconfigure(c, weight=1)
        
        self.lbl_icon = tb.Label(
            fr,
            text="\t【2】拖入.ico文件 或 点击...\t ",
            bootstyle="info",
            anchor="w",
            relief="solid",
            borderwidth=2,
            cursor="hand2",
        )
        self.lbl_icon.grid(
            row=0, column=0, columnspan=4, sticky="nsew", pady=(0, 20), padx=8
        )

        btn_resource_path = tb.Button(
            fr, text="资源", command=lambda: self.choose_resource(), bootstyle="success-outline"
        )
        btn_resource_path.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))

        en_name = tb.Entry(fr, bootstyle="primary")
        en_name.insert(0, "【exe名称】: " + self.exe_name)
        en_name.grid(
            row=1, column=1, columnspan=1, sticky="nsew", padx=(0, 20), pady=(0, 5)
        )

        btn_last = tb.Button(
            fr, text="上一步", command=lambda: self.step1(), bootstyle="success-outline"
        )
        btn_last.grid(row=1, column=2, sticky="nsew", padx=(0, 5), pady=(0, 5))

        btn_next = tb.Button(
            fr,
            text="下一步",
            command=lambda: (
                self.__setattr__(
                    "exe_name", en_name.get().removeprefix("【exe名称】: ").strip()
                ),
                self.__setattr__(
                    "icon_path",
                    (
                        os.path.abspath(pyE.get_resource_path("resource\默认图标.ico"))
                        if not self.icon_path
                        else self.icon_path
                    ),
                ),
                self.step3(),
            ),
            bootstyle="success-outline",
        )

        btn_next.grid(row=1, column=3, sticky="nsew", padx=(0, 5), pady=(0, 5))

        # 绑定点击事件
        self.lbl_icon.bind("<Button-1>", lambda e: self.choose_icon())

        if DNDOK:
            self.lbl_icon.drop_target_register(DND_FILES)
            self.lbl_icon.dnd_bind("<<Drop>>", lambda e: self.on_ico_dropped(e))
        self.widgets += [en_name, self.lbl_icon, btn_next]
        
        print(f"解释器路径：{self.venvPython_exe}")
    def on_ico_dropped(self, event):
        paths = self.root.tk.splitlist(event.data)
        if paths and (paths[0].endswith(".ico") or paths[0].endswith(".ICO")):
            self.icon_path = paths[0]
            aa = (
                f"【已选择图标文件】:\n"
                f"\t\t{self.icon_path or '默认'}\n"
                f"【已选择资源文件夹】:\n"
                f"\t{self.resource_path or '默认不选择'}\n"
            )

            self.lbl_icon.config(text=aa)

        else:
            messagebox.showerror("错误", "请拖入ico文件")

    def choose_icon(self):
        f = filedialog.askopenfilename(
            title="请选择ico文件", filetypes=[("ICO图标", "*.ico")]
        )
        if f:
            self.icon_path = f
            aa = (
                f"【已选择图标文件】:\n"
                f"\t\t{self.icon_path or '默认'}\n"
                f"【已选择资源文件夹】:\n"
                f"\t{self.resource_path or '默认不选择'}\n"
            )

            self.lbl_icon.config(text=aa)
    def choose_resource(self):
        f = filedialog.askdirectory(
            title="请选择资源文件夹"
        )
        if f:
            self.resource_path = f
            aa = (
                f"【已选择图标文件】:\n"
                f"\t\t{self.icon_path or '默认'}\n"
                f"【已选择资源文件夹】:\n"
                f"\t{self.resource_path or '默认不选择'}\n"
            )

            self.lbl_icon.config(text=aa)

    # 第三步
    def step3(self):
        self.clear_widgets()
        fr = tb.Frame(self.root)
        fr.grid_propagate(False)
        fr.pack(pady=(16, 0), fill="both", expand=True, padx=8)
        self.widgets.append(fr)
        # 设定行权重，height比例大约4:1，也就是80%和20%
        fr.rowconfigure(0, weight=1)
        fr.rowconfigure(1, weight=0, minsize=int(h / 6.25))
        # 继续维持列均分
        for c in range(4):
            fr.columnconfigure(c, weight=1)

        self.info = tb.Label(
            fr,
            anchor="w",
            bootstyle="info",
            borderwidth=2,  # 边框宽度（像素）
            relief="solid",  # 边框样式：flat / ridge / groove / solid / raised / sunken
        )
        self.info.grid(
            row=0, column=0, columnspan=4, sticky="nsew", pady=(0, 10), padx=8
        )


    # Treeview 日志，不显示标题
        self.log_text = ScrolledText(fr, wrap="word", height=15)
        self.log_text.grid(row=0, column=0, columnspan=4, sticky="nsew", pady=(0, 10), padx=8)
        self.log_text.grid_remove()   # ← 一创建即隐藏


        self.dist_path = os.path.join(os.getcwd(), "dist")
        self.info.config(text=self.Now_load_info())  # 更新

        btn_last = tb.Button(
            fr, text="上一步", command=lambda: self.step2(), bootstyle="success-outline"
        )
        btn_last.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))

        btn_dist = tb.Button(
            fr,
            text="文件夹",
            command=lambda: self.choose_dist(),
            bootstyle="info-outline",
        )
        btn_dist.grid(row=1, column=1, sticky="nsew", padx=(0, 5), pady=(0, 5))
        tt()
        # 步骤A: 加载图片并缩放
        img = Image.open(pyE.get_resource_path('resource\火箭 (1).png'))
        img = img.resize((20, 20), Image.LANCZOS)  # 你可以调整尺寸
        photo = ImageTk.PhotoImage(img)

        self.btn_build = tb.Button(
            fr,
            text="打包 GO! ",
            image=photo,          # 图片
            compound='right', 
            command=lambda: self.do_build(),
            bootstyle="primary-outline",
        )
        self.btn_build.image = photo  # 防止图像被垃圾回收

        tt()
        self.btn_build.grid(row=1, column=3, sticky="nsew", padx=(0, 5), pady=(0, 5))

        self.widgets += [self.info, btn_dist, btn_last, self.btn_build]

    def choose_dist(self):
        d = filedialog.askdirectory(title="选择EXE保存目录")
        if d:
            self.dist_path = d
            self.info.config(text=self.Now_load_info())  # 更新

    def Now_load_info(self):
        aaaa = (
            f"【名称】:   {os.path.basename(self.exe_name)}({os.path.basename(self.script_path)})\n"
            f"【图标】:   {os.path.basename(self.icon_path)}\n"
            f"【资源】:   {os.path.basename(self.resource_path) or '无'}\n"
            f"【输出至文件夹】:\n      {self.dist_path}\n"
            f"【解释器】:\n      " + self.venvPython_exe + "\n"
        )
        return aaaa

            
    def update_info_text(self, text):
        # 这里改成替换显示内容
        def _update():
            self.info.config(text=text)
        self.root.after(0, _update)

    def do_build(self):
        # self.root.update()
        self.log_text.grid();#self.log_scroll.grid();
        self.info.grid_remove()
        if not self.script_path or not os.path.isfile(self.script_path):
            messagebox.showerror("错误", "请选择有效的py文件")
            return
        if self.icon_path and (not os.path.isfile(self.icon_path)):
            messagebox.showerror("错误", "请选择有效的ico文件")

            return
        if self.dist_path and (not os.path.isdir(self.dist_path)):
            if self.dist_path != os.path.join(os.getcwd(), "dist"):
                messagebox.showerror("错误", self.dist_path)
                messagebox.showerror("错误", "请选择有效的输出目录")
                return
        if self.venvPython_exe and (not os.path.isfile(self.venvPython_exe)):
            messagebox.showerror("错误", self.venvPython_exe)
            messagebox.showerror("错误", "请选择正确的python解释器")
            return
        self.btn_build.config(state="disabled")

        def show_path_popup(parent, path):
            win = tb.Toplevel(parent)
            win.title("完成")
            win.geometry(vwin_geometry)
            win.update_idletasks()
            parent.update_idletasks()

            # 居中
            def center_child():
                if not win.winfo_exists():
                    return
                try:
                    pw, ph = parent.winfo_width(), parent.winfo_height()
                    px, py = parent.winfo_x(), parent.winfo_y()
                    ww, wh = win.winfo_width(), win.winfo_height()
                    x = px + (pw - ww) // 2
                    y = py + (ph - wh) // 2
                    win.geometry(f"{ww}x{wh}+{x}+{y}")
                except Exception:
                    pass   # 防止窗口已销毁时报错(保险)

            center_child()  # 初次居中

            # 使子窗口随主窗口移动/缩放时居中
            on_parent_move_id = parent.bind('<Configure>', lambda e: center_child(), add='+')

            # 控件布局
            self.root.wm_attributes("-topmost", False)
            win.wm_attributes("-topmost", True)
            win.rowconfigure(0, weight=1)
            win.rowconfigure(1, weight=1)
            for col in range(5):
                win.columnconfigure(col, weight=1)
            tb.Label(win, text="输出文件在：").grid(
                row=0, column=0, columnspan=4, sticky="nsew", pady=(0, 0)
            )
            entry = tb.Entry(win)
            entry.grid(row=1, column=0, sticky="ew", padx=(10, 5))
            entry.insert(0, path)
            entry.config(state="readonly")

            def close_and_unbind():
                try:
                    parent.unbind('<Configure>', on_parent_move_id)
                except Exception:
                    pass
                win.destroy()

            def copy_to_clipboard():
                win.clipboard_clear()
                win.clipboard_append(path)
                win.update()
                self.root.after(0, self.step1)
                close_and_unbind()

            copybu = tb.Button(
                win,
                text="返回",
                command=copy_to_clipboard,
                bootstyle="success",
                cursor="hand2",
            )
            copybu.grid(row=1, column=1, sticky="ew", columnspan=2, padx=(0, 5))
            entry.select_range(0, "end")
            entry.focus_set()
            win.transient(parent)
            win.grab_set()

            def on_close():
                win.wm_attributes("-topmost", False)
                self.root.wm_attributes("-topmost", self.always_on_top.get())
                close_and_unbind()
            win.protocol("WM_DELETE_WINDOW", on_close)
            # 不用win.mainloop()


        
        def add_log_line(line):
            self.root.after(0, lambda: (
                self.log_text.insert("end", line.strip() + "\n"),
                self.log_text.see("end")
            ))

        def run_build():
            try:
                print(".py路径:", self.script_path)
                print("当前路径:", sys.executable)
                print("解释器路径", self.venvPython_exe)
                print("图标路径:", self.icon_path)
                print("资源文件夹:", self.resource_path)
                print("输出目录:", self.dist_path)
                if 1:
                    local_package_dir = pyE.get_resource_path(findPythonExe.pyinstaller_choose(self.venvPython_exe))
                    findPythonExe.ensure_pyinstaller_installed(self.venvPython_exe, local_package_dir)
                    build_exe_subprocess=pyE.build_exe_subprocess_pyinstaller;
                else:
                    findPythonExe.ensure_nuitka_installed(self.venvPython_exe)
                    build_exe_subprocess=pyE.build_exe_subprocess_pyinstaller;
                returncode = build_exe_subprocess(
                    script_path=self.script_path,
                    exe_name=self.exe_name,
                    windowed=not self.windowed.get(),
                    resource_into_Exe=self.resource_into_exe.get(),
                    icon_path=self.icon_path or None,
                    dist_path=self.dist_path or None,
                    python_executable=self.venvPython_exe or None,
                    output_callback=add_log_line,
                    resource_dir=self.resource_path or None,
                )
                if returncode == 0:
                    path = self.dist_path or os.path.join(os.getcwd(), "dist")
                    self.root.after(0, show_path_popup, self.root, path)
                else:
                    self.root.after(
                        0, messagebox.showerror, "打包失败", "PyInstaller 执行失败"
                    )

            except Exception as e:
                self.root.after(0, messagebox.showerror, "打包失败", str(e))
            self.root.after(0, self.btn_build.config, {"state": "normal"})

        threading.Thread(target=run_build).start()


if __name__ == "__main__":
    if DNDOK:
        root = TkinterDnD.Tk()
        tb.Style("superhero")
    else:
        root = tb.Window(themename="superhero")
    root.resizable(False, False)
    # << 在实例化PackApp之前，把样式的字体全局改掉！！ >>
    tb.Style().configure(".", font=("微软雅黑", app_fontsize))

    app = PackApp(root)
    # app.step3()
    # << geometry 不在 __init__ 内写死，由这里统一设置 >>
    root.geometry(win_geometry)
    root.mainloop()
