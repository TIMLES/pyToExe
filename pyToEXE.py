import os
import sys
import subprocess
import shutil
import ast
#打包函数

from useful_func import get_resource_path, safe_decode, collect_py_sources

# 判定“用到了 tk / tkinter”的模式（含 tk 生态的扩展包）
_TK_PATTERNS = [
    "import tkinter", "from tkinter",
    "import Tkinter", "from Tkinter",
    "import ttk", "from ttk",
    "import tkinter.ttk", "from tkinter.ttk",
    "from PIL import ImageTk", "import PIL.ImageTk",
]
# ttkbootstrap 需要额外收集主题数据
_TTKBOOTSTRAP_PATTERNS = [
    "import ttkbootstrap", "from ttkbootstrap",
]


def _script_uses_tkinter(script_path):
    """
    静态扫描入口脚本及其本地包内所有 .py，判断是否用到 tkinter / ttkbootstrap。
    入口脚本通常只是转发（如 `from mypkg.app import main`），
    真正的 GUI 代码在本地包里，所以必须递归扫描。

    返回："ttkbootstrap" / "tkinter" / None
    """
    found_tk = False
    for path in collect_py_sources(script_path):
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                src = f.read()
        except Exception:
            continue
        if any(pat in src for pat in _TTKBOOTSTRAP_PATTERNS):
            return "ttkbootstrap"
        if not found_tk and any(pat in src for pat in _TK_PATTERNS):
            found_tk = True
    return "tkinter" if found_tk else None

def build_exe_subprocess_pyinstaller(
    script_path,
    exe_name="program",
    windowed=False,
    resource_into_Exe=False,
    icon_path=None,
    dist_path=None,
    python_executable=None,  # 新增参数
    output_callback=None,
    resource_dir=None,  # 新增参数：资源包文件夹名或相对路径
    ):
    
        
    def _find_tcl_tk_data(python_exe):
        # 查找 tcl、tk DLL 及 tcl 目录，适配常规 Python 安装/虚拟环境
        base = os.path.dirname(os.path.dirname(python_exe))
        tcl_dir = ""
        if os.path.isdir(os.path.join(base, "tcl")):
            tcl_dir = os.path.join(base, "tcl")
        elif os.path.isdir(os.path.join(base, "Lib", "tcl")):
            tcl_dir = os.path.join(base, "Lib", "tcl")
        else:
            tcl_dir = ""
        dll_dir = os.path.join(base, "DLLs")
        dlls = []
        if os.path.isdir(dll_dir):
            for f in os.listdir(dll_dir):
                if f.lower().startswith(("tk", "tcl")) and f.lower().endswith(".dll"):
                    dlls.append(os.path.join(dll_dir, f))
        return tcl_dir, dlls       

    
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW
    opts = [
        "--name",
        exe_name,
        "--noconfirm",
        "--clean",
    ]
    if resource_into_Exe:  # 你想要资源打进exe就加--onefile
        opts.append("--onefile")
    if windowed:
        opts.append("--windowed")
    if icon_path:
        opts.extend(["--icon", icon_path])
    if dist_path:
        opts.extend(["--distpath", dist_path])

    # -------- 新增资源包自动加入 --------
    if resource_dir is not None:
        # 支持绝对/相对路径
        resource_absdir = os.path.abspath(resource_dir)
        if os.path.exists(resource_absdir) and os.path.isdir(resource_absdir):
            sep = ';' if os.name == 'nt' else ':'
            # 只用目录basename作为目标名
            resource_basename = os.path.basename(resource_absdir)
            opts.append(f"--add-data={resource_absdir}{sep}{resource_basename}")
        else:
            print(f"资源文件夹不存在: {resource_absdir}")
            if output_callback:
                output_callback(f"资源文件夹不存在: {resource_absdir}\n")
    # ----------------------------------
        #自动识别Tk/ttk缺少的文件并加入
    if _script_uses_tkinter(script_path):
        python_exe = python_executable
        tcl_dir, dlls = _find_tcl_tk_data(python_exe)
        sep = ';' if os.name == 'nt' else ':'
        if tcl_dir:
            opts.append(f"--add-data={tcl_dir}{sep}tcl")
        for dll in dlls:
            opts.append(f"--add-binary={dll}{sep}.")
        if output_callback:
            output_callback("检测到脚本用到tkinter/ttk，已自动添加tcl目录及DLL依赖。\n")
  # ----------------------------------

    opts.append(script_path)
    cmd = [python_executable, "-m", "PyInstaller"] + opts
    process = None
    returncode = -1
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,   # 注意: 不自动解码
            # encoding=locale.getpreferredencoding(False),
            bufsize=-1,
            creationflags=flags     # 这里加上
        )
        for line_b in iter(process.stdout.readline, b''):
            line = safe_decode(line_b)
            if output_callback:
                output_callback(line)
            else:
                print(line, end="")
    except Exception as e:
        print(f"打包过程中发生错误: {e}")
        if output_callback:
            output_callback(f"打包过程中发生错误: {e}\n")
    finally:
        if process is not None:
            try:
                if process.stdout:
                    process.stdout.close()
            except Exception:
                pass
            try:
                process.wait()
            except Exception:
                pass
            returncode = process.returncode
    # 清理
    build_dir = os.path.join(os.getcwd(), "build")
    if os.path.exists(build_dir):
        try:
            shutil.rmtree(build_dir)
            msg = f"已删除 build 文件夹：{build_dir}\n"
            if output_callback:
                output_callback(msg)
            else:
                print(msg, end="")
        except Exception as e:
            msg = f"删除 build 文件夹失败: {e}\n"
            if output_callback:
                output_callback(msg)
            else:
                print(msg, end="")
    spec_file = os.path.join(os.getcwd(), f"{exe_name}.spec")
    if os.path.exists(spec_file):
        try:
            os.remove(spec_file)
            msg = f"已删除 spec 文件: {spec_file}\n"
            if output_callback:
                output_callback(msg)
            else:
                print(msg, end="")
        except Exception as e:
            msg = f"删除 spec 文件失败: {e}\n"
            if output_callback:
                output_callback(msg)
            else:
                print(msg, end="")
    return returncode


def build_exe_subprocess_nuitka(
    script_path,
    exe_name="program",
    windowed=False,
    resource_into_Exe=False,
    icon_path=None,
    dist_path=None,
    python_executable=None,
    output_callback=None,
    resource_dir=None,
    ):


    # 1. 确定 Python 路径
    python_exe = python_executable
    
    # 2. 基础参数
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    opts = [
        "--remove-output",           # 编译完成后自动清理 build 文件夹
    ]

    # 3. tkinter / ttkbootstrap 插件
    tk_usage = _script_uses_tkinter(script_path)
    if tk_usage in ("tkinter", "ttkbootstrap"):
        opts.append("--enable-plugin=tk-inter")
    if tk_usage == "ttkbootstrap":
        opts.append("--include-package=ttkbootstrap")

    # 4. 模式设置 (Standalone vs Onefile)
    if resource_into_Exe:
        opts.append("--onefile")
    else:
        opts.append("--standalone")

    # 5. 窗口与图标
    if windowed and sys.platform == "win32":
        opts.append("--windows-console-mode=disable")
    
    if icon_path and sys.platform == "win32":
        # 注意：Nuitka 支持直接传入路径
        opts.append(f"--windows-icon-from-ico={icon_path}")

    # 6. 资源文件夹 (Data Files)
    if resource_dir:
        res_abs = os.path.abspath(resource_dir)
        if os.path.exists(res_abs):
            res_base = os.path.basename(res_abs)
            # 格式：--include-data-dir=来源=去向
            opts.append(f"--include-data-dir={res_abs}={res_base}")

    # 7. 输出路径与文件名
    if dist_path:
        opts.append(f"--output-dir={dist_path}")
    
    if exe_name:
        # 修正：Nuitka 指定输出名通常需要加 .exe 后缀（Windows）
        actual_exe_name = exe_name if exe_name.endswith(".exe") else f"{exe_name}.exe"
        opts.append(f"--output-filename={actual_exe_name}")

    # 8. 构建最终命令
    # 建议先尝试 python -m nuitka，这是最兼容的
    cmd = [python_exe, "-m", "nuitka"] + opts + [script_path]
    
    if output_callback:
        output_callback(f"执行命令: {' '.join(cmd)}\n")

    # 9. 执行过程 (保持你原来的 Popen 逻辑)
    process = None
    returncode = -1
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=-1,
            creationflags=flags
        )
        
        for line_b in iter(process.stdout.readline, b''):
            # 假设你定义了 safe_decode
            line = safe_decode(line_b)
            if output_callback:
                output_callback(line)
            else:
                print(line, end="")
                
        process.wait()
        returncode = process.returncode
    except Exception as e:
        if output_callback:
            output_callback(f"Nuitka 运行异常: {e}\n")
    
    return returncode


