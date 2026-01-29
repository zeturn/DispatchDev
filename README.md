# Dispatch

成果产出层，面向报告、Dashboard 与 Agent API 的统一出口。

## Overview

- **定位**：成果产出 / 报告 / Dashboard / Agent API
- **上游依赖**：[Vesper](../VesperDev)（分析结果）、[Atlas](../AtlasDev)（图谱数据）
- **编排层**：[Orion](../OrionDev)（中央控制）

## 核心能力

- 报告生成与模板管理
- Dashboard 与可视化前端
- Agent API（供外部 Agent / 自动化消费）
- 导出、订阅与通知

## Repository Structure

```text
Dispatch/
├─ backend/                 # API 与报告引擎
├─ frontend/                # Dashboard 前端
├─ docs-site/               # 文档站（可选）
├─ scripts/                 # 运维与本地开发脚本
├─ docker-compose.yml       # 本地/集成部署
└─ README.md
```

## Status

项目脚手架已创建，待实现。
