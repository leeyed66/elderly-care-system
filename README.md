# 🏠 智能老人远程监护系统

基于 YOLOv8-Pose 的实时老人行为监测与报警系统，专为独居老人安全监护设计。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Pose-green.svg)](https://ultralytics.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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
# 1. 克隆项目
git clone https://github.com/leeyed66/elderly-care-system.git
cd elderly-care-system

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 下载YOLO模型（会自动下载，也可手动下载）
# wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-pose.pt

# 5. 运行系统
python main.py
```

启动后访问 http://localhost:5000 查看监控界面。

### 命令行参数

```bash
python main.py [选项]

  -c, --config PATH    # 指定配置文件 (默认: config/config.yaml)
  -s, --source SOURCE  # 视频源: 0(摄像头), 文件路径, RTSP地址
  -m, --model PATH     # 指定YOLO模型路径
  --no-web             # 禁用Web界面
```

## ⚙️ 配置文件

主配置文件: `config/config.yaml`

```yaml
# 视频源设置
video:
  source_type: "webcam"  # webcam / rtsp / file
  source_path: 0         # 摄像头索引或文件路径

# YOLO模型
yolo:
  model_path: "yolov8n-pose.pt"  # 姿态模型(推荐)
  conf_threshold: 0.5
  device: "auto"         # auto / cpu / cuda

# 跌倒检测
fall_detection:
  enabled: true
  method: "all"          # simple / ratio / angle / all
  height_threshold: 0.3  # 高度下降阈值
  aspect_ratio_threshold: 1.0  # 宽高比阈值
  cooldown_time: 10      # 报警冷却时间(秒)

# 静止检测
inactivity_detection:
  enabled: true
  threshold_seconds: 300  # 静止报警阈值(5分钟)

# Web界面
web:
  enabled: true
  host: "0.0.0.0"
  port: 5000

# 录像设置
recording:
  enabled: true
  retention_days: 7      # 录像保留天数
```

## 🏗️ 系统架构

```
输入层                  检测层                    处理层                  输出层
┌─────────┐           ┌─────────────┐           ┌─────────────┐         ┌─────────┐
│ 摄像头   │ ────────→ │ YOLOv8-Pose │ ────────→ │  视频录像   │ ──────→ │ Web界面 │
│ RTSP流  │           │  人体检测   │           │  数据存储   │         │ 报警通知 │
│ 视频文件 │           │  姿态估计   │           │  报警管理   │         │ 日志记录 │
└─────────┘           │  跌倒检测   │           └─────────────┘         └─────────┘
                      └─────────────┘
```

## 📁 项目结构

```
elderly_care_system/
├── config/
│   ├── config.yaml          # 主配置文件
│   ├── data/
│   │   ├── monitoring.db    # SQLite数据库
│   │   └── recordings/      # 录像文件
│   ├── logs/                # 日志文件
│   └── models/              # 模型文件目录
├── src/
│   ├── core/
│   │   ├── detection/       # 检测模块
│   │   │   ├── yolo_detector.py      # YOLO检测
│   │   │   ├── fall_detector.py      # 跌倒检测
│   │   │   ├── inactivity_detector.py # 静止检测
│   │   │   └── behavior_detector.py  # 行为识别
│   │   ├── monitoring/      # 监控模块
│   │   │   ├── video_stream.py       # 视频流处理
│   │   │   └── recorder.py           # 录像管理
│   │   ├── alert/           # 报警模块
│   │   │   └── alert_manager.py      # 报警管理
│   │   └── utils/           # 工具模块
│   │       ├── config_loader.py      # 配置加载
│   │       ├── database.py           # 数据库操作
│   │       └── logger.py             # 日志记录
│   └── web/                 # Web界面
│       ├── app.py
│       └── templates/
│           └── index.html   # 监控页面
├── main.py                  # 主程序入口
├── requirements.txt         # 依赖列表
├── start.bat                # Windows启动脚本
├── .env.example             # 环境变量示例
├── test_setup.py            # 安装测试脚本
└── test_behavior.py         # 行为检测测试脚本
```

## 🔌 API 接口

### 系统状态
```http
GET /api/status
```

```json
{
  "is_running": true,
  "person_count": 1,
  "fps": 28.5,
  "fall_detection_enabled": true
}
```

### 统计数据
```http
GET /api/stats
```

### 报警记录
```http
GET /api/alerts?limit=50
```

### 视频流
```http
GET /video_feed
```
返回 MJPEG 实时视频流

## 🧠 算法原理

### 17点人体姿态

```
0-鼻子    1-左眼    2-右眼    3-左耳    4-右耳
5-左肩    6-右肩    7-左肘    8-右肘    9-左腕   10-右腕
11-左髋   12-右髋   13-左膝   14-右膝   15-左踝  16-右踝
```

### 跌倒检测

系统综合以下指标判断跌倒：

1. **躯干角度**: 计算肩中心到髋中心的连线角度，躺下时接近水平（>60°）
2. **身高/肩宽比**: 站立时 >3，躺下时 <2
3. **检测框宽高比**: 从站立（高>宽）变为躺下（宽>高）

## 📊 性能优化

```yaml
# CPU优化
performance:
  skip_frames: 2        # 每隔2帧处理一次
  resize_factor: 0.5    # 处理分辨率减半

# GPU优化
yolo:
  device: "cuda"        # 使用GPU
  half: true            # 半精度推理
```

## ❓ 常见问题

**Q: 模型下载失败？**  
手动下载到项目根目录：
```bash
wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-pose.pt
```

**Q: 摄像头无法打开？**  
尝试更换摄像头索引：`python main.py --source 1`

**Q: FPS太低？**  
- 降低 `resize_factor` 到 0.3
- 增加 `skip_frames` 到 4
- 使用 GPU 加速

**Q: 没有报警声音？**  
声音报警仅在 Windows 系统有效，Linux/Mac 请使用 Webhook 推送。

## 🔧 测试脚本

```bash
# 测试环境安装
python test_setup.py

# 测试行为检测
python test_behavior.py
```

## 🛠️ 开发计划

- [x] 17点姿态估计与跌倒检测
- [x] 行为识别（站/坐/躺）
- [x] Web监控界面
- [ ] 多摄像头支持
- [ ] 手机App推送
- [ ] 人脸识别
- [ ] 健康数据分析

## 📄 许可证

MIT License

## 🙏 致谢

- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics)
- [Flask](https://flask.palletsprojects.com/)
- [OpenCV](https://opencv.org/)

---
<p align="center">Made with ❤️ for elderly care</p>
