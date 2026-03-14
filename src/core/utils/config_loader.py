"""
配置加载工具
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    """配置加载器"""
    
    @staticmethod
    def load_yaml(config_path: str) -> Dict[str, Any]:
        """加载YAML配置文件"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return config
    
    @staticmethod
    def save_yaml(config: Dict, config_path: str):
        """保存配置到YAML文件"""
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    
    @staticmethod
    def merge_configs(base_config: Dict, override_config: Dict) -> Dict:
        """合并配置"""
        result = base_config.copy()
        
        for key, value in override_config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader.merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
