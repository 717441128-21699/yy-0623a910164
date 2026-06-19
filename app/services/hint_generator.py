import cv2
import numpy as np
from typing import List, Dict
from datetime import date


class HintGenerator:
    def __init__(self):
        pass

    def calculate_image_diff(self, before_path: str, after_path: str) -> float:
        before = cv2.imread(before_path, cv2.IMREAD_GRAYSCALE)
        after = cv2.imread(after_path, cv2.IMREAD_GRAYSCALE)

        if before is None or after is None:
            return 0.0

        if before.shape != after.shape:
            after = cv2.resize(after, (before.shape[1], before.shape[0]))

        diff = cv2.absdiff(before, after)
        diff_score = float(np.mean(diff))

        return diff_score

    def calculate_alignment_change(self, before_path: str, after_path: str, angle: str) -> Dict:
        before = cv2.imread(before_path, cv2.IMREAD_GRAYSCALE)
        after = cv2.imread(after_path, cv2.IMREAD_GRAYSCALE)

        if before is None or after is None:
            return {"change_level": "unknown", "score": 0}

        if before.shape != after.shape:
            after = cv2.resize(after, (before.shape[1], before.shape[0]))

        diff = cv2.absdiff(before, after)
        _, diff_binary = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
        change_ratio = float(np.sum(diff_binary > 0)) / (diff.shape[0] * diff.shape[1])

        if "正面" in angle or "前牙" in angle or "口内正面" in angle:
            if change_ratio > 0.15:
                change_level = "明显"
            elif change_ratio > 0.08:
                change_level = "中度"
            else:
                change_level = "轻微"
        else:
            if change_ratio > 0.12:
                change_level = "明显"
            elif change_ratio > 0.06:
                change_level = "中度"
            else:
                change_level = "轻微"

        return {
            "change_level": change_level,
            "score": round(change_ratio * 100, 2),
            "change_ratio": change_ratio
        }

    def generate_hint(self, photo_pairs: List[Dict], compare_mode: str,
                       before_date: date, after_date: date) -> str:
        if not photo_pairs:
            return "无可用对比照片"

        hints = []
        changes_summary = {}
        total_change_score = 0.0
        significant_changes = 0

        for pair in photo_pairs:
            angle = pair["angle"]
            analysis = self.calculate_alignment_change(
                pair["before_path"], pair["after_path"], angle
            )
            changes_summary[angle] = analysis
            total_change_score += analysis["score"]

            if analysis["change_level"] in ["明显", "中度"]:
                significant_changes += 1

        avg_change = total_change_score / len(photo_pairs) if photo_pairs else 0

        has_anterior_change = False
        has_posterior_change = False

        for angle, analysis in changes_summary.items():
            if "正面" in angle or "前牙" in angle or "口内正面" in angle:
                if analysis["change_level"] in ["明显", "中度"]:
                    has_anterior_change = True
            if "侧面" in angle or "左侧" in angle or "右侧" in angle:
                if analysis["change_level"] in ["明显", "中度"]:
                    has_posterior_change = True

        if compare_mode == "initial_vs_current":
            hints.append("初诊对比分析：")
        else:
            hints.append("上次复诊对比分析：")

        if has_anterior_change:
            hints.append("前牙排列变化明显，建议医生确认是否进入精细调整阶段")

        if has_posterior_change:
            hints.append("后牙咬合关系有调整迹象，注意咬合稳定性评估")

        if avg_change > 10:
            hints.append(f"整体变化较显著（变化指数 {avg_change:.1f}%），治疗进展良好")
        elif avg_change > 5:
            hints.append(f"整体有一定变化（变化指数 {avg_change:.1f}%），治疗按计划进行")
        else:
            hints.append(f"整体变化较小（变化指数 {avg_change:.1f}%），建议检查矫治器佩戴情况")

        if compare_mode != "initial_vs_current":
            days_diff = (after_date - before_date).days
            if days_diff < 14:
                hints.append("距上次复诊时间较短，变化属于正常范围")
            elif days_diff > 60:
                hints.append("距上次复诊时间较长，建议确认治疗进度")

        if len(photo_pairs) < 6:
            hints.append(f"仅完成 {len(photo_pairs)} 个角度对比，建议补充标准角度照片以获得更全面评估")

        return "。".join(hints) + "。"


hint_generator = HintGenerator()
