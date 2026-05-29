"""Agent 规划器 – 将用户意图转换为工具调用序列"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PlanStep:
    tool: str
    args: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class Plan:
    steps: List[PlanStep] = field(default_factory=list)
    final_note: str = ""


class Planner:
    """规划器：支持 LLM 推理 + 本地关键词双模式"""

    def __init__(self, llm_call: Optional[Any] = None) -> None:
        self._llm = llm_call

    def plan(self, user_input: str, tool_descriptions: str, 
             history: List[Dict[str, str]]) -> Plan:
        if self._llm:
            return self._llm_plan(user_input, tool_descriptions, history)
        return self._keyword_plan(user_input)

    def _llm_plan(self, user_input: str, tool_descriptions: str,
                  history: List[Dict[str, str]]) -> Plan:
        prompt = (
            ""
            f"你是数据标注质检 Agent。可用工具:\n{tool_descriptions}\n\n"
            f"用户: {user_input}\n"
            f"请以 ReAct 格式规划步骤。每次一行: TOOL:工具名 ARGS:json"
        )
        try:
            resp = self._llm([{"role": "user", "content": prompt}])
            return self._parse(resp)
        except Exception:
            return self._keyword_plan(user_input)

    def _parse(self, text: str) -> Plan:
        plan = Plan()
        for line in text.split("\n"):
            if line.startswith("TOOL:"):
                parts = line.split("ARGS:", 1)
                tool = parts[0].replace("TOOL:", "").strip()
                args = {}
                if len(parts) > 1:
                    try:
                        import json
                        args = json.loads(parts[1].strip())
                    except Exception:
                        pass
                plan.steps.append(PlanStep(tool=tool, args=args))
        return plan

    def _keyword_plan(self, text: str) -> Plan:
        plan = Plan()
        t = text.lower()

        if any(k in t for k in ["检查","质检","扫描","跑一下","全检"]):
            plan.steps.append(PlanStep(tool="run_checks", reason="用户要求运行质检"))
        if any(k in t for k in ["异常","问题","错误","明细","细节"]):
            plan.steps.append(PlanStep(tool="get_issues", reason="用户要求查看异常明细"))
        if any(k in t for k in ["报告","报表","导出","总结","结论"]):
            plan.steps.append(PlanStep(tool="get_report", reason="用户要求生成报告"))
        if any(k in t for k in ["样本","第","行","查看","看看"]):
            for w in text.split():
                if w.isdigit():
                    plan.steps.append(PlanStep(tool="get_sample", args={"row_num": int(w)}, reason="查看指定行"))
                    break

        if not plan.steps:
            plan.steps.append(PlanStep(tool="run_checks", reason="默认执行全量质检"))
            plan.steps.append(PlanStep(tool="get_issues", reason="展示异常明细"))
            plan.final_note = "已完成质检，请在右侧面板查看详细结果。"

        return plan
