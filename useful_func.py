import os
import sys  

import ast
import time
import locale

# PyInstaller 运行环境资源路径修正,但只限于读取
def get_resource_path(relpath):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relpath)
    return os.path.join(os.path.dirname(__file__), relpath)


# 扫描时跳过的目录（虚拟环境、缓存、构建产物）
_SCAN_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", ".env", "virtualenv",
    "__pycache__", "node_modules", "site-packages", "dist-packages",
    "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".idea", ".vscode",
}


def _is_skipped_path(path, root):
    """路径中是否含有应该跳过的目录名（只看 root 以下部分）"""
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        return True
    parts = rel.split(os.sep)
    return any(p in _SCAN_SKIP_DIRS or p.startswith(".") for p in parts[:-1])


def _resolve_module_paths(base_dir, module_name):
    """
    把模块名按 base_dir 解析成实际 .py / __init__.py 路径。
    例：base=G:/Proj, "pkg.sub" -> [G:/Proj/pkg/__init__.py, G:/Proj/pkg/sub.py]
    模棱两可时返回空列表（非本地模块）。
    """
    if not module_name:
        init = os.path.join(base_dir, "__init__.py")
        return [init] if os.path.isfile(init) else []

    found = []
    cur = base_dir
    parts = module_name.split(".")
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        as_mod = os.path.join(cur, part + ".py")
        as_pkg = os.path.join(cur, part)
        if os.path.isfile(as_mod):
            found.append(as_mod)
            return found if is_last else []
        init = os.path.join(as_pkg, "__init__.py")
        if os.path.isdir(as_pkg):
            if os.path.isfile(init):
                found.append(init)
            cur = as_pkg
            continue
        return []
    return found


def collect_py_sources(script_path, max_files=300, max_bytes=200_000):
    """
    从入口脚本出发，沿 import 关系递归收集“真正被引用到”的本地 .py 文件。

    为什么不用整目录遍历：一个项目里可能有很多互不相关的脚本（服务端、工具脚本、
    另一个 GUI），全扫进去会让 tkinter 检测和依赖检测误判。
    这里只跑传递闭包：入口 -> 它 import 的本地模块 -> 那些模块 import 的本地模块...

    能识别：
    - 绝对 import（import pkg.mod / from pkg.mod import x），在入口脚本所在目录
      及其向上到最外层包的各级目录下解析
    - 相对 import（from .x import y / from .. import z / from . import k），
      按当前文件所在包目录逐级回退解析

    返回：绝对路径列表，第一个元素恒为入口脚本本身；不包含任何第三方包/标准库。
    """
    script_path = os.path.abspath(script_path)
    root = os.path.dirname(script_path)

    # 解析绝对 import 的搜索基目录：入口所在目录，入口在包内时再加上各级父目录
    bases = [root]
    cur = root
    while os.path.isfile(os.path.join(cur, "__init__.py")):
        parent = os.path.dirname(cur)
        if parent == cur or parent in bases:
            break
        bases.append(parent)
        cur = parent

    visited = [script_path]
    seen = {script_path}
    queue = [script_path]

    def enqueue(path, base_for_skip):
        if not path:
            return
        path = os.path.abspath(path)
        if path in seen or not path.endswith(".py"):
            return
        if not os.path.isfile(path) or _is_skipped_path(path, base_for_skip):
            return
        try:
            if os.path.getsize(path) > max_bytes:
                return
        except OSError:
            return
        seen.add(path)
        visited.append(path)
        queue.append(path)

    while queue and len(visited) < max_files:
        path = queue.pop(0)
        pkg_dir = os.path.dirname(path)  # 当前文件所属包目录
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                tree = ast.parse(f.read(), filename=path)
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for base in bases:
                        for cand in _resolve_module_paths(base, alias.name):
                            enqueue(cand, base)

            elif isinstance(node, ast.ImportFrom):
                if node.level:  # 相对 import：按当前包目录回退
                    base = pkg_dir
                    for _ in range(node.level - 1):
                        base = os.path.dirname(base)
                    for cand in _resolve_module_paths(base, node.module):
                        enqueue(cand, root)
                    if not node.module:  # from . import x -> 兄弟模块
                        for alias in node.names:
                            for cand in _resolve_module_paths(base, alias.name):
                                enqueue(cand, root)
                elif node.module:
                    for base in bases:
                        for cand in _resolve_module_paths(base, node.module):
                            enqueue(cand, base)

    return visited


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