import ttkbootstrap as tb
import tkinter as tk

# 常见英文字体（手写/花体风格），不一定每台电脑都支持
fonts = [
    "Brush Script MT",
    "Comic Sans MS",
    "Segoe Script",
    "Lucida Handwriting",
    "Edwardian Script ITC",
    "Freestyle Script",
    "Vladimir Script",
    "Monotype Corsiva",
    "Segoe Print",
    "Arial Rounded MT Bold",
]

try:
    root = tb.Window(themename='litera')
except Exception:
    # 如果ttkbootstrap不可用就退回标准tkinter
    root = tk.Tk()

label_title = tk.Label(root, text="花体英文字体展示", font=("Arial", 20, "bold"))
label_title.pack(pady=(10,10))

sample_text = "Ray"

for fname in fonts:
    try:
        lbl = tk.Label(root,
            text=f"{fname}:  {sample_text}",
            font=(fname, 28),
            pady=5)
        lbl.pack()
    except Exception as e:
        print(f"字体 {fname} 不支持: {e}")

root.mainloop()