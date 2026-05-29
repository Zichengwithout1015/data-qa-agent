"""Agent 主循环 – 串联 Planning → Tool-use → 输出"""
import os
import re
from typing import Any, Callable, Dict, List, Optional

import httpx
from dotenv import load_dotenv

from .planner import Planner, Plan, PlanStep
from .tools import create_tools, ToolRegistry

load_dotenv()


class DataQAAgent:
    """数据标注质检 Agent

    流程: 用户上传CSV → Agent理解意图 → 调用工具 → 生成报告
    """

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.tools = create_tools()
        llm = self._call_llm if self.api_key else None
        self.planner = Planner(llm_call=llm)
        self._client: Optional[httpx.Client] = None
        self.conversation: List[Dict[str, str]] = []

    def load_csv(self, csv_text: str) -> str:
        return self.tools.run("parse_csv", csv_text=csv_text)

    def chat(self, user_input: str) -> str:
        self.conversation.append({"role": "user", "content": user_input})
        plan = self.planner.plan(
            user_input,
            self.tools.describe(),
            self.conversation[-6:],
        )

        results: List[str] = []
        for step in plan.steps:
            obs = self.tools.run(step.tool, **step.args)
            results.append(f"[{step.tool}]\n{obs}")

        obs_all = "\n\n".join(results)

        # 尝试用 LLM 润色回复
        if self.api_key:
            response = self._summarize(user_input, obs_all)
        else:
            response = obs_all
            if plan.final_note:
                response += f"\n\n{plan.final_note}"

        self.conversation.append({"role": "assistant", "content": response})
        return response

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        resp = self._client.post(
            f"{self.base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": messages, "temperature": 0.3},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _summarize(self, user_input: str, obs: str) -> str:
        msgs = [
            {"role": "system", "content": (
                "你是数据标注质检助手。用中文简洁汇报，突出关键数字和行动建议。"
                "只需1-2段，不要重复全部细节。"
            )},
            {"role": "user", "content": f"用户指令: {user_input}\n\n执行结果:\n{obs}"},
        ]
        try:
            return self._call_llm(msgs)
        except Exception:
            return obs

    def close(self) -> None:
        if self._client:
            self._client.close()
