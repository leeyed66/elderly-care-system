# 🏠 智能老人远程监护系统

基于 YOLOv8-Pose 的实时老人行为监测与报警系统，专为独居老人安全监护设计。

## ✨ 核心功能

| 功能 | 描述 | 技术方案 |
|------|------|----------|
| **人体检测** | 实时检测画面中的人员 | YOLOv8 |
| **姿态估计** | 17点人体关键点检测 | YOLOv8-Pose |
| **跌倒检测** | 检测跌倒事件并报警 | 姿态角度 + 宽高比分析 |
| **静止检测** | 长时间无活动监测 | 位置追踪算法 |
| **行为识别** | 识别站/坐/躺等状态 | 关键点序列分析 |
| **视频监控** | 实时预览与自动录像 | OpenCV + FFmpeg |
| **报警通知** | 多渠道报警推送 | 声音/邮件/Webhook |

## 🚀 快速开始

### 环境要求

- Python 3.10+
- 4GB+ 内存
- 摄像头（可选，支持视频文件）

### 安装运行

```bash
# 1. 进入项目目录
cd elderly_care_system

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行系统
python main.py
```

启动后访问 http://localhost:5000 查看监控界面。

## 📄 许可证

MIT License
