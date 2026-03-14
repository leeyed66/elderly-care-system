"""
视频流处理模块
支持多种视频源: 摄像头, RTSP, 文件, IP相机
"""

import cv2
import time
import threading
import queue
import logging
from typing import Optional, Callable, Tuple, Union
from enum import Enum
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


class VideoSource(Enum):
    """视频源类型"""
    WEBCAM = "webcam"
    RTSP = "rtsp"
    FILE = "file"
    IP_CAMERA = "ip_camera"


@dataclass
class FrameData:
    """帧数据结构"""
    frame: np.ndarray
    timestamp: float
    frame_number: int
    source_info: dict = None


class VideoStream:
    """视频流处理器"""
    
    def __init__(self, config: dict):
        """
        初始化视频流
        
        Args:
            config: 视频配置
        """
        self.config = config
        self.source_type = VideoSource(config.get('source_type', 'webcam'))
        self.source_path = config.get('source_path', 0)
        self.target_width = config.get('width', 640)
        self.target_height = config.get('height', 480)
        self.target_fps = config.get('fps', 30)
        self.buffer_size = config.get('buffer_size', 10)
        
        self.cap = None
        self.is_running = False
        self.is_paused = False
        
        # 帧缓冲区
        self.frame_queue = queue.Queue(maxsize=self.buffer_size)
        self.latest_frame = None
        self.latest_frame_data = None
        
        # 统计信息
        self.frame_count = 0
        self.dropped_frames = 0
        self.start_time = None
        self.actual_fps = 0
        
        # 线程
        self.capture_thread = None
        self.lock = threading.Lock()
        
        logger.info(f"视频流初始化: {self.source_type.value} - {self.source_path}")
    
    def start(self) -> bool:
        """启动视频流"""
        if self.is_running:
            logger.warning("视频流已经在运行")
            return True
        
        # 打开视频源
        if not self._open_source():
            return False
        
        self.is_running = True
        self.start_time = time.time()
        
        # 启动捕获线程
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        
        logger.info("视频流已启动")
        return True
    
    def _open_source(self) -> bool:
        """打开视频源"""
        try:
            if self.source_type == VideoSource.WEBCAM:
                # 摄像头
                self.cap = cv2.VideoCapture(int(self.source_path))
                # 设置摄像头参数
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
                self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                
            elif self.source_type == VideoSource.RTSP:
                # RTSP流
                self.cap = cv2.VideoCapture(self.source_path, cv2.CAP_FFMPEG)
                
            elif self.source_type == VideoSource.FILE:
                # 视频文件
                self.cap = cv2.VideoCapture(self.source_path)
                
            elif self.source_type == VideoSource.IP_CAMERA:
                # IP相机 (使用HTTP/RTSP)
                self.cap = cv2.VideoCapture(self.source_path)
            
            if not self.cap.isOpened():
                logger.error(f"无法打开视频源: {self.source_path}")
                return False
            
            # 获取实际参数
            self.actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            logger.info(f"视频源已打开: {self.actual_width}x{self.actual_height} @ {self.actual_fps:.1f}fps")
            return True
            
        except Exception as e:
            logger.error(f"打开视频源失败: {e}")
            return False
    
    def _capture_loop(self):
        """捕获循环 (在后台线程中运行)"""
        frame_interval = 1.0 / self.target_fps if self.target_fps > 0 else 0
        last_capture_time = 0
        
        while self.is_running:
            if self.is_paused:
                time.sleep(0.01)
                continue
            
            current_time = time.time()
            
            # 帧率控制
            if frame_interval > 0 and current_time - last_capture_time < frame_interval:
                time.sleep(0.001)
                continue
            
            ret, frame = self.cap.read()
            
            if not ret:
                if self.source_type == VideoSource.FILE:
                    # 视频文件结束，循环播放
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.frame_count = 0
                    continue
                else:
                    logger.error("视频流读取失败")
                    break
            
            last_capture_time = current_time
            self.frame_count += 1
            
            # 调整帧大小
            if frame.shape[1] != self.target_width or frame.shape[0] != self.target_height:
                frame = cv2.resize(frame, (self.target_width, self.target_height))
            
            # 创建帧数据
            frame_data = FrameData(
                frame=frame,
                timestamp=current_time,
                frame_number=self.frame_count,
                source_info={
                    'width': self.target_width,
                    'height': self.target_height,
                    'fps': self.actual_fps
                }
            )
            
            # 更新最新帧
            with self.lock:
                self.latest_frame = frame.copy()
                self.latest_frame_data = frame_data
            
            # 添加到队列 (非阻塞)
            try:
                self.frame_queue.put_nowait(frame_data)
            except queue.Full:
                # 队列满，丢弃最旧的帧
                try:
                    self.frame_queue.get_nowait()
                    self.dropped_frames += 1
                    self.frame_queue.put_nowait(frame_data)
                except queue.Empty:
                    pass
        
        logger.info("捕获线程已停止")
    
    def read(self) -> Optional[FrameData]:
        """
        读取一帧
        
        Returns:
            FrameData或None
        """
        if not self.is_running:
            return None
        
        try:
            return self.frame_queue.get(timeout=1.0)
        except queue.Empty:
            return None
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """获取最新帧 (非阻塞)"""
        with self.lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
    
    def get_latest_frame_data(self) -> Optional[FrameData]:
        """获取最新帧数据"""
        with self.lock:
            return self.latest_frame_data
    
    def pause(self):
        """暂停视频流"""
        self.is_paused = True
        logger.info("视频流已暂停")
    
    def resume(self):
        """恢复视频流"""
        self.is_paused = False
        logger.info("视频流已恢复")
    
    def stop(self):
        """停止视频流"""
        self.is_running = False
        
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
        
        if self.cap:
            self.cap.release()
        
        # 清空队列
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
        
        logger.info("视频流已停止")
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        return {
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'frame_count': self.frame_count,
            'dropped_frames': self.dropped_frames,
            'elapsed_time': elapsed,
            'actual_fps': self.frame_count / elapsed if elapsed > 0 else 0,
            'queue_size': self.frame_queue.qsize(),
            'resolution': (self.actual_width, self.actual_height) if hasattr(self, 'actual_width') else None
        }
    
    def set_resolution(self, width: int, height: int):
        """设置分辨率"""
        self.target_width = width
        self.target_height = height
        
        if self.cap and self.source_type == VideoSource.WEBCAM:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    def restart(self) -> bool:
        """重启视频流"""
        self.stop()
        time.sleep(0.5)
        return self.start()
