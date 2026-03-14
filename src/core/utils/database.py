"""
数据库管理模块
用于存储检测记录和报警历史
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
        logger.info(f"数据库初始化完成: {db_path}")
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接 (上下文管理器)"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 检测记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    person_count INTEGER,
                    detections TEXT,
                    frame_path TEXT
                )
            ''')
            
            # 报警记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT UNIQUE,
                    alert_type TEXT,
                    alert_level TEXT,
                    message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    location TEXT,
                    image_path TEXT,
                    metadata TEXT
                )
            ''')
            
            # 跌倒事件表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fall_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER,
                    confidence REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    location TEXT,
                    image_path TEXT
                )
            ''')
            
            # 系统日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT,
                    message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 行为事件表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS behavior_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER,
                    behavior_type TEXT,
                    confidence REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    location TEXT,
                    image_path TEXT,
                    duration REAL
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_falls_time ON fall_events(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_detections_time ON detections(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_behavior_time ON behavior_events(timestamp)')
    
    def save_detection(self, person_count: int, detections: List[Dict], 
                      frame_path: Optional[str] = None) -> int:
        """保存检测记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO detections (person_count, detections, frame_path)
                VALUES (?, ?, ?)
            ''', (person_count, json.dumps(detections), frame_path))
            return cursor.lastrowid
    
    def save_alert(self, alert_id: str, alert_type: str, level: str, 
                   message: str, location: Optional[str] = None,
                   image_path: Optional[str] = None, 
                   metadata: Optional[Dict] = None) -> int:
        """保存报警记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO alerts 
                (alert_id, alert_type, alert_level, message, location, image_path, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (alert_id, alert_type, level, message, location, 
                 image_path, json.dumps(metadata) if metadata else None))
            return cursor.lastrowid
    
    def save_fall_event(self, track_id: int, confidence: float,
                       location: Optional[str] = None,
                       image_path: Optional[str] = None) -> int:
        """保存跌倒事件"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO fall_events (track_id, confidence, location, image_path)
                VALUES (?, ?, ?, ?)
            ''', (track_id, confidence, location, image_path))
            return cursor.lastrowid
    
    def save_system_log(self, level: str, message: str) -> int:
        """保存系统日志"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_logs (level, message)
                VALUES (?, ?)
            ''', (level, message))
            return cursor.lastrowid
    
    def get_detections(self, start_time: Optional[str] = None,
                      end_time: Optional[str] = None,
                      limit: int = 100) -> List[Dict]:
        """获取检测记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM detections WHERE 1=1'
            params = []
            
            if start_time:
                query += ' AND timestamp >= ?'
                params.append(start_time)
            if end_time:
                query += ' AND timestamp <= ?'
                params.append(end_time)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_alerts(self, alert_type: Optional[str] = None,
                   level: Optional[str] = None,
                   start_time: Optional[str] = None,
                   limit: int = 100) -> List[Dict]:
        """获取报警记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM alerts WHERE 1=1'
            params = []
            
            if alert_type:
                query += ' AND alert_type = ?'
                params.append(alert_type)
            if level:
                query += ' AND alert_level = ?'
                params.append(level)
            if start_time:
                query += ' AND timestamp >= ?'
                params.append(start_time)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_fall_events(self, start_time: Optional[str] = None,
                       limit: int = 100) -> List[Dict]:
        """获取跌倒事件"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM fall_events WHERE 1=1'
            params = []
            
            if start_time:
                query += ' AND timestamp >= ?'
                params.append(start_time)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_stats(self) -> Dict:
        """获取统计数据"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM detections')
            total_detections = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM alerts')
            total_alerts = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM fall_events')
            total_falls = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM detections 
                WHERE date(timestamp) = date('now')
            ''')
            today_detections = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM alerts 
                WHERE date(timestamp) = date('now')
            ''')
            today_alerts = cursor.fetchone()[0]
            
            return {
                'total_detections': total_detections,
                'total_alerts': total_alerts,
                'total_falls': total_falls,
                'today_detections': today_detections,
                'today_alerts': today_alerts
            }
    
    def save_behavior_event(self, behavior_type: str, confidence: float,
                           location: Optional[str] = None,
                           image_path: Optional[str] = None,
                           track_id: int = 0,
                           duration: float = 0.0) -> int:
        """保存行为事件"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO behavior_events (track_id, behavior_type, confidence, location, image_path, duration)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (track_id, behavior_type, confidence, location, image_path, duration))
            return cursor.lastrowid
    
    def get_behavior_events(self, behavior_type: Optional[str] = None,
                           start_time: Optional[str] = None,
                           limit: int = 100) -> List[Dict]:
        """获取行为事件"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = 'SELECT * FROM behavior_events WHERE 1=1'
            params = []
            
            if behavior_type:
                query += ' AND behavior_type = ?'
                params.append(behavior_type)
            if start_time:
                query += ' AND timestamp >= ?'
                params.append(start_time)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def cleanup_old_records(self, days: int = 30):
        """清理旧记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            tables = ['detections', 'alerts', 'fall_events', 'system_logs', 'behavior_events']
            for table in tables:
                cursor.execute(f'''
                    DELETE FROM {table} 
                    WHERE timestamp < datetime('now', '-{days} days')
                ''')
                deleted = cursor.rowcount
                logger.info(f"清理 {table} 表 {deleted} 条旧记录")
