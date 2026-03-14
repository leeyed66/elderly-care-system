"""
视频录像模块
用于自动保存监控视频
"""

import os
import cv2
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
import glob

logger = logging.getLogger(__name__)


class VideoRecorder:
    """视频录像器"""
    
    def __init__(self, config: dict):
        """
        初始化录像器
        
        Args:
            config: 录像配置
        """
        self.config = config
        self.enabled = config.get('enabled', True)
        self.output_dir = Path(config.get('output_dir', 'recordings'))
        self.format = config.get('format', 'mp4')
        self.codec = config.get('codec', 'mp4v')
        self.segment_duration = config.get('segment_duration', 300)
        self.retention_days = config.get('retention_days', 7)
        
        self.writer = None
        self.is_recording = False
        self.current_file = None
        self.segment_start_time = None
        
        self.frame_width = None
        self.frame_height = None
        self.fps = None
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"录像器初始化完成，输出目录: {self.output_dir}")
    
    def start_recording(self, width: int, height: int, fps: float = 20.0) -> bool:
        """
        开始录像
        
        Args:
            width: 帧宽度
            height: 帧高度
            fps: 帧率
        """
        if not self.enabled:
            return False
        
        if self.is_recording:
            logger.warning("录像已在进行中")
            return True
        
        self.frame_width = width
        self.frame_height = height
        self.fps = fps
        
        return self._start_new_segment()
    
    def _start_new_segment(self) -> bool:
        """开始新的录像段"""
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.{self.format}"
            self.current_file = self.output_dir / filename
            
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*self.codec)
            self.writer = cv2.VideoWriter(
                str(self.current_file),
                fourcc,
                self.fps,
                (self.frame_width, self.frame_height)
            )
            
            if not self.writer.isOpened():
                logger.error("无法创建视频写入器")
                return False
            
            self.is_recording = True
            self.segment_start_time = time.time()
            
            logger.info(f"开始录像: {self.current_file}")
            return True
            
        except Exception as e:
            logger.error(f"开始录像失败: {e}")
            return False
    
    def write_frame(self, frame):
        """写入一帧"""
        if not self.is_recording or self.writer is None:
            return
        
        try:
            # 检查是否需要分段
            if time.time() - self.segment_start_time >= self.segment_duration:
                self._rotate_segment()
            
            # 确保帧大小正确
            if frame.shape[1] != self.frame_width or frame.shape[0] != self.frame_height:
                frame = cv2.resize(frame, (self.frame_width, self.frame_height))
            
            self.writer.write(frame)
            
        except Exception as e:
            logger.error(f"写入帧失败: {e}")
    
    def _rotate_segment(self):
        """轮换录像段"""
        # 关闭当前写入器
        if self.writer:
            self.writer.release()
        
        # 清理旧文件
        self._cleanup_old_files()
        
        # 开始新段
        self._start_new_segment()
    
    def _cleanup_old_files(self):
        """清理旧录像文件"""
        try:
            cutoff_time = datetime.now() - timedelta(days=self.retention_days)
            
            for file_path in self.output_dir.glob(f"*.{self.format}"):
                # 从文件名解析时间
                try:
                    filename = file_path.stem
                    if filename.startswith("recording_"):
                        date_str = filename[10:25]
                        file_time = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                        
                        if file_time < cutoff_time:
                            file_path.unlink()
                            logger.debug(f"删除旧录像: {file_path}")
                except Exception:
                    continue
                    
        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")
    
    def stop_recording(self):
        """停止录像"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        if self.writer:
            self.writer.release()
            self.writer = None
        
        logger.info(f"停止录像: {self.current_file}")
        self.current_file = None
    
    def get_status(self) -> dict:
        """获取录像状态"""
        if not self.is_recording:
            return {'recording': False}
        
        elapsed = time.time() - self.segment_start_time if self.segment_start_time else 0
        return {
            'recording': True,
            'current_file': str(self.current_file) if self.current_file else None,
            'segment_elapsed': elapsed,
            'segment_remaining': self.segment_duration - elapsed
        }
    
    def get_recordings_list(self) -> list:
        """获取录像文件列表"""
        recordings = []
        
        try:
            for file_path in sorted(self.output_dir.glob(f"*.{self.format}"), reverse=True):
                stat = file_path.stat()
                recordings.append({
                    'filename': file_path.name,
                    'path': str(file_path),
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
        except Exception as e:
            logger.error(f"获取录像列表失败: {e}")
        
        return recordings
