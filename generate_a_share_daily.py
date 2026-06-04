from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import urllib.request
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


def check_dedup(output_dir: str | Path, mode: str, date: str) -> bool:
    """检查今日该模式是否已成功发送过，返回 True 表示应跳过。"""
    marker = Path(output_dir) / f".sent_{mode}_{date}"
    if marker.exists():
        print(f"去重跳过：{marker.name} 已存在，今日 {mode} 已成功发送。")
        return True
    return False


def write_dedup_marker(output_dir: str | Path, mode: str, date: str) -> None:
    """写入去重标记文件。"""
    marker = Path(output_dir) / f".sent_{mode}_{date}"
    marker.write_text(datetime.now().isoformat(), encoding="utf-8")


def send_feishu(webhook_url: str, title: str, report_url: str | None = None,
                exit_code: int = 0, error_msg: str | None = None) -> bool:
    """发送飞书通知。exit_code: 0=成功, 2=不完整, 1=失败。"""
    if not webhook_url:
        print("飞书通知跳过：未配置 webhook。")
        return False

    if exit_code == 1:
        status_icon = "❌"
        status_text = "报告生成失败"
    elif exit_code == 2:
        status_icon = "⚠️"
        status_text = "报告已生成（数据可能不完整）"
    else:
        status_icon = "📊"
        status_text = "报告已生成"

    content = f"{status_icon} {title}\n{status_text}"
    if report_url:
        content += f"\n👉 {report_url}"
    if error_msg:
        content += f"\n错误：{error_msg}"

    payload = json.dumps({"msg_type": "text", "content": {"text": content}}).encode("utf-8")
    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print(f"飞书通知已发送：{status_text}")
                return True
            print(f"飞书通知失败：HTTP {resp.status}")
            return False
    except Exception as e:
        print(f"飞书通知异常：{e}")
        return False


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
    parser.add_argument("--feishu-webhook", default=os.environ.get("FEISHU_WEBHOOK_URL"),
                        help="飞书 Webhook 地址，默认从环境变量 FEISHU_WEBHOOK_URL 读取。")
    parser.add_argument("--report-url", default=os.environ.get("REPORT_URL"),
                        help="报告在线地址，用于飞书通知中附带链接。")
    parser.add_argument("--no-dedup", action="store_true",
                        help="禁用幂等去重，强制重新生成并发送通知。")
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
    now = datetime.now()
    selected_mode = resolve_mode(args.mode, now)
    date_value = args.date or now.strftime("%Y-%m-%d")

    # 幂等去重：今日该模式已发送则跳过
    if not args.no_dedup and check_dedup(args.output_dir, selected_mode, date_value):
        return 0

    try:
        result = generate(args.mode, args.date, args.output_dir, strict=args.strict)
        persist_result_file(result, args.output_dir)
        emit_result(result, args.json)
        exit_code = 0 if result["validation"]["ok"] else 2

        # 写入去重标记 + 发送飞书通知
        write_dedup_marker(args.output_dir, result["mode"], result["report_date"])
        send_feishu(
            args.feishu_webhook or "",
            f"{result['success_message']} {result['report_date']}",
            report_url=args.report_url,
            exit_code=exit_code,
        )
        return exit_code
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
        send_feishu(
            args.feishu_webhook or "",
            f"报告生成失败 {date_value}",
            exit_code=1,
            error_msg=str(exc),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
