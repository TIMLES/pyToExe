import ttkbootstrap as tb
from ttkbootstrap.constants import *

root = tb.Window(themename="superhero")
frame = tb.Frame(root)
frame.pack(fill="both", expand=True, padx=10, pady=10)

pad = {'padx': 8, 'pady': 6, 'sticky': "w"}
row = 0

chk1 = tb.Checkbutton(frame, text="Checkbutton 勾选框", bootstyle=WARNING)
chk1.grid(row=row, column=0, **pad)

selected_var = tb.IntVar()  # 变量，决定互斥哪一项是选中的
radio1 = tb.Radiobutton(frame, text="A", value=1, variable=selected_var)
radio2 = tb.Radiobutton(frame, text="B", value=2, variable=selected_var)
radio1.grid(row=row, column=1, **pad)
radio2.grid(row=row, column=2, **pad)
radio1.invoke()  # 默认勾选A

root.mainloop()