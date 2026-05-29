"""Agent 工具定义"""
import csv
import io
from typing import Any, Dict, List

from src.qa_engine.rules import RuleEngine, QAResult
from src.qa_engine.reporter import ReportGenerator


class ToolRegistry:
    """工具注册表 – Agent 可调用的工具集合"""

    def __init__(self) -> None:
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._data_cache: List[Dict[str, Any]] = []

    def register(self, name: str, desc: str, func: Any) -> None:
        self._tools[name] = {"description": desc, "func": func}

    def describe(self) -> str:
        return "\n".join(f"- {n}: {d['description']}" for n, d in self._tools.items())

    def run(self, name: str, **kwargs: Any) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"未知工具: {name}"
        try:
            return tool["func"](**kwargs)
        except Exception as e:
            return f"工具执行失败 [{name}]: {e}"


def create_tools() -> ToolRegistry:
    registry = ToolRegistry()
    engine = RuleEngine()

    def parse_csv(csv_text: str) -> str:
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        registry._data_cache = rows
        cols = reader.fieldnames or []
        return f"已解析 {len(rows)} 条数据，字段: {', '.join(cols[:8])}"

    def run_checks() -> str:
        rows = registry._data_cache
        if not rows:
            return "错误: 请先上传 CSV 数据"
        result = engine.check(rows)
        highlights = ReportGenerator.get_highlights(result)
        return "质检完成\n" + "\n".join(f"  • {h}" for h in highlights)

    def get_issues(limit: int = 50) -> str:
        rows = registry._data_cache
        if not rows:
            return "错误: 请先上传 CSV 数据"
        result = engine.check(rows)
        if not result.issues:
            return "✅ 未发现异常"
        lines = [f"共 {len(result.issues)} 条异常，显示前 {min(limit, len(result.issues))} 条:"]
        for issue in result.issues[:limit]:
            lines.append(f"  行{issue.row} [{issue.level}] {issue.column}: {issue.reason}")
        return "\n".join(lines)

    def get_report() -> str:
        rows = registry._data_cache
        if not rows:
            return "错误: 请先上传 CSV 数据"
        result = engine.check(rows)
        return ReportGenerator.to_markdown(result)

    def get_sample(row_num: int) -> str:
        rows = registry._data_cache
        if not rows or row_num < 1 or row_num > len(rows):
            return f"行号 {row_num} 超出范围 (1-{len(rows)})"
        row = rows[row_num - 1]
        return "\n".join(f"  {k}: {v}" for k, v in row.items())

    registry.register("parse_csv",  "解析上传的 CSV 标注数据", parse_csv)
    registry.register("run_checks", "执行质检规则检查", run_checks)
    registry.register("get_issues", "获取异常明细列表", get_issues)
    registry.register("get_report", "生成完整质检 Markdown 报告", get_report)
    registry.register("get_sample", "查看指定行的原始标注数据", get_sample)

    return registry
