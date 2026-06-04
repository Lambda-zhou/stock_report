from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib import error, request

sys.dont_write_bytecode = True


def load_status(status_file: str | None) -> dict[str, Any]:
    if not status_file:
        return {}
    path = Path(status_file)
    if not path.exists():
        return {
            "status": "error",
            "error_type": "FileNotFoundError",
            "error": f"状态文件不存在: {path}",
            "status_file": str(path),
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "error_type": "JSONDecodeError",
            "error": str(exc),
            "status_file": str(path),
        }


def cleanup_temp_status_file(status_file: str | None, status: dict[str, Any], *, dry_run: bool) -> None:
    if not dry_run or not status_file:
        return
    path = Path(status_file)
    if not path.exists() or not path.is_file():
        return
    try:
        resolved = path.resolve()
        cwd = Path.cwd().resolve()
    except OSError:
        return
    if resolved.parent != cwd:
        return
    if not path.name.endswith("_status.json"):
        return
    if status.get("error_type") != "JSONDecodeError":
        return
    try:
        path.unlink()
    except OSError:
        return


def compose_message(status: dict[str, Any], workflow_url: str | None, report_url: str | None, extra_text: str | None, *, simple: bool = False, exit_code: int = 0) -> str:
    if simple:
        mode = (status.get("mode") or "").strip()
        label = {"midday": "盘中", "close": "收盘"}.get(mode, mode or "日报")
        date = (status.get("report_date") or "").strip()
        date_part = f" {date}" if date else ""
        error = status.get("error_type") or status.get("error")
        if exit_code == 1 or (error and exit_code != 2):
            lines = [
                f"❌ A股{label}报告{date_part}生成失败",
                f"⛔ 错误: {error}" if error else "⛔ 未知错误",
            ]
            return "\n".join(lines)
        elif exit_code == 2:
            report_url = report_url or status.get("report_url", "")
            lines = [
                f"⚠️ A股{label}报告{date_part}已出 (数据可能不完整)",
            ]
            if report_url:
                lines.append(f"🔗 查看报告: {report_url}")
            return "\n".join(lines)
        elif report_url:
            lines = [
                f"📊 A股{label}报告{date_part}已出",
                f"🔗 查看完整报告: {report_url}",
            ]
            return "\n".join(lines)
        else:
            return f"📊 A股{label}报告{date_part}已生成"
    lines: list[str] = ["AI Stock Daily Report 任务通知"]
    if status:
        lines.append(f"status: {status.get('status', 'unknown')}")
        if status.get("mode"):
            lines.append(f"mode: {status['mode']}")
        if status.get("report_date"):
            lines.append(f"report_date: {status['report_date']}")
        if status.get("data_completeness") is not None:
            lines.append(f"data_completeness: {status['data_completeness']}%")
        validation = status.get("validation") or {}
        if validation.get("summary"):
            lines.append(f"validation: {validation['summary']}")
        if status.get("output_path"):
            lines.append(f"output_path: {status['output_path']}")
        if status.get("error_type") or status.get("error"):
            lines.append(f"error: {status.get('error_type', 'Error')} - {status.get('error', '')}")
    if workflow_url:
        lines.append(f"workflow: {workflow_url}")
    if report_url:
        lines.append(f"report: {report_url}")
    if extra_text:
        lines.append(extra_text)
    return "\n".join(lines)


def post_text_message(webhook: str, text: str, timeout: int = 20) -> dict[str, Any]:
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="发送飞书机器人通知，供 GitHub Actions 调用。")
    parser.add_argument("--webhook", help="飞书机器人 webhook URL；未提供时默认跳过发送。")
    parser.add_argument("--status-file", help="generate_a_share_daily.py 输出的 JSON 文件路径。")
    parser.add_argument("--workflow-url", help="GitHub Actions run URL。")
    parser.add_argument("--report-url", help="已发布报告地址（如 Pages 链接），可选。")
    parser.add_argument("--extra-text", help="附加说明文本。")
    parser.add_argument("--simple", action="store_true", help="简洁模式：仅发送报告链接。")
    parser.add_argument("--exit-code", type=int, default=0, help="生成脚本退出码: 0=完美, 2=数据不完美, 1=失败")
    parser.add_argument("--dry-run", action="store_true", help="仅打印消息，不实际发送。")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    status = load_status(args.status_file)
    message = compose_message(status, args.workflow_url, args.report_url, args.extra_text, simple=args.simple, exit_code=args.exit_code)

    if args.dry_run or not args.webhook:
        reason = "dry-run" if args.dry_run else "missing webhook"
        print(json.dumps({"status": "skipped", "reason": reason, "message": message}, ensure_ascii=False, indent=2))
        cleanup_temp_status_file(args.status_file, status, dry_run=args.dry_run)
        return 0

    try:
        response = post_text_message(args.webhook, message)
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(json.dumps({"status": "error", "error_type": "HTTPError", "code": exc.code, "detail": detail}, ensure_ascii=False, indent=2))
        return 1
    except Exception as exc:
        print(json.dumps({"status": "error", "error_type": exc.__class__.__name__, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({"status": "sent", "response": response, "message": message}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
