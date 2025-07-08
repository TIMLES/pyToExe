import PyInstaller.__main__
import os
import shutil

def build_exe(script_path, exe_name="program", windowed=False, icon_path=None, dist_path=None):
    opts = [
        f'--name={exe_name}',
        '--onefile',
    ]
    if windowed:
        opts.append('--windowed')
    if icon_path:
        opts.append(f'--icon={icon_path}')
    if dist_path:
        opts.append(f'--distpath={dist_path}')
    opts.append(script_path)
    
    PyInstaller.__main__.run(opts)
    
    # 删除 build 文件夹
    build_dir = os.path.join(os.getcwd(), "build")
    if os.path.exists(build_dir):
        try:
            shutil.rmtree(build_dir)
            print(f"已删除 build 文件夹：{build_dir}")
        except Exception as e:
            print(f"删除 build 文件夹失败: {e}")
    else:
        print(f"未找到 build 文件夹：{build_dir}")
    
    # 删除 .spec 文件
    spec_file = os.path.join(os.getcwd(), f"{exe_name}.spec")
    if os.path.exists(spec_file):
        try:
            os.remove(spec_file)
            print(f"已删除 spec 文件: {spec_file}")
        except Exception as e:
            print(f"删除 spec 文件失败: {e}")

if __name__ == '__main__':
    script_path = r'test.py'
    exe_name = 'test'
    icon_path = r'图标.ico'
    dist_path = r'D:\打卡后端'

    build_exe(
        script_path=script_path,
        exe_name=exe_name,
        windowed=False ,
        icon_path=icon_path,
        dist_path=dist_path
    )

    print(f"打包完成，exe在文件夹：{dist_path}")