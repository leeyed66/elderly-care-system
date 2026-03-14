"""
环境测试脚本
验证系统依赖是否正确安装
"""

import sys
import importlib

def check_python_version():
    print(f"Python版本: {sys.version}")
    if sys.version_info >= (3, 13):
        print("✅ Python版本符合要求 (>=3.13)")
        return True
    else:
        print("⚠️ 建议使用Python 3.13或更高版本")
        return True

def check_module(module_name, import_name=None):
    import_name = import_name or module_name
    try:
        importlib.import_module(import_name)
        print(f"✅ {module_name} 已安装")
        return True
    except ImportError:
        print(f"❌ {module_name} 未安装")
        return False

def check_cuda():
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✅ CUDA可用: {torch.cuda.get_device_name(0)}")
            return True
        else:
            print("ℹ️ CUDA不可用，将使用CPU推理")
            return True
    except ImportError:
        return False

def check_camera():
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                print("✅ 摄像头可用")
                return True
        print("⚠️ 摄像头不可用 (可能正在被占用)")
        return False
    except Exception as e:
        print(f"⚠️ 摄像头检测失败: {e}")
        return False

def check_yolo():
    try:
        from ultralytics import YOLO
        print("✅ Ultralytics YOLO 可正常导入")
        print("  正在下载/加载YOLOv8n模型...")
        model = YOLO('yolov8n.pt')
        print("✅ YOLO模型加载成功")
        return True
    except Exception as e:
        print(f"❌ YOLO加载失败: {e}")
        return False

def main():
    print("=" * 50)
    print("智能老人远程监护系统 - 环境检测")
    print("=" * 50)
    print()
    
    results = []
    
    print("【基础环境】")
    results.append(check_python_version())
    print()
    
    print("【核心依赖】")
    core_modules = [
        ('torch', 'torch'),
        ('torchvision', 'torchvision'),
        ('ultralytics', 'ultralytics'),
        ('OpenCV', 'cv2'),
        ('NumPy', 'numpy'),
        ('Pillow', 'PIL'),
        ('Flask', 'flask'),
        ('Flask-SocketIO', 'flask_socketio'),
        ('PyYAML', 'yaml'),
        ('colorlog', 'colorlog'),
    ]
    for name, import_name in core_modules:
        results.append(check_module(name, import_name))
    print()
    
    print("【可选依赖】")
    optional_modules = [
        ('MediaPipe (可选，支持 Python ≤ 3.12)', 'mediapipe'),
        ('SciPy', 'scipy'),
    ]
    for name, import_name in optional_modules:
        check_module(name, import_name)
    print()
    
    print("【MediaPipe 兼容性说明】")
    print("  ✅ 系统已完全兼容 YOLOv8-Pose，无需 MediaPipe 也能正常运行")
    print("  ℹ️  MediaPipe 目前不支持 Python 3.13+")
    print("  ℹ️  如果您使用 Python ≤ 3.12，可以安装 MediaPipe 作为补充")
    print()
    
    print("【高级检查】")
    results.append(check_cuda())
    check_camera()
    results.append(check_yolo())
    print()
    
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"检查结果: {passed}/{total} 项通过")
    
    if passed == total:
        print("✅ 环境检测全部通过，可以正常运行系统")
        print()
        print("启动命令: python main.py")
    else:
        print("⚠️ 部分检测未通过，请安装缺失的依赖:")
        print("  pip install -r requirements.txt")
    print("=" * 50)

if __name__ == "__main__":
    main()
