import ast
import subprocess
import sys
import os
import platform
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import json

#python虚拟环境与包判断

from useful_func import get_resource_path, collect_py_sources

#是否为有用的python路径
def is_valid_python_exe(p):
    if not os.path.isfile(p):
        return False
    try:
        result = subprocess.run([p, "-V"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = (result.stdout or result.stderr).decode("utf-8", errors="ignore")
        return "Python" in out
    except Exception:
        return False



pyToEXE_config_path = os.path.expanduser("~/.pyToEXE_pythonPaths.json")

def load_python_paths(config_path=pyToEXE_config_path):
    """从配置文件读取 Python 路径列表"""
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("python_exes", [])
        except Exception:
            return []
    else:
        return []

def update_python_paths(new_path,config_path=pyToEXE_config_path):
    """把新解释器路径插入到配置最上方（避免重复）"""
    paths = load_python_paths()
    new_path = os.path.realpath(new_path)
    if new_path in paths:
        paths.remove(new_path)
    paths.insert(0, new_path)
    """写回配置文件"""
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"python_exes": paths}, f, ensure_ascii=False, indent=2)
        print(f"保存配置文件成功")
    except Exception as e:
        print(f"保存配置文件失败: {e}")

def find_compatible_python(pyfile):
    """
    从配置文件中逐一并行检查 Python 可执行路径，
    返回第一个兼容的路径字符串，找不到则返回 None。
    """
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    python_paths = load_python_paths()

    # 过滤掉不存在的路径
    valid_paths = [p for p in python_paths if os.path.isfile(p)]
    if not valid_paths:
        return None
    # ① 先单独检查第一个（优先）
    first = valid_paths[0]
    if not check_imported_packages_in_target_python(pyfile, first):
        return first

    # ② 再并行检查剩余的
    rest = valid_paths[1:]
    if not rest:
        return None

    # 并行检查兼容性
    with ThreadPoolExecutor(max_workers=min(8, len(rest))) as pool:
        futures = {pool.submit(check_imported_packages_in_target_python, pyfile, exe): exe for exe in rest}
        for f in as_completed(futures):
            if not f.result():
                return futures[f]

    return None


    
#检查目标路径是否包含所有包
def check_imported_packages_in_target_python(py_filepath, python_exe):
    """
    检查 py_filepath 及其本地包所 import 的所有包（非标准库、非本地模块）
    在目标解释器 python_exe 下是否都已安装
    返回未安装的包名集合
    优化：多包一次性检测，极大提升效率
    """
    flags = 0
    if sys.platform == "win32":  #是否为windows平台
        flags = subprocess.CREATE_NO_WINDOW

    def get_imported_packages(py_filepaths):
        """解析一组 .py 文件中的 import 包（返回顶层包名集合，忽略相对 import）"""
        pkg_names = set()
        for py_filepath in py_filepaths:
            try:
                with open(py_filepath, "r", encoding="utf-8", errors="ignore") as f:
                    tree = ast.parse(f.read(), filename=py_filepath)
            except (SyntaxError, OSError):
                continue
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
                [python_exe, "-c", code], capture_output=True, text=True,
                    creationflags=flags
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
        若入口脚本本身就在包里（同目录有 __init__.py），把包名链也算作本地。
        """
        dirname = os.path.dirname(os.path.abspath(py_filepath)) or os.getcwd()
        mod_names = set()
        for fn in os.listdir(dirname):
            full = os.path.join(dirname, fn)
            if fn.endswith(".py") and fn != os.path.basename(py_filepath):
                mod_names.add(os.path.splitext(fn)[0])
            elif os.path.isdir(full):  # 只要是目录即可视为本地包
                mod_names.add(fn)
        # 入口脚本位于包内部时（如 mypkg/app.py），把 mypkg 及其父包名也视为本地
        cur = dirname
        while os.path.isfile(os.path.join(cur, "__init__.py")):
            mod_names.add(os.path.basename(cur))
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        return mod_names

    # --- 主逻辑 ---
    stdlib = get_stdlib_modules(python_exe)
    localmods = get_local_modules(py_filepath)
    # 入口脚本 + 本地包内所有 .py 一起扫，避免入口只是转发时漏检
    imported = get_imported_packages(collect_py_sources(py_filepath))
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
                            capture_output=True, text=True,
                    creationflags=flags)
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


    

def ensure_pyinstaller_installed(python_exe):
    """
    检查指定解释器中 PyInstaller 是否已安装，
    未安装时通过 'uv' 快速在线安装。
    """
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW

    # 检查是否已安装 PyInstaller
    def has_pyinstaller(python_exe):
        try:
            subprocess.check_call([
                python_exe, '-c', 'import PyInstaller'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags)
            return True
        except subprocess.CalledProcessError:
            return False

    if has_pyinstaller(python_exe):
        print(f"PyInstaller 已在环境 {python_exe} 中安装，跳过安装。")
        return True
    print(f"环境 {python_exe} 未安装 PyInstaller，改用 uv 快速安装...")
    try:
        # 使用 uv 安装 PyInstaller （相当于更快的 pip install pyinstaller）
        subprocess.check_call([
            "uv", 'pip', 'install', 
            '--upgrade', 'pyinstaller', 
            '--python', python_exe  # 关键：通过 --python 指定你的虚拟环境路径
        ], creationflags=flags)

        print(f"已通过 uv 安装 PyInstaller 到 {python_exe}！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"使用 uv 安装 PyInstaller 失败: {e}")
        return False

def ensure_nuitka_installed(python_exe):
    """
    使用 uv 确保指定解释器中 Nuitka 已安装。
    若已安装则直接返回 True；
    若未安装则判断 uv 是否可用并尝试安装。
    :param python_exe: 目标虚拟环境的 python 可执行文件路径
    :return: True 表示 Nuitka 已安装或安装成功，False 表示无法安装
    """
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW

    def has_nuitka(python_exe):
        """判断 nuitka 是否已安装"""
        try:
            subprocess.check_call(
                [python_exe, "-c", "import nuitka"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags
            )
            return True
        except subprocess.CalledProcessError:
            return False
        except Exception as e:
            print(f"检测 Nuitka 失败: {e}")
            return False

    def has_uv(python_exe):
        """判断 uv 是否可用"""
        try:
            subprocess.check_call(
                [python_exe, "-m", "uv", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags
            )
            return True
        except subprocess.CalledProcessError:
            return False
        except Exception as e:
            print(f"检测 uv 失败: {e}")
            return False

    # 先检测是否已有 Nuitka
    if has_nuitka(python_exe):
        print(f"Nuitka 已在环境 {python_exe} 中安装，跳过安装。")
        return True


    # 使用 uv 安装 Nuitka
    print(f"环境 {python_exe} 未安装 Nuitka，尝试使用 uv 安装 ...")
    try:
        subprocess.check_call([
            "uv", "pip", "install", "nuitka", "--python", python_exe
        ], creationflags=flags)
        print("Nuitka 安装成功！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"使用 uv 安装 Nuitka 失败: {e}")
        return False




if __name__ == "__main__":
    # 输出当前解释器
    print("当前Python解释器：", sys.executable)