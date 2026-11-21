import os
import sys  

import time
import locale

# PyInstaller 运行环境资源路径修正,但只限于读取
def get_resource_path(relpath):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relpath)
    return os.path.join(os.path.dirname(__file__), relpath)


#编码问题:安全编码为字符串
def safe_decode(line_bytes):
    for enc in [locale.getpreferredencoding(False), 'utf-8', 'gbk']:
        try:
            return line_bytes.decode(enc)
        except Exception:
            continue
    return line_bytes.decode('utf-8', errors='replace')

# 
def make_timer():
    last_time = None
    count = -1

    def tt(msg=""):
        nonlocal last_time, count
        now = time.time()
        count += 1
        if last_time is None:
            msg_time=f"第{count}次调用（{msg}）：首次调用，无上次时间参考。"
            print(msg_time)
        else:
            elapsed = (now - last_time) * 1000  # 转为毫秒
            if msg:
                msg_time=f"第{count}次调用（{msg}）：用时 {elapsed:.2f} ms"
                print(msg_time)
            else:
                msg_time=f"第{count}次调用：用时 {elapsed:.2f} ms"
                print(msg_time)
        last_time = now
        return msg_time

    return tt

# 居中窗口
def center_window(win, width=None, height=None):
    win.update_idletasks()
    w = width or win.winfo_width()
    h = height or win.winfo_height()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 3
    win.geometry(f"{w}x{h}+{x}+{y}")