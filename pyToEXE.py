import os
import sys
import locale
import subprocess
import shutil
#访问目标资源，使得能在打包后还能获取
def get_resource_path(relpath):
    # relpath 例如: 'resource/xxx.png'
    if hasattr(sys, '_MEIPASS'):            #打包后exe
        return os.path.join(sys._MEIPASS, relpath)
    return os.path.join(os.path.dirname(__file__), relpath)   # 纯源码情况
#编码问题
def safe_decode(line_bytes):
    for enc in [locale.getpreferredencoding(False), 'utf-8', 'gbk']:
        try:
            return line_bytes.decode(enc)
        except Exception:
            continue
    return line_bytes.decode('utf-8', errors='replace')

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

    opts.append(script_path)
    if python_executable is None:
        python_executable = sys.executable
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
            bufsize=1,
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
    resource_into_Exe=False,  # 对应 onefile
    icon_path=None,
    dist_path=None,
    python_executable=None,
    output_callback=None,
    resource_dir=None,
):
    """
    仿pyinstaller接口，使用nuitka打包。参数定义一致，便于无缝切换。
    自动检测是否用到tkinter，并自动加--enable-plugin=tk-inter。
    """

    def _script_uses_tkinter(script_path):
        """静态扫描脚本代码是否用了tkinter"""
        try:
            with open(script_path, encoding="utf-8") as f:
                src = f.read()
            # 常见写法全部覆盖
            for pat in [
                "import tkinter", "from tkinter",    # py3标准
                "import Tkinter", "from Tkinter",    # py2标准
                "import ttk", "from ttk",            # ttk扩展
                "import tkinter.ttk", "from tkinter.ttk",
                "import ttkbootstrap", "from ttkbootstrap",
                "import tkmacosx", "from tkmacosx",
                "import tksheet", "from tksheet",
                "import tkintertable", "from tkintertable",
                "import tkcalendar", "from tkcalendar",
                "import customtkinter", "from customtkinter",
                "import tkPDFViewer", "from tkPDFViewer",
                "import tkhtmlview", "from tkhtmlview",
                "import tkinterDnD2", "from tkinterDnD2",
                "import tktimepicker", "from tktimepicker",
                "import tkmultientry", "from tkmultientry",
                "import tkpredictor", "from tkpredictor",
                "import easygui", "from easygui",               # easygui内部兜底用tk
                "import idlelib", "from idlelib",
                "import PySimpleGUI", "from PySimpleGUI",
                "import PySimpleGUI.PySimpleGUI", "from PySimpleGUI.PySimpleGUI",
                "import PySimpleGUI.PySimpleGUITk", "from PySimpleGUI.PySimpleGUITk",
                "import PySimpleGUI_tk", "from PySimpleGUI_tk",  # 旧版本
                "import pygubu", "from pygubu",
                "import tkmaterial", "from tkmaterial",
                "import ttkthemes", "from ttkthemes",
                # Pillow的ImageTk在tk下用
                "from PIL import ImageTk",
                "import PIL.ImageTk",
            ]:
                if pat in src:
                    return True
            return False
        except Exception as e:
            msg = f"检测tkinter时读取{script_path}失败: {e}"
            if output_callback:
                output_callback(msg + "\n")
            else:
                print(msg)
            return False

    opts = [
        "--follow-imports",
        "--assume-yes-for-downloads",
        "--remove-output",
    ]
    # 是否自动加tkinter插件
    if _script_uses_tkinter(script_path):
        opts.append("--enable-plugin=tk-inter")
        if output_callback:
            output_callback("检测到脚本用到tkinter，自动添加tk-inter插件参数。\n")
        else:
            print("检测到脚本用到tkinter，自动添加tk-inter插件参数。")

    # 窗口参数
    if windowed and os.name == 'nt':
        opts.append("--windows-disable-console") 
    # onefile
    if resource_into_Exe:
        opts.append("--onefile")
    else:
        opts.append("--standalone")
    # ICON
    if icon_path and os.name == 'nt':
        opts.append(f"--windows-icon-from-ico={icon_path}")
    # 资源
    if resource_dir is not None:
        resource_absdir = os.path.abspath(resource_dir)
        if os.path.exists(resource_absdir) and os.path.isdir(resource_absdir):
            resource_basename = os.path.basename(resource_absdir)
            opts.append(f'--include-data-dir={resource_absdir}={resource_basename}')
        else:
            msg = f"资源文件夹不存在: {resource_absdir}\n"
            if output_callback:
                output_callback(msg)
            else:
                print(msg, end="")
    # 输出目录
    if dist_path:
        opts.append(f"--output-dir={dist_path}")
    # exe名
    if exe_name and resource_into_Exe:
        opts.append(f"--output-filename={exe_name}")
    opts.append(script_path)
    # python
    if python_executable is None:
        python_executable = sys.executable
    cmd = [python_executable, "-m", "nuitka"] + opts
    print("Nuitka命令：", " ".join([str(x) for x in cmd])) 

    process = None
    returncode = -1
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=1,
        )
        for line_b in iter(process.stdout.readline, b''):
            line = safe_decode(line_b)
            if output_callback:
                output_callback(line)
            else:
                print(line, end="")
    except Exception as e:
        msg = f"Nuitka打包过程中发生错误: {e}\n"
        if output_callback:
            output_callback(msg)
        else:
            print(msg, end="")
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
    # build清理
    build_dir_candidates = ["build", "__nuitka_build"]
    for bdir in build_dir_candidates:
        build_dir = os.path.join(os.getcwd(), bdir)
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
    # nuitka无spec文件，但有 .dist-info，如果要也可清理
    for entry in os.listdir(os.getcwd()):
        if entry.endswith('.dist-info') and os.path.isdir(entry):
            try:
                shutil.rmtree(os.path.join(os.getcwd(), entry))
            except Exception:
                pass
    return returncode