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
    """优先本目录虚拟环境，再检查系统其他python，返回可运行pyfile的python解释器路径"""
    def check_imported_packages(pyfile, python_exe):
        # 检查pyfile import的包是否都在python_exe里已安装
        import ast
        with open(pyfile, encoding="utf-8") as f:
            root = ast.parse(f.read(), pyfile)
        modules = set()
        for node in ast.walk(root):
            if isinstance(node, ast.Import):
                modules.update(n.name.split('.')[0] for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split('.')[0])
        # 跳过内置
        stdlib = set(sys.builtin_module_names)
        for m in modules:
            if m in stdlib or m == '__future__': continue
            code = (
                f"import importlib.util; "
                f"print(1 if importlib.util.find_spec('{m}') is None else 0)"
            )
            try:
                out = subprocess.check_output([python_exe, "-c", code], stderr=subprocess.DEVNULL)
                if out.strip() == b'1':
                    return m  # 缺失直接返回模块名（有缺就算不兼容）
            except Exception:
                return m
        return None  # 全都装了

    # 1. 优先本地虚拟环境
    base = os.path.dirname(os.path.abspath(pyfile))
    venvs = ['venv', '.venv', '.env', 'env']
    for v in venvs:
        pyexe = os.path.join(base, v, 'Scripts' if os.name=='nt' else 'bin', 'python.exe' if os.name=='nt' else 'python')
        if os.path.isfile(pyexe):
            if not check_imported_packages(pyfile, pyexe):
                return pyexe

    # 2. 当前python
    cur_exe = sys.executable
    if not check_imported_packages(pyfile, cur_exe):
        return cur_exe

    # 3. 系统其余python（where/which）
    plat = platform.system()
    paths = set()
    cmds = ["where python"] if plat=="Windows" else ["which -a python3", "which -a python"]
    for cmd in cmds:
        try:
            out = subprocess.check_output(cmd, shell=True, encoding="utf-8", stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                p = os.path.realpath(line.strip())
                if os.path.isfile(p): paths.add(p)
        except Exception:
            continue

    paths.discard(os.path.realpath(cur_exe))

    # 并行检查其他python
    with ThreadPoolExecutor(max_workers=8) as pool:
        futu = {pool.submit(check_imported_packages, pyfile, exe): exe for exe in paths}
        for f in as_completed(futu):
            if not f.result():
                return futu[f]
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

    # 检查/安装 pip
    def ensure_pip_installed(python_exe):
        try:
            subprocess.check_call([python_exe, '-m', 'pip', '--version'],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            print(f"环境 {python_exe} 未检测到 pip，正在尝试自动安装 pip ...")
            try:
                subprocess.check_call([python_exe, '-m', 'ensurepip'])
                print("pip 安装成功。")
                return True
            except subprocess.CalledProcessError as e:
                print(f"自动安装 pip 失败: {e}")
                return False
        except Exception as e:
            print(f"检测 pip 失败: {e}")
            return False

    # 先保证 pip 可用
    if not ensure_pip_installed(python_exe):
        print(f"环境 {python_exe} 无法使用 pip，无法继续安装 PyInstaller。")
        return False

    # 检查 PyInstaller
    def has_pyinstaller(python_exe):
        try:
            subprocess.check_call([
                python_exe, '-c', 'import PyInstaller'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False

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

def ensure_nuitka_installed(python_exe):
    """
    检查指定解释器中 Nuitka 是否已安装，若未安装则确保 pip 可用并联网安装 Nuitka。
    :param python_exe: 目标虚拟环境的 python 解释器路径
    :return: True 表示 Nuitka 已安装或安装成功，False 表示无法安装
    """

    def ensure_pip_installed(python_exe):
        try:
            subprocess.check_call(
                [python_exe, '-m', 'pip', '--version'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except subprocess.CalledProcessError:
            print(f"环境 {python_exe} 未检测到 pip，正在尝试自动安装 pip ...")
            try:
                subprocess.check_call([python_exe, '-m', 'ensurepip'])
                print("pip 安装成功。")
                return True
            except subprocess.CalledProcessError as e:
                print(f"自动安装 pip 失败: {e}")
                return False
        except Exception as e:
            print(f"检测 pip 失败: {e}")
            return False

    def has_nuitka(python_exe):
        try:
            subprocess.check_call(
                [python_exe, "-c", "import nuitka"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except subprocess.CalledProcessError:
            return False

    # 步骤1：确保 pip 可用
    if not ensure_pip_installed(python_exe):
        print(f"环境 {python_exe} 无法使用 pip，无法继续安装 Nuitka。")
        return False

    # 步骤2：判断nuitka是否已安装
    if has_nuitka(python_exe):
        print(f"Nuitka 已在环境 {python_exe} 中安装，跳过安装。")
        return True

    print(f"环境 {python_exe} 未安装 Nuitka，尝试使用 pip 在线安装 ...")
    try:
        subprocess.check_call([python_exe, "-m", "pip", "install", "nuitka"])
        print("Nuitka 安装成功！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"在线安装 Nuitka 失败: {e}")
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
    #download_pyinstaller_and_deps(r'resource\PyInstaller_last_bag')

    # ==== 检查并本地安装PyInstaller用（目标环境） ====
    python_exe = r'G:\VScode\VScode\test\.venv\Scripts\python.exe'           # 你的目标 Python 路径
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