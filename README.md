# AI Racing Coach

ACC（Assetto Corsa Competizione）专用 AI 赛车教练。采集实时遥测数据，通过 LLM 生成逐弯驾驶建议报告，并提供实时音频提示。

## 功能现状

| Sprint | 模块 | 状态 |
|--------|------|------|
| S0 | 项目脚手架 | ✅ 完成 |
| S1 | ACC 遥测采集（共享内存） | ✅ 完成 |
| S2 | 赛道建模与弯道检测 | ✅ 完成 |
| S3 | 参考圈对比与错误检测 | ✅ 完成 |
| S4 | LLM 反馈报告生成 | ✅ 完成 |
| S5 | Web UI 与进步追踪 | ✅ 完成 |
| S6 | 实时热路径（制动提示 + 锁轮警报） | ✅ 完成 |

## 环境要求

- Windows 10/11（ACC 共享内存为 Windows 专用）
- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- ACC（Assetto Corsa Competizione）

## 快速开始

```bash
# 安装依赖
uv sync

# 运行测试
uv run pytest

# 实时验证 ACC 连接（需先启动 ACC 并上赛道）
uv run python scripts/check_acc.py

# 启动 Web UI（浏览器访问 http://127.0.0.1:8000）
uv run uvicorn racing_coach.web.app:app --reload --host 127.0.0.1 --port 8000

# 实时热路径：制动点提示 + 锁轮警报（ACC 运行中）
uv run python scripts/hotpath.py --session <session_id> --ref-lap 1
```

## 工作流程

### 录制 + 分析（事后）

```bash
# 1. 上赛道，开始录制（60 Hz）
uv run python scripts/record_session.py
# 退出后打印 session_id

# 2. 分析指定圈次（对比参考圈）
uv run python scripts/analyze_session.py --session <id> --lap 3 --ref-lap 1

# 3. 打开 Web UI 查看报告
#    http://127.0.0.1:8000/progress
```

### 实时热路径

```bash
# 加载参考圈制动点，驾驶时给出音频提示
uv run python scripts/hotpath.py --session <id> --ref-lap 1

# 不需要音效（测试模式）
uv run python scripts/hotpath.py --no-audio
```

## 遥测接口

ACC 通过 Windows 具名共享内存暴露遥测数据，无需第三方 SDK：

| 内存段 | 内容 |
|--------|------|
| `Local\acpmf_physics` | 速度、踏板、转向、G力、转速、挡位 |
| `Local\acpmf_graphics` | 圈号、圈时、赛道位置、车辆坐标 |

## 项目结构

```
src/racing_coach/
  telemetry/     # ACC 数据采集（ACCLiveConnection, ACCParser, TelemetryStorage）
  track/         # 赛道建模与弯道检测
  analysis/      # 参考圈对比与错误分析
  reporting/     # LLM 反馈生成（Moonshot kimi-k2.5）
  web/           # FastAPI Web 服务（报告页 + 进步趋势页）
  hotpath/       # 实时热路径（TelemetryEventStream, BrakePointCue, LockAlertRule）
scripts/
  record_session.py   # 录制遥测数据
  analyze_session.py  # 六步分析管道
  hotpath.py          # 实时热路径入口
  check_acc.py        # ACC 连接验证工具
```

## 开发

```bash
uv run pytest          # 运行测试（221 个）
uv run pytest --cov    # 覆盖率报告
uv run ruff check .    # 代码检查
uv run ruff check --fix .  # 自动修复
```
