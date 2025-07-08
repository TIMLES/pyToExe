import ttkbootstrap as tb
import sys
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 2: Per-monitor-DPI-aware
    except Exception:
        pass
def get_window_dpi(hwnd):
    try:
        import ctypes
        user32 = ctypes.windll.user32
        dpi = user32.GetDpiForWindow(hwnd)
        return dpi
    except Exception:
        # 如果系统不支持, fallback:
        return get_monitor_dpi(hwnd)
def get_monitor_dpi(hwnd):
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        shcore = ctypes.windll.shcore
        MONITOR_DEFAULTTONEAREST = 2
        monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        dpiX = wintypes.UINT()
        dpiY = wintypes.UINT()
        shcore.GetDpiForMonitor(monitor, 2, ctypes.byref(dpiX), ctypes.byref(dpiY))
        return dpiX.value
    except Exception:
        return 96
class DynamicWindowSizeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("窗口测量")
        self.root.geometry("400x300")
        root.wm_attributes("-alpha", 0.7)
        tb.Style("superhero")
        self.dpi_label = tb.Label(
            root, 
            text="DPI：检测中",
            font=("微软雅黑", 13, "bold"),
            foreground="yellow",       # 只加了这行
        )
        self.dpi_label.pack(pady=15, padx=15)
        self.size_label = tb.Label(
            root, 
            text="当前窗口大小：400x300", 
            font=("微软雅黑", 13),
            foreground="cyan",         # 只加了这行
        )
        self.size_label.pack(pady=10)
        self.last_dpi = None
        self.last_size = None
        self._update_info()
    def _update_info(self):
        if sys.platform == "win32":
            hwnd = self.root.winfo_id()
            dpi = get_window_dpi(hwnd)
        else:
            dpi = int(self.root.winfo_fpixels('1i'))
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        if dpi != self.last_dpi:
            self.dpi_label.config(text=f"DPI：{dpi}")
            self.last_dpi = dpi
            
        if (width, height) != self.last_size:
            self.size_label.config(text=f"窗口：{width}x{height}")
            self.last_size = (width, height)
        self.root.after(200, self._update_info)
if __name__ == "__main__":
    root = tb.Window(themename="superhero")
    app = DynamicWindowSizeApp(root)
    root.mainloop()