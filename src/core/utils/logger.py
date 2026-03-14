"""
日志配置
"""

import logging
import colorlog
from pathlib import Path
from datetime import datetime


def setup_logger(name: str = None, log_level: str = "INFO", log_dir: str = None) -> logging.Logger:
    """
    设置日志
    
    Args:
        name: 日志名称
        log_level: 日志级别
        log_dir: 日志文件目录
    
    Returns:
        配置好的Logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 清除已有处理器
    logger.handlers.clear()
    
    # 控制台处理器 (带颜色)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    color_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(color_formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        log_file = log_path / f"app_{timestamp}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger
