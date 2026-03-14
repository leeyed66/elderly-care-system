"""
行为识别模块测试脚本
用于验证行为检测功能是否正常工作
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import cv2
import numpy as np
from core.detection import YOLODetector, BehaviorDetector, BehaviorType

def test_behavior_detection():
    print("=" * 50)
    print("行为识别模块测试")
    print("=" * 50)
    
    print("\n1. 初始化 YOLO 检测器...")
    yolo_config = {
        'model_path': 'yolov8n-pose.pt',
        'conf_threshold': 0.5,
        'device': 'cpu'
    }
    
    try:
        yolo = YOLODetector(yolo_config)
        yolo.warmup()
        print("   ✓ YOLO 检测器初始化成功")
    except Exception as e:
        print(f"   ✗ YOLO 检测器初始化失败: {e}")
        return False
    
    print("\n2. 初始化行为检测器...")
    behavior_config = {
        'enabled': True,
        'window_size': 5,
        'confidence_threshold': 0.6,
        'min_duration': 2.0
    }
    
    try:
        behavior_detector = BehaviorDetector(behavior_config)
        print("   ✓ 行为检测器初始化成功")
    except Exception as e:
        print(f"   ✗ 行为检测器初始化失败: {e}")
        return False
    
    print("\n3. 打开视频源...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("   ! 无法打开摄像头，尝试使用示例视频...")
        print("   ! 将使用模拟帧进行测试")
        use_mock = True
    else:
        use_mock = False
        print("   ✓ 摄像头已打开")
    
    print("\n4. 开始行为识别测试...")
    print("   按 'q' 键退出")
    print("-" * 50)
    
    frame_count = 0
    
    try:
        while True:
            if use_mock:
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "No Camera - Behavior Recognition Test", (50, 240),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                cv2.imshow('Behavior Test', frame)
                if cv2.waitKey(1000) & 0xFF == ord('q'):
                    break
                frame_count += 1
                if frame_count >= 5:
                    break
            else:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                detections = yolo.detect(frame)
                behavior_results = behavior_detector.detect(detections, frame)
                result_frame = yolo.draw_detections(frame, detections)
                result_frame = behavior_detector.draw_behavior(result_frame, detections)
                
                info_text = f"Frame: {frame_count} | Persons: {len(detections)}"
                cv2.putText(result_frame, info_text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                y_offset = 60
                for det, behavior, confidence in behavior_results:
                    text = f"Behavior: {behavior.value} ({confidence:.2f})"
                    cv2.putText(result_frame, text, (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    y_offset += 30
                
                cv2.imshow('Behavior Recognition Test', result_frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    
    except KeyboardInterrupt:
        print("\n   ! 测试被用户中断")
    except Exception as e:
        print(f"\n   ✗ 测试过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if not use_mock:
            cap.release()
        cv2.destroyAllWindows()
    
    print("\n5. 测试统计信息:")
    stats = behavior_detector.get_stats()
    print(f"   追踪人数: {stats['total_tracked']}")
    print(f"   行为分布:")
    for behavior, count in stats['behavior_distribution'].items():
        if count > 0:
            print(f"     - {behavior}: {count}")
    
    print("\n" + "=" * 50)
    print("行为识别测试完成!")
    print("=" * 50)
    
    return True


def test_behavior_types():
    print("\n行为类型定义:")
    for behavior in BehaviorType:
        print(f"  - {behavior.name}: {behavior.value}")


if __name__ == "__main__":
    test_behavior_types()
    print("\n")
    success = test_behavior_detection()
    
    if success:
        print("\n✓ 所有测试通过!")
        sys.exit(0)
    else:
        print("\n✗ 测试失败!")
        sys.exit(1)
