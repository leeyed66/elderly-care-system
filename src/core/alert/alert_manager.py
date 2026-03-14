"""
报警管理模块
负责处理各种报警通知方式
"""

import os
import time
import json
import logging
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime
import threading
import queue
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """报警类型"""
    FALL = "跌倒检测"
    INACTIVITY = "长时间静止"
    ZONE_INTRUSION = "区域入侵"
    ABNORMAL_BEHAVIOR = "异常行为"
    BEHAVIOR_CHANGE = "行为变化"
    EMERGENCY_BEHAVIOR = "紧急行为"
    SYSTEM_ERROR = "系统错误"


class AlertLevel(Enum):
    """报警级别"""
    INFO = "信息"
    WARNING = "警告"
    CRITICAL = "紧急"


@dataclass
class Alert:
    """报警信息"""
    alert_id: str
    alert_type: AlertType
    level: AlertLevel
    message: str
    timestamp: float
    image: Optional[np.ndarray] = None
    location: Optional[tuple] = None
    metadata: Dict = field(default_factory=dict)


class AlertManager:
    """报警管理器"""
    
    def __init__(self, config: Dict):
        """
        初始化报警管理器
        
        Args:
            config: 报警配置
        """
        self.config = config
        self.alert_history: List[Alert] = []
        self.alert_callbacks: List[Callable] = []
        
        # 报警冷却时间 (每种类型独立)
        self.cooldown_times: Dict[AlertType, float] = {
            AlertType.FALL: 60,
            AlertType.INACTIVITY: 300,
            AlertType.ZONE_INTRUSION: 30,
            AlertType.ABNORMAL_BEHAVIOR: 60,
            AlertType.BEHAVIOR_CHANGE: 10,
            AlertType.EMERGENCY_BEHAVIOR: 0,
            AlertType.SYSTEM_ERROR: 10
        }
        self.last_alert_times: Dict[AlertType, float] = {}
        
        # 报警队列
        self.alert_queue = queue.Queue()
        self.is_running = False
        self.worker_thread = None
        
        # 初始化各种通知方式
        self._init_notifiers()
        
        # 启动处理线程
        self.start()
        
        logger.info("报警管理器初始化完成")
    
    def _init_notifiers(self):
        """初始化通知方式"""
        local_config = self.config.get('local', {})
        push_config = self.config.get('push', {})
        email_config = self.config.get('email', {})
        sms_config = self.config.get('sms', {})
        dingtalk_config = self.config.get('dingtalk', {})
        
        self.notifiers = {
            'local': LocalNotifier(local_config),
            'push': PushNotifier(push_config),
            'email': EmailNotifier(email_config),
            'sms': SMSNotifier(sms_config),
            'dingtalk': DingTalkNotifier(dingtalk_config)
        }
    
    def start(self):
        """启动报警处理"""
        if self.is_running:
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._process_alerts, daemon=True)
        self.worker_thread.start()
        logger.info("报警处理器已启动")
    
    def stop(self):
        """停止报警处理"""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        logger.info("报警处理器已停止")
    
    def _process_alerts(self):
        """报警处理循环"""
        while self.is_running:
            try:
                alert = self.alert_queue.get(timeout=1.0)
                self._send_alert(alert)
                self.alert_history.append(alert)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"处理报警时出错: {e}")
    
    def trigger_alert(self, alert_type: AlertType, level: AlertLevel, 
                     message: str, image: Optional[np.ndarray] = None,
                     location: Optional[tuple] = None,
                     metadata: Optional[Dict] = None) -> bool:
        """
        触发报警
        
        Args:
            alert_type: 报警类型
            level: 报警级别
            message: 报警消息
            image: 报警截图
            location: 位置信息
            metadata: 额外元数据
            
        Returns:
            是否成功触发
        """
        current_time = time.time()
        
        # 检查冷却时间
        last_time = self.last_alert_times.get(alert_type, 0)
        cooldown = self.cooldown_times.get(alert_type, 60)
        
        if current_time - last_time < cooldown:
            logger.debug(f"报警冷却中: {alert_type.value}")
            return False
        
        # 创建报警
        alert_id = f"{alert_type.value}_{int(current_time)}"
        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            level=level,
            message=message,
            timestamp=current_time,
            image=image,
            location=location,
            metadata=metadata or {}
        )
        
        # 更新最后报警时间
        self.last_alert_times[alert_type] = current_time
        
        # 加入队列
        self.alert_queue.put(alert)
        
        # 执行回调
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"报警回调执行失败: {e}")
        
        logger.warning(f"报警触发: [{level.value}] {alert_type.value} - {message}")
        return True
    
    def _send_alert(self, alert: Alert):
        """发送报警"""
        # 根据级别选择通知方式
        if alert.level == AlertLevel.CRITICAL:
            channels = ['local', 'dingtalk', 'push', 'email', 'sms']
        elif alert.level == AlertLevel.WARNING:
            channels = ['local', 'dingtalk', 'push', 'email']
        else:
            channels = ['local']
        
        for channel in channels:
            notifier = self.notifiers.get(channel)
            if notifier and notifier.is_enabled():
                try:
                    notifier.send(alert)
                except Exception as e:
                    logger.error(f"{channel}通知发送失败: {e}")
    
    def register_callback(self, callback: Callable):
        """注册报警回调函数"""
        self.alert_callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        """注销报警回调函数"""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """获取报警历史"""
        return self.alert_history[-limit:]
    
    def clear_history(self):
        """清空报警历史"""
        self.alert_history.clear()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'total_alerts': len(self.alert_history),
            'pending_alerts': self.alert_queue.qsize(),
            'alert_types': {
                atype.value: sum(1 for a in self.alert_history if a.alert_type == atype)
                for atype in AlertType
            }
        }


class BaseNotifier:
    """通知器基类"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get('enabled', False)
    
    def is_enabled(self) -> bool:
        return self.enabled
    
    def send(self, alert: Alert):
        raise NotImplementedError


class LocalNotifier(BaseNotifier):
    """本地通知器 (声音/弹窗)"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.sound_enabled = config.get('sound', True)
        self.sound_file = config.get('sound_file', 'alert.wav')
        self.popup_enabled = config.get('popup', True)
        
        # 尝试加载声音文件
        self.has_sound = False
        if self.sound_enabled:
            try:
                import winsound
                self.has_sound = True
            except ImportError:
                logger.warning("winsound模块不可用，声音报警已禁用")
    
    def send(self, alert: Alert):
        """发送本地通知"""
        # 声音报警
        if self.sound_enabled and self.has_sound:
            try:
                import winsound
                if alert.level == AlertLevel.CRITICAL:
                    winsound.MessageBeep(winsound.MB_ICONHAND)
                else:
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception as e:
                logger.debug(f"声音播放失败: {e}")
        
        logger.info(f"本地通知: [{alert.level.value}] {alert.message}")


class PushNotifier(BaseNotifier):
    """推送通知器 (Webhook)"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url', '')
    
    def send(self, alert: Alert):
        """发送Webhook推送"""
        if not self.webhook_url:
            return
        
        payload = {
            'alert_id': alert.alert_id,
            'type': alert.alert_type.value,
            'level': alert.level.value,
            'message': alert.message,
            'timestamp': datetime.fromtimestamp(alert.timestamp).isoformat(),
            'location': alert.location,
            'metadata': alert.metadata
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"推送通知已发送: {alert.alert_id}")
        except Exception as e:
            logger.error(f"推送通知发送失败: {e}")


class EmailNotifier(BaseNotifier):
    """邮件通知器"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.smtp_server = config.get('smtp_server', '')
        self.smtp_port = config.get('smtp_port', 587)
        self.sender = config.get('sender', '')
        self.password = config.get('password', '')
        self.receivers = config.get('receivers', [])
    
    def send(self, alert: Alert):
        """发送邮件"""
        if not all([self.smtp_server, self.sender, self.password, self.receivers]):
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = ', '.join(self.receivers)
            msg['Subject'] = f"[{alert.level.value}] 老人监护系统报警 - {alert.alert_type.value}"
            
            # 邮件正文
            body = f"""
            <h2>报警信息</h2>
            <p><b>类型:</b> {alert.alert_type.value}</p>
            <p><b>级别:</b> {alert.level.value}</p>
            <p><b>时间:</b> {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><b>消息:</b> {alert.message}</p>
            <p><b>位置:</b> {alert.location}</p>
            """
            
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            # 附加图片
            if alert.image is not None:
                _, img_encoded = cv2.imencode('.jpg', alert.image)
                img_attachment = MIMEImage(img_encoded.tobytes())
                img_attachment.add_header('Content-Disposition', 'attachment', 
                                        filename=f'alert_{alert.alert_id}.jpg')
                msg.attach(img_attachment)
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
            
            logger.info(f"邮件通知已发送: {alert.alert_id}")
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")


class DingTalkNotifier(BaseNotifier):
    """钉钉机器人通知器"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url', '')
        self.secret = config.get('secret', '')
    
    def _generate_sign(self, timestamp: str) -> str:
        """生成钉钉签名（如果启用了加签）"""
        if not self.secret:
            return ''
        
        import hmac
        import hashlib
        import base64
        
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return sign
    
    def send(self, alert: Alert):
        """发送钉钉消息"""
        if not self.webhook_url:
            return
        
        try:
            import time
            import urllib.parse
            
            timestamp = str(int(time.time() * 1000))
            sign = self._generate_sign(timestamp)
            
            # 构建完整 URL
            url = self.webhook_url
            if sign:
                url = f"{url}&timestamp={timestamp}&sign={urllib.parse.quote(sign)}"
            
            # 根据报警级别选择颜色
            color_map = {
                AlertLevel.CRITICAL: '#FF0000',
                AlertLevel.WARNING: '#FF8C00',
                AlertLevel.INFO: '#008000'
            }
            color = color_map.get(alert.level, '#808080')
            
            # 格式化时间
            time_str = datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            # 构建消息内容
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"🚨 {alert.alert_type.value}报警",
                    "text": f"## 🚨 老人监护系统报警\n\n"
                            f"**报警类型：** {alert.alert_type.value}\n\n"
                            f"**报警级别：** <font color='{color}'>**{alert.level.value}**</font>\n\n"
                            f"**报警时间：** {time_str}\n\n"
                            f"**报警内容：** {alert.message}\n\n"
                            f"**位置信息：** {alert.location if alert.location else '未知'}\n\n"
                            f"---\n"
                            f"请及时查看监控画面，确认老人安全状况。"
                },
                "at": {
                    "isAtAll": alert.level == AlertLevel.CRITICAL
                }
            }
            
            response = requests.post(
                url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get('errcode') == 0:
                logger.info(f"钉钉通知已发送: {alert.alert_id}")
            else:
                logger.error(f"钉钉通知发送失败: {result.get('errmsg')}")
                
        except Exception as e:
            logger.error(f"钉钉通知发送失败: {e}")


class SMSNotifier(BaseNotifier):
    """短信通知器 (需要集成短信服务商API)"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.provider = config.get('provider', 'aliyun')
        self.access_key = config.get('access_key', '')
        self.secret_key = config.get('secret_key', '')
        self.phone_numbers = config.get('phone_numbers', [])
    
    def send(self, alert: Alert):
        """发送短信"""
        if not all([self.access_key, self.secret_key, self.phone_numbers]):
            return
        
        logger.info(f"短信通知准备发送: {alert.alert_id}")
