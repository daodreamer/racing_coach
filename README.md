# AI Racing Coach

ACC（Assetto Corsa Competizione）专用 AI 赛车教练。采集实时遥测数据，通过 LLM 生成逐弯驾驶建议报告。

## 功能现状

| Sprint | 模块 | 状态 |
|--------|------|------|
| S0 | 项目脚手架 | ✅ 完成 |
| S1 | ACC 遥测采集（共享内存） | ✅ 完成 |
| S2 | 赛道建模与弯道检测 | ✅ 完成 |
| S3 | 参考圈对比与错误检测 | ✅ 完成 |
| S4 | LLM 反馈报告生成 | ✅ 完成 |
| S5 | Web UI 与进步追踪 | 🔜 待开发 |

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
```

## 遥测接口

ACC 通过 Windows 具名共享内存暴露遥测数据，无需第三方 SDK：

| 内存段 | 内容 |
|--------|------|
| `Local\acpmf_physics` | 速度、踏板、转向、G力、转速、挡位 |
| `Local\acpmf_graphics` | 圈号、圈时、赛道位置 |

## 项目结构

```
src/racing_coach/
  telemetry/     # ACC 数据采集（ACCLiveConnection, ACCParser）
  track/         # 赛道建模与弯道检测
  analysis/      # 参考圈对比与错误分析
  reporting/     # LLM 反馈生成
scripts/
  check_acc.py   # 实时遥测验证工具
```
