# 数据标注质检 Agent - Streamlit 看板
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.agent.core import DataQAAgent
from src.qa_engine.rules import RuleEngine
from src.qa_engine.reporter import ReportGenerator

st.set_page_config(page_title="标注质检 Agent", layout="wide")


if "agent" not in st.session_state:
    st.session_state.agent = DataQAAgent()
if "result" not in st.session_state:
    st.session_state.result = None
if "csv_text" not in st.session_state:
    st.session_state.csv_text = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

agent = st.session_state.agent


# ---- 侧边栏 ----
with st.sidebar:
    st.title("标注质检 Agent")
    st.markdown("---")

    api_key = st.text_input("DeepSeek API Key（可选）", type="password", placeholder="留空使用本地模式")
    if api_key:
        agent.api_key = api_key

    st.markdown("---")
    st.subheader("数据加载")
    uploaded = st.file_uploader("上传标注 CSV", type=["csv"])
    if uploaded:
        text = uploaded.read().decode("utf-8")
        st.session_state.csv_text = text
        agent.load_csv(text)
        st.success("已加载")

    if st.button("加载示例数据", use_container_width=True):
        p = os.path.join(os.path.dirname(__file__), "..", "..", "sample_data", "sample_annotations.csv")
        p = os.path.abspath(p)
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        st.session_state.csv_text = text
        agent.load_csv(text)
        st.success("已加载 30 条示例标注数据")
        st.rerun()

    if st.button("清空", use_container_width=True):
        st.session_state.result = None
        st.session_state.csv_text = ""
        st.session_state.chat_history = []
        agent.conversation = []
        st.rerun()

    mode_label = "模式: LLM" if agent.api_key else "模式: 本地规则"
    st.caption(mode_label)

    st.markdown("---")
    st.subheader("快捷指令")
    cmds = ["帮我全量检查一下标注数据", "只看严重问题", "生成质检报告", "查看第7行数据"]
    for i, cmd in enumerate(cmds):
        if st.button(cmd, key=f"quick_{i}", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": cmd})
            with st.spinner("Agent 分析中..."):
                resp = agent.chat(cmd)
            st.session_state.chat_history.append({"role": "assistant", "content": resp})
            engine = RuleEngine()
            if agent.tools._data_cache:
                st.session_state.result = engine.check(agent.tools._data_cache)
            st.rerun()


# ---- 主区域 ----
st.title("数据标注质检 Agent")
st.caption("基于规则引擎 + LLM 推理的机器人标注数据自动审查系统")

if st.session_state.csv_text:
    with st.expander("原始数据预览", expanded=False):
        try:
            df = pd.read_csv(pd.io.common.StringIO(st.session_state.csv_text))
            st.dataframe(df, use_container_width=True, height=200)
        except Exception:
            st.warning("无法解析 CSV")

    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button("执行全量质检", type="primary", use_container_width=True):
            engine = RuleEngine()
            st.session_state.result = engine.check(agent.tools._data_cache)
            st.rerun()

    result = st.session_state.result
    if result:
        st.markdown("---")
        st.subheader("质检结果")

        cols = st.columns(5)
        labels = [
            ("总条数", result.total),
            ("合格行", result.passed),
            ("异常行", result.summary.get("异常", 0)),
            ("问题总数", len(result.issues)),
            ("通过率", f"{result.passed/max(result.total,1)*100:.0f}%"),
        ]
        for (name, val), col in zip(labels, cols):
            col.metric(name, val)

        if result.issues:
            st.subheader("异常明细")
            affected = len(set(i.row for i in result.issues))
            st.caption(f"共 {len(result.issues)} 个问题，分布在 {affected} 行数据中（一行可能有多个问题）")
            rows = []
            for iss in result.issues:
                level_map = {"critical": "严重", "warning": "警告", "info": "提示"}
                rows.append({
                    "级别": level_map.get(iss.level, iss.level),
                    "行号": iss.row,
                    "字段": iss.column,
                    "原因": iss.reason,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("请从左侧上传 CSV 或加载示例数据以开始")

st.markdown("---")
st.subheader("与 Agent 对话")
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.text(msg["content"])

if prompt := st.chat_input("输入指令，如：帮我检查数据、导出报告..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.spinner("Agent 分析中..."):
        resp = agent.chat(prompt)
    st.session_state.chat_history.append({"role": "assistant", "content": resp})
    engine = RuleEngine()
    if agent.tools._data_cache:
        st.session_state.result = engine.check(agent.tools._data_cache)
    st.rerun()
