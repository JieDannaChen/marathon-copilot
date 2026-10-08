#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.26,<2", "pyyaml"]
# ///
"""Generate weekly training reports using COROS MCP.

Usage: python coros_weekly_report.py --mcp-snapshot response.json --weeks-ago 0
See README_MCP.md for connection configuration."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

# Import sibling module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coros_client import CorosClient, format_pace, format_duration, get_sport_name
from coros_mcp import add_mcp_arguments

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ── Plan Loader ────────────────────────────────────────────────────

def load_training_plan(plan_path: str, week_start: str) -> dict | None:
    """Load training plan and find the matching week.

    Args:
        plan_path: Path to training_cycle_config.yaml.
        week_start: ISO date string of the target week's Monday.

    Returns:
        Dict with planned week info, or None if no match.
    """
    if not HAS_YAML:
        print("Warning: pyyaml not installed, skipping plan comparison",
              file=sys.stderr)
        return None

    with open(plan_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    cycle = config.get("cycle", {})
    cycle_start = datetime.strptime(cycle.get("start_date", "2026-01-01"), "%Y-%m-%d")
    target_monday = datetime.strptime(week_start, "%Y-%m-%d")

    # Calculate which week number this is
    week_delta = (target_monday - cycle_start).days // 7 + 1
    if week_delta < 1:
        return None

    # Walk through phases to find the right one
    phases = config.get("phases", [])
    accumulated_weeks = 0
    target_phase = None
    week_in_phase = 0

    for phase in phases:
        phase_weeks = phase.get("weeks", 0)
        if accumulated_weeks < week_delta <= accumulated_weeks + phase_weeks:
            target_phase = phase
            week_in_phase = week_delta - accumulated_weeks
            break
        accumulated_weeks += phase_weeks

    if not target_phase:
        return None

    # Get planned km for this week
    weekly_km_list = target_phase.get("weekly_km", [])
    planned_km = (weekly_km_list[week_in_phase - 1]
                  if week_in_phase <= len(weekly_km_list) else None)

    intensity = target_phase.get("intensity", {})
    return {
        "cycle_week": week_delta,
        "phase_number": target_phase.get("number"),
        "phase_name": target_phase.get("name"),
        "phase_name_cn": target_phase.get("name_cn"),
        "week_in_phase": week_in_phase,
        "planned_km": planned_km,
        "intensity_distribution": intensity,
        "hr_cap": target_phase.get("hr_cap"),
        "key_focus": target_phase.get("key_focus"),
        "key_workouts": target_phase.get("key_workouts", []),
    }


# ── Training Quality Analysis ──────────────────────────────────────

def classify_run(activity: dict) -> str:
    """Classify a run by intensity based on pace and HR.

    Accepts both raw API format (camelCase) and formatted summary format (snake_case).

    Rough categories:
      - Easy / Recovery: pace >= E pace or HR < 145
      - Long Run: distance >= 15km and pace in E-M zone
      - Tempo / Threshold: pace in T zone and duration > 20min
      - Interval: name contains interval-related keywords
      - Race / Time Trial: name or type suggests competition

    Returns one of: 'easy', 'long_run', 'tempo', 'interval', 'race', 'other'
    """
    name = (activity.get("name") or "").lower()
    # Handle both raw API (distance in meters) and summary (distance_km)
    if "distance_km" in activity:
        distance_km = float(activity.get("distance_km") or 0)
    else:
        distance_km = float(activity.get("distance") or 0) / 1000
    avg_speed = activity.get("avgSpeed", activity.get("avg_speed", 0))  # sec/km
    avg_hr = activity.get("avgHr", activity.get("avg_hr", 0))

    # Keyword-based classification
    race_kw = ["赛", "race", "比赛", "竞赛", "pb", "pr"]
    interval_kw = ["间歇", "interval", "亚索", "yasso", "变速", "fartlek",
                   "400m", "800m", "1000m", "1km"]
    tempo_kw = ["节奏", "tempo", "乳酸", "threshold", "mp", "马拉松配速",
                "巡航"]
    long_kw = ["长距离", "长跑", "lsd", "long run", "拉练"]
    easy_kw = ["轻松", "easy", "恢复", "recovery", "慢跑", "jog"]

    for kw in race_kw:
        if kw in name:
            return "race"
    for kw in interval_kw:
        if kw in name:
            return "interval"
    for kw in tempo_kw:
        if kw in name:
            return "tempo"
    for kw in long_kw:
        if kw in name:
            return "long_run"
    for kw in easy_kw:
        if kw in name:
            return "easy"

    # Heuristic: long run by distance
    if distance_km >= 15:
        return "long_run"

    # Heuristic: by HR zone (rough)
    if avg_hr and avg_hr < 140:
        return "easy"
    if avg_hr and avg_hr > 170:
        return "interval"
    if avg_hr and avg_hr > 155:
        return "tempo"

    return "easy"


def analyze_weekly_data(summary: dict, plan: dict | None = None) -> dict:
    """Analyze weekly training data and compare with plan.

    Args:
        summary: Output from CorosClient.generate_weekly_summary().
        plan: Optional plan data from load_training_plan().

    Returns:
        Structured analysis dict for LLM consumption.
    """
    analysis = {
        "source": summary.get("source"),
        "scope": summary.get("scope"),
        "complete": summary.get("complete"),
        "queried_through": summary.get("queried_through"),
        "period": {
            "start": summary["week_start"],
            "end": summary["week_end"],
        },
        "actual": {
            "total_activities": summary["total_activities"],
            "total_km": summary["total_distance_km"],
            "total_duration": summary["total_duration_str"],
            "run_count": summary["run_count"],
            "run_km": summary["run_distance_km"],
            "run_duration": summary["run_duration_str"],
            "training_load": summary["total_training_load"],
        },
        "run_breakdown": {
            "easy_km": 0.0,
            "tempo_km": 0.0,
            "interval_km": 0.0,
            "long_run_km": 0.0,
            "race_km": 0.0,
        },
        "hr_summary": {
            "avg_hr_range": "--",
            "max_hr_peak": None,
        },
        "activities_detail": [],
    }

    hr_values = []

    for act in summary.get("activities", []):
        sport_type = act.get("type", "其他")
        # classify_run handles both camelCase (raw) and snake_case (summary) fields
        run_type = classify_run(act) if "跑步" in sport_type or "室内跑" in sport_type else "other"

        detail = {
            "label_id": act.get("label_id"),
            "sport_type": act.get("sport_type"),
            "date": act["date"],
            "type": sport_type,
            "run_category": run_type,
            "distance_km": act["distance_km"],
            "duration": act["duration"],
            "pace": act["pace"],
            "avg_hr": act["avg_hr"],
            "max_hr": act["max_hr"],
            "training_load": act["training_load"],
        }
        analysis["activities_detail"].append(detail)

        if run_type != "other":
            km = act["distance_km"]
            key = f"{run_type}_km"
            if key in analysis["run_breakdown"]:
                analysis["run_breakdown"][key] += km

        if act["avg_hr"] and act["avg_hr"] > 0:
            hr_values.append(act["avg_hr"])
        if act["max_hr"] and act["max_hr"] > (analysis["hr_summary"]["max_hr_peak"] or 0):
            analysis["hr_summary"]["max_hr_peak"] = act["max_hr"]

    # Round breakdown values
    for k in analysis["run_breakdown"]:
        analysis["run_breakdown"][k] = round(analysis["run_breakdown"][k], 2)

    # HR range
    if hr_values:
        analysis["hr_summary"]["avg_hr_range"] = (
            f"{min(hr_values)}-{max(hr_values)} bpm"
        )

    # Plan comparison
    if plan:
        analysis["plan"] = plan
        planned_km = plan.get("planned_km")
        if planned_km:
            actual_km = summary["run_distance_km"]
            deviation_km = round(actual_km - planned_km, 2)
            deviation_pct = round(deviation_km / planned_km * 100, 1) if planned_km else 0
            analysis["plan_comparison"] = {
                "planned_km": planned_km,
                "actual_km": actual_km,
                "deviation_km": deviation_km,
                "deviation_pct": deviation_pct,
                "status": (
                    "on_track" if abs(deviation_pct) <= 15
                    else "over" if deviation_pct > 0
                    else "under"
                ),
            }
            # Check intensity distribution
            intensity = plan.get("intensity_distribution", {})
            if intensity and actual_km > 0:
                run_bd = analysis["run_breakdown"]
                analysis["intensity_comparison"] = {
                    "planned": intensity,
                    "actual": {
                        "easy_pct": round(run_bd["easy_km"] / actual_km * 100, 1),
                        "tempo_pct": round(run_bd["tempo_km"] / actual_km * 100, 1),
                        "interval_pct": round(run_bd["interval_km"] / actual_km * 100, 1),
                        "long_run_pct": round(run_bd["long_run_km"] / actual_km * 100, 1),
                    },
                }

    return analysis


# ── Output Formatters ──────────────────────────────────────────────

def format_markdown_report(analysis: dict) -> str:
    """Format analysis as a readable markdown report."""
    lines = []
    period = analysis["period"]
    actual = analysis["actual"]
    breakdown = analysis["run_breakdown"]

    lines.append(f"# 周训练报告 {period['start']} ~ {period['end']}")
    lines.append("")

    lines.append(f'数据源：{analysis.get("source", "未标记")}；范围：跑步；查询至{analysis.get("queried_through")}；整周完整：{analysis.get("complete")}')
    lines.append("")

    # Plan context
    plan = analysis.get("plan")
    if plan:
        lines.append(f"**训练周期**: 第 {plan['cycle_week']} 周 | "
                      f"{plan['phase_name_cn']} (Phase {plan['phase_number']})")
        lines.append(f"**本阶段重点**: {plan['key_focus']}")
        lines.append("")

    # Summary table
    lines.append("## 训练总览")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 总活动数 | {actual['total_activities']} 次 |")
    lines.append(f"| 跑步记录数 | {actual['run_count']} 次 |")
    lines.append(f"| 跑步距离 | {actual['run_km']} km |")
    lines.append(f"| 跑步时长 | {actual['run_duration']} |")
    lines.append(f"| 训练负荷 | {actual['training_load']} |")
    lines.append(f"| 平均心率范围 | {analysis['hr_summary']['avg_hr_range']} |")
    lines.append("")

    # Plan comparison
    comp = analysis.get("plan_comparison")
    if comp:
        status_emoji = {"on_track": "OK", "over": "HIGH", "under": "LOW"}
        lines.append("## 计划 vs 实际")
        lines.append("")
        lines.append(f"- 计划跑量: **{comp['planned_km']} km**")
        lines.append(f"- 实际跑量: **{comp['actual_km']} km**")
        lines.append(f"- 偏差: {comp['deviation_km']:+.1f} km "
                      f"({comp['deviation_pct']:+.1f}%) "
                      f"[{status_emoji.get(comp['status'], comp['status'])}]")
        lines.append("")

    # Intensity breakdown
    lines.append("## 强度分布")
    lines.append("")
    lines.append("| 类型 | 距离 (km) |")
    lines.append("|------|-----------|")
    labels = {
        "easy_km": "轻松跑",
        "tempo_km": "节奏跑",
        "interval_km": "间歇跑",
        "long_run_km": "长距离",
        "race_km": "比赛/测试",
    }
    for key, label in labels.items():
        val = breakdown.get(key, 0)
        if val > 0:
            lines.append(f"| {label} | {val} |")
    lines.append("")

    # Intensity comparison
    ic = analysis.get("intensity_comparison")
    if ic:
        lines.append("### 计划 vs 实际强度比例")
        lines.append("")
        lines.append("| 类型 | 计划 | 实际 |")
        lines.append("|------|------|------|")
        type_map = {
            "easy_pct": ("easy", "轻松跑"),
            "tempo_pct": ("tempo", "节奏跑"),
            "interval_pct": ("interval", "间歇跑"),
            "long_run_pct": ("long_run", "长距离"),
        }
        for key, (_, label) in type_map.items():
            planned_val = ic["planned"].get(key, ic["planned"].get(key.replace("_pct", ""), 0))
            actual_val = ic["actual"].get(key, 0)
            lines.append(f"| {label} | {planned_val}% | {actual_val}% |")
        lines.append("")

    # Daily detail
    lines.append("## 每日活动明细")
    lines.append("")
    for i, act in enumerate(analysis["activities_detail"], 1):
        cat = act.get("run_category", "")
        cat_tag = f" [{cat}]" if cat and cat != "other" else ""
        lines.append(f"### [{i}] {act['date']}")
        lines.append(f"- 类型: {act['type']}{cat_tag}")
        lines.append(f"- 距离: {act['distance_km']} km | 时长: {act['duration']}")
        lines.append(f"- 配速: {act['pace']}/km | HR: {act['avg_hr']} bpm")
        lines.append(f"- 训练负荷: {act['training_load']}")
        lines.append("")

    return "\n".join(lines)


def format_llm_prompt_context(analysis: dict) -> str:
    """Format analysis as a compact context block for LLM training plan generation."""
    lines = []
    period = analysis["period"]
    actual = analysis["actual"]

    lines.append(f"=== 上周训练数据 ({period['start']} ~ {period['end']}) ===")

    plan = analysis.get("plan")
    if plan:
        lines.append(f"周期阶段: {plan['phase_name_cn']} (第{plan['cycle_week']}周)")
        lines.append(f"阶段重点: {plan['key_focus']}")

    lines.append(f"跑步: {actual['run_count']}次, {actual['run_km']}km, "
                  f"{actual['run_duration']}")
    lines.append(f"训练负荷: {actual['training_load']}")
    lines.append(f"心率: {analysis['hr_summary']['avg_hr_range']}, "
                  f"峰值 {analysis['hr_summary']['max_hr_peak']}bpm")

    bd = analysis["run_breakdown"]
    parts = []
    if bd["easy_km"]: parts.append(f"轻松{bd['easy_km']}km")
    if bd["tempo_km"]: parts.append(f"节奏{bd['tempo_km']}km")
    if bd["interval_km"]: parts.append(f"间歇{bd['interval_km']}km")
    if bd["long_run_km"]: parts.append(f"长距离{bd['long_run_km']}km")
    if bd["race_km"]: parts.append(f"比赛{bd['race_km']}km")
    if parts:
        lines.append(f"分布: {', '.join(parts)}")

    comp = analysis.get("plan_comparison")
    if comp:
        lines.append(f"计划偏差: {comp['deviation_km']:+.1f}km ({comp['deviation_pct']:+.1f}%)")

    lines.append("")
    lines.append("详细活动:")
    for act in analysis["activities_detail"]:
        cat = act.get("run_category", "")
        lines.append(f"  {act['date']} | {act['type']} | {act['distance_km']}km | "
                      f"{act['pace']}/km | HR {act['avg_hr']} | 负荷{act['training_load']}"
                      + (f" [{cat}]" if cat and cat != "other" else ""))

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="COROS 周训练分析报告 — 连接手表数据与训练计划",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    add_mcp_arguments(parser)
    parser.add_argument("--weeks-ago", type=int, default=1,
                        help="查询几周前的数据 (0=本周, 1=上周, 默认: 1)")
    parser.add_argument("--plan", help="训练计划配置文件路径 (YAML)")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 格式")
    parser.add_argument("--markdown", action="store_true",
                        help="输出 Markdown 格式")
    parser.add_argument("--llm-context", action="store_true",
                        help="输出 LLM 上下文格式 (紧凑)")
    parser.add_argument("-o", "--output", help="保存到文件")

    args = parser.parse_args()

    client = CorosClient.from_args(args)

    # Fetch data
    print(f"正在获取{'本' if args.weeks_ago == 0 else '上'}周训练数据...",
          file=sys.stderr)
    summary = client.generate_weekly_summary(weeks_ago=args.weeks_ago)

    if summary["total_activities"] == 0:
        print("查询范围内无跑步记录。", file=sys.stderr)
        sys.exit(0)

    # Load plan if provided
    plan = None
    if args.plan:
        plan = load_training_plan(args.plan, summary["week_start"])

    # Analyze
    analysis = analyze_weekly_data(summary, plan)

    # Format output
    if args.json:
        output = json.dumps(analysis, ensure_ascii=False, indent=2)
    elif args.llm_context:
        output = format_llm_prompt_context(analysis)
    else:
        # Default to markdown
        output = format_markdown_report(analysis)

    # Output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"报告已保存到: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
