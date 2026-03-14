"""
智能老人远程监护系统 - 主程序入口
"""

import os
import sys
import time
import signal
import argparse
import threading
from pathlib import Path
from typing import Dict, Optional, List
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import cv2
import numpy as np

from core.detection import YOLODetector, FallDetector, InactivityDetector, BehaviorDetector
from core.monitoring import VideoStream, VideoRecorder
from core.alert import AlertManager, AlertType, AlertLevel
from core.utils import ConfigLoader, setup_logger, DatabaseManager

try:
    from web.app import create_web_app
    WEB_AVAILABLE = True
except ImportError as e:
    WEB_AVAILABLE = False
    print(f"Web模块加载失败: {e}")


class ElderlyCareSystem:
    """老人监护系统主类"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self.logger = setup_logger(__name__, 'INFO', 'config/logs')
        self.config = self._load_config()
        self.logger.setLevel(self.config['system'].get('log_level', 'INFO'))
        
        self.logger.info("=" * 50)
        self.logger.info("智能老人远程监护系统启动")
        self.logger.info("=" * 50)
        
        self.video_stream = None
        self.yolo_detector = None
        self.fall_detector = None
        self.inactivity_detector = None
        self.behavior_detector = None
        self.alert_manager = None
        self.video_recorder = None
        self.database = None
        self.web_app = None
        
        self.is_running = False
        self.is_paused = False
        self.main_thread = None
        
        self.frame_count = 0
        self.start_time = None
        self.current_frame = None
        self.current_detections = []
        self.current_person_count = 0
        
        self.skip_frames = self.config['performance'].get('skip_frames', 2)
        self.resize_factor = self.config['performance'].get('resize_factor', 0.5)
        self.process_counter = 0
        
        self._init_components()
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self) -> Dict:
        if not Path(self.config_path).exists():
            self.logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
            return self._default_config()
        try:
            config = ConfigLoader.load_yaml(self.config_path)
            self.logger.info(f"配置加载成功: {self.config_path}")
            return config
        except Exception as e:
            self.logger.error(f"配置加载失败: {e}，使用默认配置")
            return self._default_config()
    
    def _default_config(self) -> Dict:
        return {
            'system': {'log_level': 'INFO', 'log_dir': 'config/logs'},
            'video': {'source_type': 'webcam', 'source_path': 0, 'width': 640, 'height': 480, 'fps': 30},
            'yolo': {'model_path': 'yolov8n.pt', 'conf_threshold': 0.5, 'iou_threshold': 0.45},
            'fall_detection': {'enabled': True, 'method': 'all'},
            'inactivity_detection': {'enabled': True, 'threshold_seconds': 300},
            'behavior_detection': {'enabled': True, 'window_size': 5, 'confidence_threshold': 0.6},
            'alert': {'local': {'enabled': True, 'sound': True}},
            'recording': {'enabled': False},
            'web': {'enabled': False},
            'database': {'path': 'config/data/monitoring.db'},
            'performance': {'skip_frames': 2, 'resize_factor': 0.5}
        }
    
    def _init_components(self):
        try:
            self.logger.info("初始化视频流...")
            self.video_stream = VideoStream(self.config['video'])
            
            self.logger.info("初始化YOLO检测器...")
            self.yolo_detector = YOLODetector(self.config['yolo'])
            self.yolo_detector.warmup()
            
            self.logger.info("初始化跌倒检测器...")
            self.fall_detector = FallDetector(self.config['fall_detection'])
            
            self.logger.info("初始化静止检测器...")
            self.inactivity_detector = InactivityDetector(self.config['inactivity_detection'])
            
            self.logger.info("初始化报警管理器...")
            self.alert_manager = AlertManager(self.config['alert'])
            self.alert_manager.register_callback(self._on_alert)
            
            self.logger.info("初始化录像器...")
            self.video_recorder = VideoRecorder(self.config['recording'])
            
            self.logger.info("初始化数据库...")
            self.database = DatabaseManager(self.config['database']['path'])
            
            if WEB_AVAILABLE and self.config['web'].get('enabled', False):
                self.logger.info("初始化Web应用...")
                self.web_app = create_web_app(self.config['web'], self)
                self.alert_manager.register_callback(self._on_alert_for_web)
            
            self.logger.info("所有组件初始化完成")
        except Exception as e:
            self.logger.error(f"组件初始化失败: {e}")
            raise
    
    def _on_alert(self, alert):
        if self.database:
            self.database.save_alert(
                alert.alert_id,
                alert.alert_type.value,
                alert.level.value,
                alert.message,
                str(alert.location) if alert.location else None,
                None,
                alert.metadata
            )
    
    def _on_alert_for_web(self, alert):
        if self.web_app:
            self.web_app.broadcast_alert({
                'alert_id': alert.alert_id,
                'alert_type': alert.alert_type.value,
                'level': alert.level.value,
                'message': alert.message,
                'timestamp': alert.timestamp,
                'location': alert.location
            })
    
    def _signal_handler(self, signum, frame):
        self.logger.info(f"接收到信号 {signum}，正在关闭系统...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        if self.is_running:
            self.logger.warning("系统已在运行")
            return
        
        self.logger.info("启动监护系统...")
        self.is_running = True
        self.start_time = time.time()
        
        if not self.video_stream.start():
            self.logger.error("视频流启动失败")
            self.is_running = False
            return
        
        if self.config['recording'].get('enabled', False):
            self.video_recorder.start_recording(
                self.config['video']['width'],
                self.config['video']['height'],
                20.0
            )
        
        self.main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self.main_thread.start()
        
        self.logger.info("系统启动完成")
    
    def stop(self):
        if not self.is_running:
            return
        
        self.logger.info("停止监护系统...")
        self.is_running = False
        
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=3.0)
        
        if self.video_stream:
            self.video_stream.stop()
        
        if self.video_recorder:
            self.video_recorder.stop_recording()
        
        if self.alert_manager:
            self.alert_manager.stop()
        
        self.logger.info("系统已停止")
    
    def restart(self):
        self.logger.info("重启系统...")
        self.stop()
        time.sleep(1)
        self.start()
    
    def _main_loop(self):
        self.logger.info("主处理循环已启动")
        while self.is_running:
            try:
                frame_data = self.video_stream.read()
                if frame_data is None:
                    time.sleep(0.01)
                    continue
                
                frame = frame_data.frame
                self.frame_count += 1
                self.process_counter += 1
                
                if self.process_counter % (self.skip_frames + 1) != 0:
                    self.current_frame = frame
                    continue
                
                processed_frame = self._process_frame(frame)
                self.current_frame = processed_frame
                
                if self.video_recorder and self.video_recorder.is_recording:
                    self.video_recorder.write_frame(processed_frame)
            except Exception as e:
                self.logger.error(f"主循环出错: {e}")
                time.sleep(0.1)
        self.logger.info("主处理循环已停止")
    
    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        if self.resize_factor != 1.0:
            process_frame = cv2.resize(frame, None, fx=self.resize_factor, fy=self.resize_factor)
        else:
            process_frame = frame
        
        detections = self.yolo_detector.detect(process_frame)
        
        if self.resize_factor != 1.0:
            scale = 1.0 / self.resize_factor
            for det in detections:
                det.bbox *= scale
                det.center = (det.center[0] * scale, det.center[1] * scale)
                det.width *= scale
                det.height *= scale
        
        self.current_detections = detections
        self.current_person_count = len(detections)
        
        if self.config['fall_detection'].get('enabled', True):
            fall_results = self.fall_detector.detect_fall(detections, frame)
            for det, state, confidence in fall_results:
                if state.value == "跌倒":
                    self.alert_manager.trigger_alert(
                        AlertType.FALL,
                        AlertLevel.CRITICAL,
                        f"检测到跌倒事件! 置信度: {confidence:.2f}",
                        image=frame,
                        location=det.center,
                        metadata={'confidence': confidence, 'track_id': getattr(det, 'track_id', None)}
                    )
                    if self.database:
                        self.database.save_fall_event(0, confidence, str(det.center), None)
        
        if self.config.get('behavior_detection', {}).get('enabled', True) and self.behavior_detector:
            behavior_results = self.behavior_detector.detect(detections, frame)
            for det, behavior, confidence in behavior_results:
                if confidence >= 0.7:
                    person_behavior = self.behavior_detector.get_person_behavior(
                        self.behavior_detector._get_track_id(det)
                    )
                    if person_behavior and behavior.value == "躺下":
                        if person_behavior.behavior_duration > 30 * 60:
                            self.alert_manager.trigger_alert(
                                AlertType.ABNORMAL_BEHAVIOR,
                                AlertLevel.WARNING,
                                f"检测到长时间躺卧 ({person_behavior.behavior_duration/60:.0f}分钟)",
                                image=frame,
                                location=det.center,
                                metadata={'behavior': behavior.value, 'duration': person_behavior.behavior_duration}
                            )
                    if self.database:
                        self.database.save_behavior_event(behavior.value, confidence, str(det.center), None)
        
        if self.config['inactivity_detection'].get('enabled', True):
            activity_results = self.inactivity_detector.update(detections)
            for track_id, inactive_time, should_alert in activity_results:
                if should_alert:
                    self.alert_manager.trigger_alert(
                        AlertType.INACTIVITY,
                        AlertLevel.WARNING,
                        f"检测到长时间静止! 持续时间: {inactive_time:.0f}秒",
                        image=frame,
                        metadata={'duration': inactive_time, 'track_id': track_id}
                    )
        
        result_frame = self.yolo_detector.draw_detections(frame, detections)
        
        if self.config['inactivity_detection'].get('enabled', True):
            result_frame = self.inactivity_detector.draw_status(result_frame, detections)
        
        if self.config.get('behavior_detection', {}).get('enabled', True) and self.behavior_detector:
            result_frame = self.behavior_detector.draw_behavior(result_frame, detections)
        
        result_frame = self._add_overlay(result_frame)
        return result_frame
    
    def _add_overlay(self, frame: np.ndarray) -> np.ndarray:
        info_lines = [
            f"Persons: {self.current_person_count}",
            f"FPS: {self.get_fps():.1f}",
            f"Frame: {self.frame_count}"
        ]
        y_offset = 30
        for i, line in enumerate(info_lines):
            y = y_offset + i * 25
            cv2.rectangle(frame, (10, y - 20), (200, y + 5), (0, 0, 0), -1)
            cv2.putText(frame, line, (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        return frame
    
    def get_fps(self) -> float:
        if self.start_time is None:
            return 0
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return 0
        return self.frame_count / elapsed
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        return self.current_frame
    
    def get_status(self) -> Dict:
        return {
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'person_count': self.current_person_count,
            'frame_count': self.frame_count,
            'fps': self.get_fps(),
            'uptime': time.time() - self.start_time if self.start_time else 0,
            'detection_active': self.yolo_detector is not None,
            'fall_detection_enabled': self.config['fall_detection'].get('enabled', False),
            'behavior_detection_enabled': self.config.get('behavior_detection', {}).get('enabled', False),
            'video_stream_status': self.video_stream.get_stats() if self.video_stream else None
        }
    
    def get_stats(self) -> Dict:
        stats = {
            'total_frames': self.frame_count,
            'fps': self.get_fps(),
            'uptime': time.time() - self.start_time if self.start_time else 0,
            'person_count': self.current_person_count
        }
        if self.database:
            db_stats = self.database.get_stats()
            stats.update(db_stats)
        if self.alert_manager:
            stats['alert_stats'] = self.alert_manager.get_stats()
        if self.fall_detector:
            stats['fall_stats'] = self.fall_detector.get_stats()
        if self.behavior_detector:
            stats['behavior_stats'] = self.behavior_detector.get_stats()
        return stats
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict]:
        if self.database:
            return self.database.get_alerts(limit=limit)
        return []
    
    def get_recent_detections(self, limit: int = 50) -> List[Dict]:
        if self.database:
            return self.database.get_detections(limit=limit)
        return []
    
    def get_recordings(self) -> List[Dict]:
        if self.video_recorder:
            return self.video_recorder.get_recordings_list()
        return []
    
    def update_config(self, new_config: Dict):
        self.config = ConfigLoader.merge_configs(self.config, new_config)
        self.logger.info("配置已更新")


def run_web_server(system: ElderlyCareSystem):
    if system.web_app:
        web_config = system.config['web']
        system.web_app.run(
            host=web_config.get('host', '0.0.0.0'),
            port=web_config.get('port', 5000),
            debug=web_config.get('debug', False)
        )


def main():
    parser = argparse.ArgumentParser(description='智能老人远程监护系统')
    parser.add_argument('--config', '-c', type=str, default='config/config.yaml')
    parser.add_argument('--source', '-s', type=str, default=None)
    parser.add_argument('--no-web', action='store_true')
    parser.add_argument('--model', '-m', type=str, default=None)
    
    args = parser.parse_args()
    
    system = ElderlyCareSystem(args.config)
    
    if args.source:
        if args.source.isdigit():
            system.config['video']['source_type'] = 'webcam'
            system.config['video']['source_path'] = int(args.source)
        elif args.source.startswith('rtsp://'):
            system.config['video']['source_type'] = 'rtsp'
            system.config['video']['source_path'] = args.source
        else:
            system.config['video']['source_type'] = 'file'
            system.config['video']['source_path'] = args.source
    
    if args.model:
        system.config['yolo']['model_path'] = args.model
    
    if args.no_web:
        system.config['web']['enabled'] = False
    
    try:
        system.start()
        
        if system.config['web'].get('enabled', False) and WEB_AVAILABLE:
            web_thread = threading.Thread(target=run_web_server, args=(system,), daemon=True)
            web_thread.start()
            print(f"\n🌐 Web界面已启动: http://localhost:{system.config['web'].get('port', 5000)}")
        
        print("\n" + "=" * 50)
        print("系统运行中，按 Ctrl+C 停止")
        print("=" * 50 + "\n")
        
        while system.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n用户中断，正在关闭...")
    finally:
        system.stop()
        print("系统已关闭")


if __name__ == "__main__":
    main()
