import ast
import subprocess
import sys
import os
import platform
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
# 创建一个闭包函数，用于跟踪上次插入时间
def Count_timeCost():
    last_time = [None]
    counter = [0]

    def time_since_last():
        now = time.time()
        if last_time[0] is None:
            print(f"第 {counter[0]} 次：首次调用")
        else:
            delta = now - last_time[0]
            print(f"第 {counter[0]} 次：距上次 {delta:.4f} 秒")
        last_time[0] = now
        counter[0] += 1
    return time_since_last

def find_compatible_python(pyfile):
    """查找能够运行给定Python文件的所有依赖的Python解释器路径（优先当前解释器）"""

    def get_python_executables():
        """获取系统中所有可用的Python解释器路径（去重, 过滤WindowsApps伪python）"""
        paths = set()
        plat = platform.system()
        commands = []
        if plat == "Windows":
            commands.append("where python")
        else:
            commands.append("which -a python3")
            commands.append("which -a python")
        for cmd in commands:
            try:
                out = subprocess.check_output(
                    cmd, 
                    shell=True, 
                    encoding="gbk" if plat == "Windows" else "utf-8",
                    stderr=subprocess.DEVNULL
                )
                for line in out.splitlines():
                    if os.path.isfile(line.strip()):
                        paths.add(os.path.realpath(line.strip()))
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        # 添加常见路径...
        username = os.getlogin()
        common_paths = [
            r"C:\Python\python.exe",
            r"C:\Python3\python.exe",
            r"C:\ProgramData\Anaconda3\python.exe",
            r"C:\ProgramData\Miniconda3\python.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\python.exe"),
            os.path.expandvars(r"%APPDATA%\Python\python.exe"),
            f"C:\\Users\\{username}\\.conda\\envs\\venv\\python.exe",
            f"C:\\Users\\{username}\\Anaconda3\\python.exe",
            f"C:\\Users\\{username}\\Miniconda3\\python.exe",
            f"C:\\Users\\{username}\\.conda\\envs\\base\\python.exe",
            f"C:\\Users\\{username}\\.conda\\envs\\venv\\python.exe",
        ]
        for path in common_paths:
            if os.path.isfile(path):
                paths.add(os.path.realpath(path))
        # ------- 关键：过滤windowsapps伪python -------
        windowsapps_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps").lower()
        filtered_paths = []
        for exe in paths:
            exe_low = exe.lower()
            if exe_low.startswith(windowsapps_dir):
                continue  # 过滤掉伪壳
            if "windowsapps" in exe_low:
                continue
            if not os.path.isfile(exe):
                continue
            filtered_paths.append(exe)
        # 按时间排序
        return sorted(set(filtered_paths), key=lambda x: os.path.getmtime(x), reverse=True)

    # --- 主逻辑 ---
    if not os.path.isfile(pyfile):
        raise FileNotFoundError(f"文件不存在: {pyfile}")

    # 优先检查当前python解释器
    current_exe = os.path.realpath(sys.executable)
    name_now=os.path.basename(current_exe).lower()
    if "python" in name_now and name_now.endswith(".exe"):  #判断必须有python和exe字样
        missing_pkgs = check_imported_packages_in_target_python(pyfile, current_exe)
        if not missing_pkgs:
            return current_exe  # 当前环境最优

    # 其它解释器
    pyexes = get_python_executables()
    # 防止重复检测
    pyexes = [exe for exe in pyexes if os.path.realpath(exe) != current_exe]
    if not pyexes:
        return None

    # 使用线程池并行检查剩余解释器兼容性
    with ThreadPoolExecutor(max_workers=min(8, len(pyexes))) as executor:
        future_to_exe = {
            executor.submit(check_imported_packages_in_target_python, pyfile, exe): exe
            for exe in pyexes
        }
        for future in as_completed(future_to_exe):
            missing_pkgs = future.result()
            if not missing_pkgs:  # 如果没有缺失的包
                return future_to_exe[future]  # 返回第一个找到的兼容解释器  
    return None


def check_imported_packages_in_target_python(py_filepath, python_exe):
    """
    检查 py_filepath 所 import 的所有包（非标准库、非本地模块）在目标解释器 python_exe 下是否都已安装
    返回未安装的包名集合
    优化：多包一次性检测，极大提升效率
    """

    def get_imported_packages(py_filepath):
        """解析.py文件中的import包（返回顶层包名集合）"""
        with open(py_filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=py_filepath)
        pkg_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pkg_names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:  # 忽略相对import
                    pkg_names.add(node.module.split(".")[0])
        return pkg_names

    def get_stdlib_modules(python_exe):
        """
        获取目标解释器的标准库模块名集合
        """
        if not hasattr(get_stdlib_modules, 'cache'):
            get_stdlib_modules.cache = {}

        if python_exe not in get_stdlib_modules.cache:
            code = r"""
try:
    import sys
    if hasattr(sys, "stdlib_module_names"):
        print('\n'.join(sys.stdlib_module_names))
    else:
        import distutils.sysconfig as sysconfig, os
        stdlib_path = sysconfig.get_python_lib(standard_lib=True)
        mods = set()
        for fn in os.listdir(stdlib_path):
            if fn.endswith('.py') and fn != '__init__.py':
                mods.add(fn[:-3])
            elif os.path.isdir(os.path.join(stdlib_path, fn)):
                mods.add(fn)
        print('\n'.join(mods))
except Exception as e:
    import traceback
    print("ERROR:", traceback.format_exc())
            """
            result = subprocess.run(
                [python_exe, "-c", code], capture_output=True, text=True
            )
            if result.stderr:
                print(f"[get_stdlib_modules] stderr from '{python_exe}':\n{result.stderr}")
            if result.stdout.startswith("ERROR:"):
                raise RuntimeError(
                    f"[get_stdlib_modules] 调用目标解释器时出错:\n{result.stdout}"
                )
            get_stdlib_modules.cache[python_exe] = set(
                line.strip() for line in result.stdout.splitlines() if line.strip()
            )
        return get_stdlib_modules.cache[python_exe]

    def get_local_modules(py_filepath):
        """
        获取与.py文件同目录下的所有.py模块名，和所有子目录（即本地包），
        适配无__init__.py的新风格（PEP 420）。
        """
        dirname = os.path.dirname(os.path.abspath(py_filepath)) or os.getcwd()
        mod_names = set()
        for fn in os.listdir(dirname):
            full = os.path.join(dirname, fn)
            if fn.endswith(".py") and fn != os.path.basename(py_filepath):
                mod_names.add(os.path.splitext(fn)[0])
            elif os.path.isdir(full):  # 只要是目录即可视为本地包
                mod_names.add(fn)
        return mod_names

    # --- 主逻辑 ---
    stdlib = get_stdlib_modules(python_exe)
    localmods = get_local_modules(py_filepath)
    imported = get_imported_packages(py_filepath)
    to_check = imported - stdlib - localmods

    if not to_check:
        return set()

    # ---- 优化：一次性检测所有包 ----
    pkgs_arg = repr(list(to_check))
    code = (
        "import importlib.util\n"
        f"pkgs = {pkgs_arg}\n"
        "missing = [p for p in pkgs if importlib.util.find_spec(p) is None]\n"
        "print('\\n'.join(missing))"
    )
    result = subprocess.run([python_exe, "-c", code],
                            capture_output=True, text=True)
    if result.returncode != 0:
        # debug 输出
        print("[DEBUG] 子进程异常！")
        print("python_exe:", python_exe)
        print("code:\n", code)
        print("stdout:\n", result.stdout)
        print("stderr:\n", result.stderr)
        print("returncode:", result.returncode)
        raise RuntimeError(f"Error in checking packages: {result.stderr}")
    missing = set(line.strip() for line in result.stdout.splitlines() if line.strip())
    return missing



def has_pyinstaller(python_exe):
    """
    检查指定解释器中 PyInstaller 是否已安装
    """
    try:
        result = subprocess.run(
            [python_exe, "-c", "import PyInstaller"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False

    

def ensure_pyinstaller_installed(python_exe, local_package_dir):
    """
    检查指定解释器中 PyInstaller 是否已安装，
    未安装时从本地包目录安装（自动安装依赖）。
    :param python_exe:      目标虚拟环境的 python 解释器路径
    :param local_package_dir: 存放 PyInstaller 及其依赖的本地包目录
    """
    if has_pyinstaller(python_exe):
        print(f"PyInstaller 已在环境 {python_exe} 中安装，跳过安装。")
        return True
    print(f"环境 {python_exe} 未安装 PyInstaller，开始准备本地安装...")

    # 确认本地目录下存在 PyInstaller 安装包
    files = os.listdir(local_package_dir)
    if not any(f.lower().startswith("pyinstaller") and
               (f.endswith('.whl') or f.endswith('.tar.gz')) for f in files):
        print(f"在 {local_package_dir} 未找到 PyInstaller 安装包！")
        return False

    try:
        subprocess.check_call([
            python_exe, '-m', 'pip', 'install', 'pyinstaller',
            '--no-index',
            '--find-links', local_package_dir
        ])
        print(f"已用本地包目录 {local_package_dir} 安装 PyInstaller 到 {python_exe}！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"本地安装 PyInstaller 失败: {e}")
        return False

def download_pyinstaller_and_deps(download_dir, version=None):
    """
    从PyPI联网下载特定版本或最新版PyInstaller及其依赖到指定目录。
    """
    import os, sys, subprocess
    os.makedirs(download_dir, exist_ok=True)
    if version:
        pkg_spec = f"PyInstaller=={version}"
    else:
        pkg_spec = "PyInstaller"
    subprocess.check_call([
        sys.executable, "-m", "pip", "download", pkg_spec, "-d", download_dir
    ])
    print(f"PyInstaller {version or '最新'} 及其依赖已下载到 {download_dir}")


def get_python_version(python_exe_path):
    try:
        result = subprocess.run(
            [python_exe_path, '-V'],
            capture_output=True,
            text=True
        )
        output = result.stdout.strip() or result.stderr.strip()
        m = re.search(r'Python\s+(\d+)\.(\d+)', output)
        if m:
            return int(m.group(1)), int(m.group(2))
        raise RuntimeError(f"无法解析版本信息: {output}")
    except Exception as e:
        return f"发生错误: {e}"


def pyinstaller_choose(python_exe):#选择pyinstaller版本
    version_tuple=get_python_version(python_exe)
    if (2, 7) <= version_tuple <= (3, 5):
        return r'resource\PyInstaller3_6_bag'
    elif (3, 6) <= version_tuple <= (3, 8):
        return r'resource\PyInstaller5_13_bag'
    elif version_tuple >= (3, 9):
        return r'resource\PyInstaller_last_bag'
    else:
        raise ValueError(f"不支持的Python版本: {version_tuple}")
    

if __name__ == "__main__":
    # 输出当前解释器
    print("当前Python解释器：", sys.executable)

    # # ==== 下载依赖包用（联网环境下使用）====
    # # 下载PyInstaller 3.6及其依赖，对应Python2.7/3.3-3.5
    # download_pyinstaller_and_deps(r'resource\PyInstaller3_6_bag', version="3.6")
    # # 下载PyInstaller 5.13.0及其依赖，对应Python3.6-3.8
    # download_pyinstaller_and_deps(r'resource\PyInstaller5_13_bag', version="5.13.0")
    # # 下载PyInstaller 最新及其依赖，对应Python3.8+
    download_pyinstaller_and_deps(r'resource\PyInstaller_last_bag')

    # ==== 检查并本地安装PyInstaller用（目标环境） ====
    python_exe = r'G:\VScode\VScode\.conda\python.exe'           # 你的目标 Python 路径
    # local_package_dir = r'resource\PyInstaller513_bag'               # 离线whl包存放路径
    # ensure_pyinstaller_installed(python_exe, local_package_dir)
    print(pyinstaller_choose(python_exe))
    aa=time.time()
    # local_package_dir = r'resource\PyInstaller513_bag'
    # if not is_python_ge37(python_exe ):
    #     local_package_dir = r'resource\PyInstaller3_bag' 
    # ensure_pyinstaller_installed(python_exe ,local_package_dir)
    print(f"运行时间：{1000*(time.time()-aa):.0f}ms")
  
# aa=time.time()
# # ######## 示例用法 ########
# if __name__ == "__main__":
#     pyfile = r"窗口获取.py"  # 这里写你自己的 .py 路径
#     interpreter = find_compatible_python(pyfile)
#     print(interpreter)
#     print(f"运行时间：{1000*(time.time()-aa):.0f}ms")