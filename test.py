import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.tooltip import ToolTip  # 放在 import 部分
root = tb.Window(themename="cosmo")
root.title("ttkbootstrap 所有控件展示 (v1.14.0)")

# ---------------- 主题切换控件 -------------------
themenames = list(root.style.theme_names())

def change_theme(event):
    style = theme_combo.get()
    root.style.theme_use(style)

theme_frame = tb.Frame(root)
theme_label = tb.Label(theme_frame, text="请选择主题：")
theme_combo = tb.Combobox(theme_frame, values=themenames, width=18)
theme_combo.set(root.style.theme.name)
theme_combo.bind("<<ComboboxSelected>>", change_theme)
theme_label.pack(side="left", padx=(0, 4))
theme_combo.pack(side="left")
theme_frame.pack(fill="x", padx=10, pady=10)

# ---------------- 所有控件展示 --------------------
notebook = tb.Notebook(root)
notebook.pack(fill="both", expand=True, padx=10, pady=10)

# ------- 基本控件页 -------
frame1 = tb.Frame(notebook)
notebook.add(frame1, text="基础控件")

pad = {'padx': 8, 'pady': 6, 'sticky': "w"}
row = 0

tb.Label(frame1, text="Label 标签").grid(row=row, column=0, **pad)
entry = tb.Entry(frame1)
entry.insert(0, "Entry 单行输入框")
entry.grid(row=row, column=1, **pad)

row += 1
btn1 = tb.Button(frame1, text="主按钮", bootstyle=PRIMARY)
btn2 = tb.Button(frame1, text="成功按钮", bootstyle=SUCCESS)
btn1.grid(row=row, column=0, **pad)
btn2.grid(row=row, column=1, **pad)

row += 1
chk1 = tb.Checkbutton(frame1, text="Checkbutton 勾选框", bootstyle=WARNING)
chk1.grid(row=row, column=0, **pad)
radio1 = tb.Radiobutton(frame1, text="A", value=1)
radio2 = tb.Radiobutton(frame1, text="B", value=2)
radio1.grid(row=row, column=1, **pad)
radio2.grid(row=row, column=2, **pad)
radio1.invoke()

row += 1
combo = tb.Combobox(frame1, values=["选项A", "选项B", "选项C"], width=14)
combo.current(0)
combo.grid(row=row, column=0, **pad)
spin = tb.Spinbox(frame1, from_=0, to=10, width=12)
spin.grid(row=row, column=1, **pad)

row += 1
menubtn = tb.Menubutton(frame1, text="下拉菜单按钮")
menu = tb.Menu(menubtn)
for i in range(3):
    menu.add_command(label=f"菜单项{i+1}")
menubtn["menu"] = menu
menubtn.grid(row=row, column=0, **pad)

row += 1
txt = tb.Text(frame1, height=3, width=28)
txt.insert("end", "这是多行文本框。\n支持换行。")
txt.grid(row=row, column=0, columnspan=3, padx=8, pady=6, sticky="ew")

# --------- 特色控件页 ----------
frame2 = tb.Frame(notebook)
notebook.add(frame2, text="特色控件")

row = 0
# 进度条
pbar = tb.Progressbar(frame2, value=55, bootstyle=INFO, length=210)
pbar.grid(row=row, column=0, **pad)

row += 1
# 仪表盘
meter = tb.Meter(frame2, amountused=65, subtext="仪表 Meter", bootstyle=SUCCESS, metertype='full')
meter.grid(row=row, column=0, **pad)

row += 1
# Floodgauge 进度条 (bar风格必须常用几种，不要-xxx)
flood = tb.Floodgauge(frame2, value=45, maximum=100, bootstyle="danger", text="Floodgauge 控件")
flood.grid(row=row, column=0, **pad)

row += 1
# DateEntry 日期选择 (需 python-dateutil + tzlocal)
try:
    date_entry = tb.DateEntry(frame2)
except Exception:
    date_entry = tb.Label(frame2, text="未安装dateutil或tzlocal, DateEntry不可用")
date_entry.grid(row=row, column=0, **pad)

row += 1
# MessageBox 测试
toolbtn = tb.Button(
    frame2, text="点击弹出消息对话框", command=lambda: Messagebox.info("你好！", "ttkbootstrap 的 Messagebox"))
toolbtn.grid(row=row, column=0, **pad)

row += 1
# ToolTip 测试
tooltip_btn = tb.Button(frame2, text="鼠标悬停显示提示")
tooltip_btn.grid(row=row, column=0, **pad)
ToolTip(tooltip_btn, text="这是 ToolTip 气泡提示")

# --------- Treeview表格页 ----------
frame3 = tb.Frame(notebook)
notebook.add(frame3, text="表格/列表")

tree = tb.Treeview(frame3, columns=("姓名", "分数"), show="headings", height=5)
tree.heading("姓名", text="姓名")
tree.heading("分数", text="分数")
for n, s in [("张三",80),("李四",90),("王五",88),("赵六",95)]:
    tree.insert("", "end", values=(n, s))
tree.pack(fill="x", padx=12, pady=12)

root.mainloop()