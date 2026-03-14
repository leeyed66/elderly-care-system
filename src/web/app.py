"""
Flask Web应用
提供监控界面和API
"""

import os
import sys
import json
import base64
import cv2
import numpy as np
from flask import Flask, render_template, Response, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from datetime import datetime
import threading
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


class WebApp:
    """Web应用"""
    
    def __init__(self, config: dict, monitoring_system=None):
        """
        初始化Web应用
        
        Args:
            config: Web配置
            monitoring_system: 监护系统实例
        """
        self.config = config
        self.monitoring_system = monitoring_system
        
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = config.get('secret_key', 'dev-secret-key')
        
        CORS(self.app)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        
        self._setup_routes()
        self._setup_socketio()
        
        # 视频流质量
        self.stream_quality = config.get('stream_quality', 80)
        self.stream_fps = config.get('stream_fps', 15)
        
        self.is_running = False
        
        logger.info("Web应用初始化完成")
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.app.route('/')
        def index():
            """首页 - 监控面板"""
            return render_template('index.html')
        
        @self.app.route('/api/status')
        def api_status():
            """获取系统状态"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            return jsonify(self.monitoring_system.get_status())
        
        @self.app.route('/api/stats')
        def api_stats():
            """获取统计数据"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            return jsonify(self.monitoring_system.get_stats())
        
        @self.app.route('/api/alerts')
        def api_alerts():
            """获取报警历史"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            limit = request.args.get('limit', 50, type=int)
            return jsonify(self.monitoring_system.get_recent_alerts(limit))
        
        @self.app.route('/api/detections')
        def api_detections():
            """获取检测历史"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            limit = request.args.get('limit', 50, type=int)
            return jsonify(self.monitoring_system.get_recent_detections(limit))
        
        @self.app.route('/api/recordings')
        def api_recordings():
            """获取录像列表"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            return jsonify(self.monitoring_system.get_recordings())
        
        @self.app.route('/api/behaviors')
        def api_behaviors():
            """获取当前行为识别结果"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            if hasattr(self.monitoring_system, 'behavior_detector') and self.monitoring_system.behavior_detector:
                return jsonify(self.monitoring_system.behavior_detector.get_all_behaviors())
            return jsonify({})
        
        @self.app.route('/api/behavior_events')
        def api_behavior_events():
            """获取行为事件历史"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            limit = request.args.get('limit', 50, type=int)
            if hasattr(self.monitoring_system, 'database') and self.monitoring_system.database:
                return jsonify(self.monitoring_system.database.get_behavior_events(limit=limit))
            return jsonify([])
        
        @self.app.route('/api/config', methods=['GET'])
        def get_config():
            """获取配置"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            return jsonify(self.monitoring_system.config)
        
        @self.app.route('/api/config', methods=['POST'])
        def update_config():
            """更新配置"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            new_config = request.json
            self.monitoring_system.update_config(new_config)
            return jsonify({'success': True})
        
        @self.app.route('/api/control/start', methods=['POST'])
        def control_start():
            """启动监控"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            self.monitoring_system.start()
            return jsonify({'success': True, 'status': 'running'})
        
        @self.app.route('/api/control/stop', methods=['POST'])
        def control_stop():
            """停止监控"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            self.monitoring_system.stop()
            return jsonify({'success': True, 'status': 'stopped'})
        
        @self.app.route('/api/control/restart', methods=['POST'])
        def control_restart():
            """重启监控"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            self.monitoring_system.restart()
            return jsonify({'success': True, 'status': 'restarting'})
        
        @self.app.route('/api/behavior_stats')
        def api_behavior_stats():
            """获取行为统计信息"""
            if self.monitoring_system is None:
                return jsonify({'error': '系统未启动'}), 503
            
            if hasattr(self.monitoring_system, 'behavior_detector') and self.monitoring_system.behavior_detector:
                return jsonify(self.monitoring_system.behavior_detector.get_stats())
            return jsonify({'error': '行为检测未启用'})
        
        @self.app.route('/video_feed')
        def video_feed():
            """视频流"""
            return Response(
                self._generate_frames(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
    
    def _setup_socketio(self):
        """设置SocketIO事件"""
        
        @self.socketio.on('connect')
        def handle_connect():
            logger.info(f"客户端已连接: {request.sid}")
            emit('status', {'message': '已连接到服务器'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info(f"客户端已断开: {request.sid}")
    
    def _generate_frames(self):
        """生成视频帧"""
        while True:
            if self.monitoring_system is None:
                # 返回空白帧
                blank = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank, "System Not Running", (150, 240),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                _, buffer = cv2.imencode('.jpg', blank)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                self.socketio.sleep(0.1)
                continue
            
            frame = self.monitoring_system.get_current_frame()
            
            if frame is not None:
                # 压缩帧
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.stream_quality]
                _, buffer = cv2.imencode('.jpg', frame, encode_params)
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            
            # 控制帧率
            self.socketio.sleep(1.0 / self.stream_fps)
    
    def broadcast_alert(self, alert_data: dict):
        """广播报警信息"""
        try:
            self.socketio.emit('alert', alert_data)
        except Exception as e:
            logger.error(f"广播报警失败: {e}")
    
    def broadcast_status(self, status_data: dict):
        """广播状态信息"""
        try:
            self.socketio.emit('status_update', status_data)
        except Exception as e:
            logger.error(f"广播状态失败: {e}")
    
    def run(self, host: str = None, port: int = None, debug: bool = False):
        """运行Web服务器"""
        host = host or self.config.get('host', '0.0.0.0')
        port = port or self.config.get('port', 5000)
        debug = debug or self.config.get('debug', False)
        
        self.is_running = True
        logger.info(f"启动Web服务器: http://{host}:{port}")
        
        self.socketio.run(
            self.app,
            host=host,
            port=port,
            debug=debug,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    
    def stop(self):
        """停止Web服务器"""
        self.is_running = False
        logger.info("Web服务器已停止")


_web_app_instance = None


def create_web_app(config: dict, monitoring_system=None) -> WebApp:
    """创建Web应用实例"""
    global _web_app_instance
    _web_app_instance = WebApp(config, monitoring_system)
    return _web_app_instance


def get_web_app() -> WebApp:
    """获取Web应用实例"""
    return _web_app_instance
