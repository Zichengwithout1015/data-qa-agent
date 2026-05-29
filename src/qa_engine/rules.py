"""标注数据规则检查引擎 – 不依赖 LLM 的快速质检"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class Issue:
    row: int
    column: str
    level: str   # critical / warning / info
    reason: str
    current_value: Any = None


@dataclass
class QAResult:
    total: int = 0
    passed: int = 0
    issues: List[Issue] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)


class RuleEngine:
    """多维规则检查引擎

    检查项:
    1. 必填字段缺失
    2. 数据类型校验
    3. 标签值合法性
    4. 连续重复标注 (疑似批量复制)
    5. 标签冲突 (文件名 vs 标签内容不一致)
    6. 数值范围异常
    """

    # 模拟机器人数据标注的字段定义
    SCHEMA = {
        "image_id":    {"type": "str",  "required": True},
        "scene":       {"type": "str",  "required": True,  "valid": ["indoor", "outdoor", "tunnel", "night"]},
        "surface":     {"type": "str",  "required": True,  "valid": ["flat", "uneven", "stairs", "slope", "gravel"]},
        "lighting":    {"type": "str",  "required": True,  "valid": ["bright", "dim", "dark", "backlight"]},
        "obstacle":    {"type": "str",  "required": False, "valid": ["none", "person", "vehicle", "box", "pole", ""]},
        "drivable":    {"type": "str",  "required": True,  "valid": ["yes", "no", "partial"]},
        "confidence":  {"type": "float","required": False, "min": 0.0, "max": 1.0},
        "annotator":   {"type": "str",  "required": False},
        "remark":      {"type": "str",  "required": False},
    }

    # 语义冲突规则: 场景 x 光照 不应该出现的组合
    CONFLICT_RULES = [
        ("scene=indoor", "lighting=bright", "室内场景罕见强光标注，请确认"),
        ("scene=night",  "lighting=bright", "夜间场景不应标注为bright，怀疑弱光误标"),
        ("scene=tunnel", "lighting=bright", "隧道场景罕见强光，检查是否为出口附近"),
        ("surface=stairs","obstacle=none",  "楼梯场景不应标注无障碍物，安全规范要求"),
    ]

    def check(self, rows: List[Dict[str, Any]]) -> QAResult:
        result = QAResult(total=len(rows))

        for idx, row in enumerate(rows):
            row_ok = True

            # 1. 必填字段检查
            for col, spec in self.SCHEMA.items():
                if spec["required"] and (col not in row or row[col] in (None, "", " ")):
                    result.issues.append(Issue(
                        row=idx + 1, column=col, level="critical",
                        reason=f"必填字段缺失: {col}",
                    ))
                    row_ok = False
                if col not in row:
                    continue
                val = row[col]
                # 跳过空值校验
                if val in (None, "", " "):
                    continue

                # 2. 类型校验
                if spec["type"] == "float":
                    try:
                        float(val)
                    except (ValueError, TypeError):
                        result.issues.append(Issue(
                            row=idx + 1, column=col, level="warning",
                            reason=f"期望数值类型，实际为: {val}",
                            current_value=val,
                        ))
                        row_ok = False
                        continue

                # 3. 标签合法性
                if "valid" in spec and val not in spec["valid"]:
                    result.issues.append(Issue(
                        row=idx + 1, column=col, level="warning",
                        reason=f"非法标签值 '{val}'，允许值: {spec['valid']}",
                        current_value=val,
                    ))
                    row_ok = False

                # 4. 数值范围
                if spec["type"] == "float":
                    try:
                        fv = float(val)
                        if "min" in spec and fv < spec["min"]:
                            result.issues.append(Issue(
                                row=idx + 1, column=col, level="warning",
                                reason=f"{col}={fv} 低于最小值 {spec['min']}",
                            ))
                            row_ok = False
                        if "max" in spec and fv > spec["max"]:
                            result.issues.append(Issue(
                                row=idx + 1, column=col, level="warning",
                                reason=f"{col}={fv} 超过最大值 {spec['max']}",
                            ))
                            row_ok = False
                    except (ValueError, TypeError):
                        pass

            if row_ok:
                result.passed += 1

        # 5. 连续重复检测 (疑似批量复制)
        self._check_duplicates(rows, result)

        # 6. 语义冲突检测
        self._check_conflicts(rows, result)

        # 汇总
        result.summary = {
            "总条数": result.total,
            "合格": result.passed,
            "异常": result.total - result.passed,
            "严重": sum(1 for i in result.issues if i.level == "critical"),
            "警告": sum(1 for i in result.issues if i.level == "warning"),
            "提示": sum(1 for i in result.issues if i.level == "info"),
        }

        return result

    def _check_duplicates(self, rows: List[Dict[str, Any]], result: QAResult) -> None:
        if len(rows) < 3:
            return
        cols = ["scene", "surface", "lighting", "obstacle", "drivable"]
        streak = 0
        prev = None
        for idx, row in enumerate(rows):
            key = tuple(row.get(c, "") for c in cols)
            if key == prev:
                streak += 1
            else:
                if streak >= 3:
                    result.issues.append(Issue(
                        row=idx - streak + 1, column="*",
                        level="info",
                        reason=f"连续 {streak} 条标注完全相同，疑似批量复制 (第 {idx - streak + 1} 到 {idx} 行)",
                    ))
                streak = 1
                prev = key
        if streak >= 3:
            result.issues.append(Issue(
                row=len(rows) - streak + 1, column="*",
                level="info",
                reason=f"连续 {streak} 条标注完全相同，疑似批量复制 (末尾)",
            ))

    def _check_conflicts(self, rows: List[Dict[str, Any]], result: QAResult) -> None:
        for idx, row in enumerate(rows):
            for cond_a, cond_b, reason in self.CONFLICT_RULES:
                col_a, val_a = cond_a.split("=")
                col_b, val_b = cond_b.split("=")
                if row.get(col_a) == val_a and row.get(col_b) == val_b:
                    result.issues.append(Issue(
                        row=idx + 1, column=f"{col_a}+{col_b}",
                        level="warning",
                        reason=f"语义冲突: {reason} (检测到 {cond_a}, {cond_b})",
                    ))
