"""质检报告生成器"""
from typing import Any, Dict, List

from .rules import QAResult, Issue


class ReportGenerator:
    """生成 Markdown / JSON 格式的质检报告"""

    @staticmethod
    def to_markdown(result: QAResult) -> str:
        lines = [
            "# 📊 标注数据质检报告",
            "",
            "## 📈 总览",
            "",
        ]
        for k, v in result.summary.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

        if result.issues:
            lines.append("## ⚠️ 异常明细")
            lines.append("")
            lines.append("| # | 行号 | 字段 | 级别 | 原因 |")
            lines.append("|---|---|---|---|---|")
            for i, issue in enumerate(result.issues[:50], 1):
                lines.append(f"| {i} | {issue.row} | {issue.column} | {issue.level} | {issue.reason} |")
            if len(result.issues) > 50:
                lines.append(f"| ... | ... | ... | ... | 还有 {len(result.issues) - 50} 条异常，请查看完整报告 |")

        lines.append("")
        lines.append(f"> 自动生成于 Agent 质检引擎")

        return "\n".join(lines)

    @staticmethod
    def to_dict(result: QAResult) -> Dict[str, Any]:
        return {
            "summary": result.summary,
            "issues": [
                {"row": i.row, "column": i.column, "level": i.level, "reason": i.reason}
                for i in result.issues
            ],
        }

    @staticmethod
    def get_highlights(result: QAResult) -> List[str]:
        """生成 LLM 可用的摘要要点"""
        highlights = [
            f"总数据 {result.total} 条，合格 {result.passed} 条 ({result.passed/max(result.total,1)*100:.1f}%)",
        ]
        if result.summary.get("严重", 0) > 0:
            highlights.append(f"严重问题 {result.summary['严重']} 条，需立即修复")
        if result.summary.get("警告", 0) > 0:
            highlights.append(f"警告级问题 {result.summary['警告']} 条，建议复核")
        dupes = [i for i in result.issues if "批量复制" in i.reason]
        if dupes:
            highlights.append(f"发现 {len(dupes)} 处批量复制嫌疑")
        conflicts = [i for i in result.issues if "语义冲突" in i.reason]
        if conflicts:
            highlights.append(f"发现 {len(conflicts)} 处语义冲突")
        return highlights
