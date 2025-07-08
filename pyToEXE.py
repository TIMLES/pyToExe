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

def build_exe_subprocess(
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

