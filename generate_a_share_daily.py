from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True


MODE_CONFIG = {
    "close": {
        "module": "generate_a_share_report",
        "builder": "build_report",
        "prefix": "A股收盘日报",
        "success": "日报生成成功",
        "min_completeness": 95,
    },
    "midday": {
        "module": "generate_a_share_midday_report",
        "builder": "build_midday_report",
        "prefix": "A股午盘日报",
        "success": "午盘日报生成成功",
        "min_completeness": 90,
    },
}


def resolve_mode(mode: str, now: datetime) -> str:
    if mode != "auto":
        return mode
    return "midday" if now.hour < 15 else "close"


def normalize_date(report_date: str | None, now: datetime) -> str:
    date_value = report_date or now.strftime("%Y-%m-%d")
    datetime.strptime(date_value, "%Y-%m-%d")
    return date_value


def validate_result(result: dict[str, Any], html_doc: str, strict: bool) -> dict[str, Any]:
    checks = dict((result.get("data_quality") or {}).get("checks") or {})
    missing_count = (result.get("data_quality") or {}).get("missing_count")
    completeness = result.get("data_completeness")
    threshold = result.get("strict_threshold")
    output_path = Path(result["output_path"])

    validation_checks = {
        "output_exists": output_path.exists(),
        "date_present": result["report_date"] in html_doc,
        "completeness_present": completeness is not None,
        "threshold_met": completeness is not None and threshold is not None and completeness >= threshold,
    }
    if checks:
        validation_checks.update(checks)

    failed_checks = [name for name, ok in validation_checks.items() if not ok]
    ok = not failed_checks if strict else validation_checks["output_exists"] and validation_checks["date_present"]
    summary = (
        f"strict校验通过（阈值 {threshold}%）"
        if ok and strict
        else "基础校验通过"
        if ok
        else f"校验失败：{', '.join(failed_checks)}"
    )

    return {
        "strict": strict,
        "ok": ok,
        "summary": summary,
        "failed_checks": failed_checks,
        "checks": validation_checks,
        "missing_count": missing_count,
        "strict_threshold": threshold,
    }


def generate(
    mode: str,
    report_date: str | None = None,
    output_dir: str | Path = "ga_out",
    *,
    strict: bool = False,
) -> dict[str, Any]:
    now = datetime.now()
    selected_mode = resolve_mode(mode, now)
    config = MODE_CONFIG[selected_mode]
    date_value = normalize_date(report_date, now)

    module = importlib.import_module(config["module"])
    # Existing generators read REPORT_DATE at render time; overriding it here keeps
    # old scripts reusable while allowing this stable runner to control the date.
    setattr(module, "REPORT_DATE", date_value)
    html_doc, stats = getattr(module, config["builder"])()

    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    output_path = output_dir_path / f"{config['prefix']}_{date_value}.html"
    output_path.write_text(html_doc, encoding="utf-8")

    result = {
        "status": "success",
        "mode": selected_mode,
        "mode_requested": mode,
        "report_date": date_value,
        "output_path": str(output_path),
        "generated_at": stats.get("generated_at"),
        "data_completeness": stats.get("data_completeness"),
        "trading_day": stats.get("trading_day"),
        "success_message": config["success"],
        "strict_threshold": config["min_completeness"],
        "data_quality": stats.get("data_quality"),
    }
    result["validation"] = validate_result(result, html_doc, strict=strict)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="复用既有模板生成 A 股午盘/收盘 HTML 日报。")
    parser.add_argument(
        "--mode",
        choices=["auto", "midday", "close"],
        default="auto",
        help="报告模式：auto 在 15:00 前生成午盘版，15:00 后生成收盘版。",
    )
    parser.add_argument("--date", help="报告日期，格式 YYYY-MM-DD；默认使用当天。")
    parser.add_argument("--output-dir", default="ga_out", help="HTML 输出目录，默认 ga_out。")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出生成结果，便于自动化读取。")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="启用严格校验：HTML 文件存在、日期命中，且数据完整度达到模式阈值（午盘>=90，收盘>=95）。",
    )
    return parser


def emit_result(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"{result['success_message']}：")
    print(f"文件路径：{result['output_path']}")
    print(f"报告日期：{result['report_date']}")
    print(f"生成时间：{result['generated_at']}")
    print(f"数据完整度：{result['data_completeness']}%")
    print(f"复用模式：{result['mode']}")
    print(f"校验摘要：{result['validation']['summary']}")


def persist_result_file(result: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    result_path = output_dir_path / "result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result_path


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = generate(args.mode, args.date, args.output_dir, strict=args.strict)
        persist_result_file(result, args.output_dir)
        emit_result(result, args.json)
        return 0 if result["validation"]["ok"] else 2
    except Exception as exc:
        error_result = {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "mode_requested": args.mode,
            "report_date": args.date,
            "output_dir": args.output_dir,
            "strict": args.strict,
        }
        persist_result_file(error_result, args.output_dir)
        if args.json:
            print(json.dumps(error_result, ensure_ascii=False, indent=2))
        else:
            print("日报生成失败：")
            print(f"错误类型：{error_result['error_type']}")
            print(f"错误信息：{error_result['error']}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
