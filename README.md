# 🔍 数据标注质检 Agent

> 基于规则引擎 + LLM 推理的标注数据自动审查系统

## 💡 项目背景

在机器人数据采集工作中（日均 300+ 条视频标注），人工标注经常出现字段缺失、标签冲突、批量复制等问题。本项目构建了一个 **Python 原生 AI Agent**，实现标注数据自动质检，将单次审查时间从 30 分钟降到 5 秒。

## 🧠 技术架构

| 模块 | 说明 |
|------|------|
| 规则引擎 | 6 项自动化检查（字段完整性、类型校验、标签合法性、重复检测、语义冲突、范围检查） |
| Agent 核心 | ReAct 范式：Planning → Tool-use → 结构化输出 |
| LLM 后端 | DeepSeek API（可选，不配也能跑本地规则模式） |
| 前端 | Streamlit 看板，支持 CSV 上传、结果可视化、自然语言交互 |

## 🚀 快速开始

`ash
pip install -r requirements.txt
streamlit run src/ui/dashboard.py
`

浏览器打开 http://localhost:8501，点击「加载示例数据」即可看到效果。

> 不配置 API Key 也能运行，Agent 将使用本地关键词模式。

## 🎮 使用方式

1. 上传 CSV 标注数据（或加载内置示例）
2. 点击「执行全量质检」查看结果
3. 在对话区用自然语言与 Agent 交互

## 📁 项目结构

`
data-qa-agent/
├── src/
│   ├── agent/          # Agent 核心
│   │   ├── core.py     # 主循环
│   │   ├── planner.py  # 意图解析
│   │   └── tools.py    # 工具注册（5 个 Tool）
│   ├── qa_engine/      # 质检引擎
│   │   ├── rules.py    # 规则检查（6 项）
│   │   └── reporter.py # 报告生成
│   └── ui/
│       └── dashboard.py
├── sample_data/
│   └── sample_annotations.csv  # 30条示例（含10+处故意埋的错）
├── requirements.txt
└── README.md
`

## 🔬 质检能力

| 检查项 | 说明 |
|--------|------|
| 字段完整性 | 必填字段是否为空 |
| 类型校验 | confidence 是否为数值 |
| 标签合法性 | 场景/光照等是否在允许范围内 |
| 连续重复 | 连续 N 条完全相同 → 疑似批量复制 |
| 语义冲突 | 如 "night场景 + bright光照" |
| 范围检查 | confidence 是否在 0-1 之间 |

## 📝 License

MIT
