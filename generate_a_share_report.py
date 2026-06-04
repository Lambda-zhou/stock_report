from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta
import html as html_lib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable

import requests


MISSING = "暂无可靠数据"
REPORT_DATE = datetime.now().strftime("%Y-%m-%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

INDEX_SYMBOLS = OrderedDict(
    [
        ("上证指数", "sh000001"),
        ("深证成指", "sz399001"),
        ("创业板指", "sz399006"),
        ("科创50", "sh000688"),
        ("沪深300", "sh000300"),
        ("上证50", "sh000016"),
        ("中证500", "sh000905"),
        ("中证1000", "sh000852"),
    ]
)

ETF_SYMBOLS = OrderedDict(
    [
        ("通信ETF", "sh515880"),
        ("芯片ETF", "sh512480"),
        ("软件ETF", "sh515230"),
        ("人工智能ETF", "sh515070"),
        ("黄金ETF", "sh518880"),
        ("有色ETF", "sh512400"),
        ("煤炭ETF", "sh515220"),
        ("电力ETF", "sz159611"),
        ("化工ETF", "sh516020"),
        ("银行ETF", "sh512800"),
        ("国债ETF", "sh511010"),
        ("30年国债ETF", "sh511090"),
        ("科创50ETF", "sh588000"),
    ]
)

FOCUS_ETFS = {
    "通信ETF",
    "芯片ETF",
    "软件ETF",
    "人工智能ETF",
    "黄金ETF",
    "有色ETF",
    "煤炭ETF",
    "电力ETF",
    "化工ETF",
    "银行ETF",
    "国债ETF",
    "30年国债ETF",
}


# ---------------------------------------------------------------------------
# 板块配置：优先从环境变量读取，未设置则使用内置默认值
# GitHub Actions 中通过 Repository Variable "FOCUS_GROUPS_JSON" 配置
# JSON 格式: {"板块名": {"个股名": "sz000001", ...}, ...}
# ---------------------------------------------------------------------------

_DEFAULT_FOCUS_GROUPS = OrderedDict(
    [
        (
            "科技硬件 / AI算力",
            OrderedDict(
                [
                    ("中际旭创", "sz300308"),
                    ("新易盛", "sz300502"),
                    ("海光信息", "sh688041"),
                    ("寒武纪", "sh688256"),
                    ("沪电股份", "sz002463"),
                    ("工业富联", "sh601138"),
                    ("胜宏科技", "sz300476"),
                    ("深南电路", "sz002916"),
                ]
            ),
        ),
        (
            "通信设备 / 光模块",
            OrderedDict(
                [
                    ("中际旭创", "sz300308"),
                    ("新易盛", "sz300502"),
                    ("天孚通信", "sz300394"),
                    ("中兴通讯", "sz000063"),
                    ("烽火通信", "sh600498"),
                    ("长飞光纤", "sh601869"),
                    ("亨通光电", "sh600487"),
                    ("光迅科技", "sz002281"),
                ]
            ),
        ),
        (
            "互联网软件 / 信创",
            OrderedDict(
                [
                    ("科大讯飞", "sz002230"),
                    ("金山办公", "sh688111"),
                    ("用友网络", "sh600588"),
                    ("恒生电子", "sh600570"),
                    ("浪潮信息", "sz000977"),
                    ("中科曙光", "sh603019"),
                    ("中国软件", "sh600536"),
                    ("诚迈科技", "sz300598"),
                ]
            ),
        ),
        (
            "有色金属 / 黄金",
            OrderedDict(
                [
                    ("紫金矿业", "sh601899"),
                    ("山东黄金", "sh600547"),
                    ("天齐锂业", "sz002466"),
                    ("北方稀土", "sh600111"),
                    ("洛阳钼业", "sh603993"),
                    ("中金黄金", "sh600489"),
                    ("华友钴业", "sh603799"),
                    ("盛新锂能", "sz002240"),
                ]
            ),
        ),
        (
            "资源能源 / 高股息",
            OrderedDict(
                [
                    ("中国神华", "sh601088"),
                    ("中国石油", "sh601857"),
                    ("中国海油", "sh600938"),
                    ("长江电力", "sh600900"),
                    ("陕西煤业", "sh601225"),
                    ("兖矿能源", "sh600188"),
                    ("中煤能源", "sh601898"),
                    ("中国石化", "sh600028"),
                ]
            ),
        ),
        (
            "电力 / 电网",
            OrderedDict(
                [
                    ("长江电力", "sh600900"),
                    ("国电南瑞", "sh600406"),
                    ("中国核电", "sh601985"),
                    ("特变电工", "sh600089"),
                    ("华能国际", "sh600011"),
                    ("国投电力", "sh600886"),
                    ("三峡能源", "sh600905"),
                    ("正泰电器", "sh601877"),
                ]
            ),
        ),
        (
            "化工材料",
            OrderedDict(
                [
                    ("万华化学", "sh600309"),
                    ("华鲁恒升", "sh600426"),
                    ("卫星化学", "sz002648"),
                    ("荣盛石化", "sz002493"),
                    ("恒力石化", "sh600346"),
                    ("东方盛虹", "sz000301"),
                    ("宝丰能源", "sh600989"),
                    ("扬农化工", "sh600486"),
                ]
            ),
        ),
        (
            "银行 / 国债",
            OrderedDict(
                [
                    ("工商银行", "sh601398"),
                    ("招商银行", "sh600036"),
                    ("农业银行", "sh601288"),
                    ("银行ETF", "sh512800"),
                    ("国债ETF", "sh511010"),
                    ("30年国债ETF", "sh511090"),
                ]
            ),
        ),
    ]
)

_DEFAULT_FOCUS_INDUSTRY_KEYWORDS = {
    "科技硬件 / AI算力": ["半导体", "元器件", "通信设备", "计算机设备", "互联网", "软件"],
    "通信设备 / 光模块": ["通信", "光学", "电子元器件"],
    "互联网软件 / 信创": ["软件", "互联网", "计算机应用", "信息服务"],
    "有色金属 / 黄金": ["有色", "黄金", "金属", "稀土"],
    "资源能源 / 高股息": ["煤炭", "石油", "钢铁", "电信运营"],
    "电力 / 电网": ["电力", "电气设备", "输变电"],
    "化工材料": ["化工", "化学", "塑料", "化纤"],
    "银行 / 国债": ["银行", "保险", "证券"],
}


def _load_focus_config():
    """从环境变量加载板块配置；未设置则使用内置默认值。"""
    groups_json = os.environ.get("FOCUS_GROUPS_JSON")
    if not groups_json:
        return _DEFAULT_FOCUS_GROUPS, _DEFAULT_FOCUS_INDUSTRY_KEYWORDS
    try:
        raw = json.loads(groups_json)
        groups = OrderedDict((k, OrderedDict(v)) for k, v in raw.items())
        kw_json = os.environ.get("FOCUS_KEYWORDS_JSON")
        if kw_json:
            keywords = json.loads(kw_json)
        else:
            # 从组名自动拆关键词（斜杠分隔）
            keywords = {}
            for name in groups:
                parts = [p.strip() for p in name.replace("/", "/").split("/")]
                keywords[name] = [p for p in parts if p]
        return groups, keywords
    except (json.JSONDecodeError, TypeError) as exc:
        print(f"[warn] FOCUS_GROUPS_JSON 解析失败，使用默认值: {exc}", file=sys.stderr)
        return _DEFAULT_FOCUS_GROUPS, _DEFAULT_FOCUS_INDUSTRY_KEYWORDS


FOCUS_GROUPS, FOCUS_INDUSTRY_KEYWORDS = _load_focus_config()


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    if text in {"", "-", "None", MISSING}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def esc(value: Any) -> str:
    return html_lib.escape(str(MISSING if value is None else value), quote=True)


def fmt_num(value: Any, digits: int = 2) -> str:
    num = _safe_float(value)
    if num is None:
        return str(value) if isinstance(value, str) and value else MISSING
    return f"{num:,.{digits}f}"


def fmt_pct(value: Any) -> str:
    num = _safe_float(value)
    if num is None:
        return MISSING
    return f"{num:+.2f}%"


def fmt_yuan_to_yi(value: Any) -> str:
    num = _safe_float(value)
    if num is None:
        return MISSING
    return f"{num / 100_000_000:,.2f}亿元"


def pct_class(value: Any) -> str:
    num = _safe_float(value)
    if num is None:
        return "missing"
    if num > 0:
        return "up"
    if num < 0:
        return "down"
    return "neutral"


def market_code(symbol: str) -> str:
    symbol = symbol.lower()
    if symbol.startswith("sh"):
        return f"{symbol[2:]}.SH"
    if symbol.startswith("sz"):
        return f"{symbol[2:]}.SZ"
    if symbol.startswith("bj"):
        return f"{symbol[2:]}.BJ"
    return symbol.upper()


def quote_name(symbol: str, quote: dict[str, Any] | None = None) -> str:
    name = (quote or {}).get("name") or market_code(symbol)
    return f"{name}（{market_code(symbol)}）"


def avg_pct(symbols: list[str], quotes: dict[str, dict[str, Any]]) -> float | None:
    values = [_safe_float((quotes.get(symbol) or {}).get("pct")) for symbol in symbols]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return sum(values) / len(values)


def chip(label: str, class_name: str = "status-neutral") -> str:
    return f'<span class="status-chip {esc(class_name)}">{esc(label)}</span>'


def risk_chip(level: str) -> str:
    class_name = "risk-high" if "高" in level else "risk-mid"
    return chip(level, class_name)


def bar(value: Any, max_abs: float | None = None) -> str:
    num = _safe_float(value)
    if num is None:
        return f'<span class="missing">{MISSING}</span>'
    max_value = max(abs(max_abs or 0), abs(num), 0.01)
    width = min(100, abs(num) / max_value * 100)
    class_name = "up" if num > 0 else "down" if num < 0 else "neutral"
    return (
        f'<div class="bar {class_name}"><span style="width:{width:.1f}%"></span>'
        f"<b>{fmt_pct(num)}</b></div>"
    )


def card(title: str, value: str, sub: str, tone: str = "blue") -> str:
    return (
        f'<div class="metric-card {esc(tone)}">'
        f'<div class="metric-title">{esc(title)}</div>'
        f'<div class="metric-value">{esc(value)}</div>'
        f'<div class="metric-sub">{esc(sub)}</div>'
        "</div>"
    )


def section(section_id: str, title: str, body: str) -> str:
    return (
        f'<section id="{esc(section_id)}" class="section-anchor">'
        '<details class="section-card" open>'
        f"<summary><h2>{esc(title)}</h2><span class=\"chev\">展开 / 收起</span></summary>"
        f'<div class="section-body">{body}</div>'
        "</details></section>"
    )


def _render_cell(cell: Any) -> tuple[str, str]:
    class_name = ""
    value = cell
    if isinstance(cell, tuple):
        value = cell[0]
        class_name = str(cell[1])
    if value == MISSING:
        class_name = f"{class_name} missing".strip()
    if isinstance(value, str) and value.lstrip().startswith("<"):
        return value, class_name
    return esc(value), class_name


def table(headers: list[str], rows: list[list[Any]], class_names: str = "") -> str:
    head_html = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body_parts = []
    for row in rows:
        cells = []
        for cell in row:
            content, class_name = _render_cell(cell)
            class_attr = f' class="{esc(class_name)}"' if class_name else ""
            cells.append(f"<td{class_attr}>{content}</td>")
        body_parts.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<div class="table-wrap">'
        f'<table class="{esc(class_names)}"><thead><tr>{head_html}</tr></thead>'
        f"<tbody>{''.join(body_parts)}</tbody></table></div>"
    )


def judgement(value: Any) -> str:
    num = _safe_float(value)
    if num is None:
        return "等待数据"
    if num >= 3:
        return "强势"
    if num > 0:
        return "偏强"
    if num <= -3:
        return "弱势"
    if num < 0:
        return "偏弱"
    return "震荡"


def trend_text(quote: dict[str, Any] | None) -> str:
    if not quote:
        return "等待数据"
    pct = _safe_float(quote.get("pct"))
    close = _safe_float(quote.get("close"))
    open_price = _safe_float(quote.get("open"))
    if pct is None:
        return "等待数据"
    if pct > 0 and close is not None and open_price is not None and close >= open_price:
        return "收盘偏强"
    if pct > 0:
        return "红盘震荡"
    if pct < 0 and close is not None and open_price is not None and close <= open_price:
        return "收盘偏弱"
    if pct < 0:
        return "绿盘修复"
    return "窄幅震荡"


def status_class(text: str) -> str:
    if "强" in text:
        return "status-strong"
    if "弱" in text:
        return "status-risk"
    if "等待" in text:
        return "data-missing"
    return "status-watch"


def _parse_sina_quote(symbol: str, raw: str) -> dict[str, Any] | None:
    parts = raw.split(",")
    if len(parts) < 32 or not parts[0]:
        return None
    open_price = _safe_float(parts[1])
    prev_close = _safe_float(parts[2])
    close = _safe_float(parts[3])
    high = _safe_float(parts[4])
    low = _safe_float(parts[5])
    volume = _safe_float(parts[8])
    amount = _safe_float(parts[9])
    pct = None
    if close is not None and prev_close:
        pct = (close - prev_close) / prev_close * 100
    date_value = parts[30] if len(parts) > 30 else ""
    time_value = parts[31] if len(parts) > 31 else ""
    return {
        "symbol": symbol.lower(),
        "name": parts[0],
        "open": open_price,
        "prev_close": prev_close,
        "close": close,
        "high": high,
        "low": low,
        "volume": volume,
        "amount": amount,
        "pct": pct,
        "date": date_value,
        "time": time_value,
        "source": "新浪财经 hq.sinajs.cn",
    }


def _eastmoney_secid(symbol: str) -> str:
    symbol = symbol.lower()
    if symbol.startswith("sh"):
        return f"1.{symbol[2:]}"
    if symbol.startswith("sz"):
        return f"0.{symbol[2:]}"
    if symbol.startswith("bj"):
        return f"0.{symbol[2:]}"
    return symbol


def _fetch_eastmoney_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    secid_to_symbol = {_eastmoney_secid(symbol): symbol.lower() for symbol in symbols}
    fields = "f12,f13,f14,f2,f3,f5,f6,f15,f16,f17,f18,f124"
    for chunk in _chunks(list(secid_to_symbol), 80):
        try:
            response = requests.get(
                "https://push2.eastmoney.com/api/qt/ulist.np/get",
                params={"fltt": "2", "invt": "2", "fields": fields, "secids": ",".join(chunk)},
                headers=HEADERS,
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            continue
        for row in (payload.get("data") or {}).get("diff") or []:
            market = row.get("f13")
            prefix = "sh" if market == 1 else "sz"
            symbol = f"{prefix}{row.get('f12')}".lower()
            ts = row.get("f124")
            dt = datetime.fromtimestamp(ts) if isinstance(ts, int) and ts > 0 else None
            result[symbol] = {
                "symbol": symbol,
                "name": row.get("f14"),
                "open": _safe_float(row.get("f17")),
                "prev_close": _safe_float(row.get("f18")),
                "close": _safe_float(row.get("f2")),
                "high": _safe_float(row.get("f15")),
                "low": _safe_float(row.get("f16")),
                "volume": _safe_float(row.get("f5")),
                "amount": _safe_float(row.get("f6")),
                "pct": _safe_float(row.get("f3")),
                "date": dt.strftime("%Y-%m-%d") if dt else "",
                "time": dt.strftime("%H:%M:%S") if dt else "",
                "source": "东方财富 push2",
            }
    return result


def fetch_sina_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    unique_symbols = list(OrderedDict.fromkeys(symbol.lower() for symbol in symbols))
    quotes: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(unique_symbols, 80):
        try:
            response = requests.get(
                "https://hq.sinajs.cn/list=" + ",".join(chunk),
                headers=HEADERS,
                timeout=20,
            )
            response.encoding = "gbk"
            response.raise_for_status()
        except Exception:
            continue
        for symbol, raw in re.findall(r'var hq_str_([a-z0-9_]+)="(.*?)";', response.text, re.S):
            quote = _parse_sina_quote(symbol, raw)
            if quote:
                quotes[symbol.lower()] = quote

    missing = [symbol for symbol in unique_symbols if symbol not in quotes]
    if missing:
        quotes.update(_fetch_eastmoney_quotes(missing))
    return quotes


def fetch_bankuai(kind: str = "industry") -> list[dict[str, Any]]:
    try:
        response = requests.get(
            f"http://money.finance.sina.com.cn/q/view/newFLJK.php?param={kind}",
            headers=HEADERS,
            timeout=20,
        )
        response.encoding = "gbk"
        response.raise_for_status()
        match = re.search(r"=\s*(\{.*\});?\s*$", response.text, re.S)
        if not match:
            return []
        data = json.loads(match.group(1))
    except Exception:
        return []

    rows = []
    for value in data.values():
        parts = value.split(",")
        if len(parts) < 13:
            continue
        rows.append(
            {
                "code": parts[0],
                "name": parts[1],
                "pct": _safe_float(parts[5]),
                "volume": _safe_float(parts[6]),
                "amount": _safe_float(parts[7]),
                "leader_symbol": parts[8],
                "leader_pct": _safe_float(parts[9]),
                "leader_name": parts[12],
            }
        )
    return rows


def _summarize_market_breadth(pct_values: list[float], amount: float, source: str) -> dict[str, Any] | None:
    if not pct_values:
        return None
    return {
        "total": len(pct_values),
        "up": sum(1 for value in pct_values if value > 0),
        "down": sum(1 for value in pct_values if value < 0),
        "flat": sum(1 for value in pct_values if value == 0),
        "limit_up": sum(1 for value in pct_values if value >= 9.8),
        "limit_down": sum(1 for value in pct_values if value <= -9.8),
        "gt5": sum(1 for value in pct_values if value >= 5),
        "lt5": sum(1 for value in pct_values if value <= -5),
        "amount": amount,
        "source": source,
    }


def _fetch_sina_breadth_pages() -> list[dict[str, Any]]:
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    headers = {"User-Agent": HEADERS["User-Agent"], "Referer": "http://vip.stock.finance.sina.com.cn/mkt/"}

    def fetch_page(page: int) -> list[dict[str, Any]]:
        response = requests.get(
            url,
            params={
                "page": page,
                "num": 100,
                "sort": "symbol",
                "asc": 1,
                "node": "hs_a",
                "symbol": "",
                "_s_r_a": "page",
            },
            headers=headers,
            timeout=15,
        )
        response.encoding = "gbk"
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []

    rows: list[dict[str, Any]] = []
    for page in range(1, 91):
        page_rows: list[dict[str, Any]] | None = None
        for _attempt in range(3):
            try:
                page_rows = fetch_page(page)
                break
            except Exception:
                continue
        if page_rows is None:
            return []
        if not page_rows:
            break
        rows.extend(page_rows)
    return rows


def fetch_sina_market_breadth() -> dict[str, Any] | None:
    rows = []
    for _attempt in range(2):
        try:
            response = requests.get(
                "https://push2.eastmoney.com/api/qt/clist/get",
                params={
                    "pn": 1,
                    "pz": 10000,
                    "po": 1,
                    "np": 1,
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                    "fltt": 2,
                    "invt": 2,
                    "fid": "f3",
                    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
                "fields": "f12,f14,f2,f3,f6",
                },
                headers=HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            rows = ((response.json().get("data") or {}).get("diff")) or []
            if rows:
                break
        except Exception:
            continue
    if rows:
        pct_values = [_safe_float(row.get("f3")) for row in rows]
        pct_values = [value for value in pct_values if value is not None]
        amount = sum(_safe_float(row.get("f6")) or 0 for row in rows)
        return _summarize_market_breadth(pct_values, amount, "东方财富全A行情")

    sina_rows = _fetch_sina_breadth_pages()
    pct_values = [_safe_float(row.get("changepercent")) for row in sina_rows]
    pct_values = [value for value in pct_values if value is not None]
    amount = sum(_safe_float(row.get("amount")) or 0 for row in sina_rows)
    return _summarize_market_breadth(pct_values, amount, "新浪市场中心全A分页行情")


def fetch_chinamoney_ccpr(report_date: str | None = None) -> dict[str, Any] | None:
    date_value = report_date or REPORT_DATE
    try:
        start_date = (datetime.strptime(date_value, "%Y-%m-%d") - timedelta(days=12)).strftime("%Y-%m-%d")
        response = requests.get(
            "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew",
            params={"startDate": start_date, "endDate": date_value, "currency": "USD/CNY"},
            headers=HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        records = response.json().get("records") or []
    except Exception:
        return None

    parsed = []
    for record in records:
        values = record.get("values") or []
        price = _safe_float(values[0] if values else None)
        if price is not None:
            parsed.append((record.get("date"), price))
    parsed = [item for item in parsed if item[0]]
    if not parsed:
        return None
    parsed.sort(key=lambda item: item[0])
    current = next((item for item in reversed(parsed) if item[0] <= date_value), parsed[-1])
    prev_candidates = [item for item in parsed if item[0] < current[0]]
    previous = prev_candidates[-1] if prev_candidates else None
    delta = current[1] - previous[1] if previous else None
    change_text = (
        f"{delta:+.4f}（USD/CNY上行表示人民币相对美元走弱）" if delta is not None else "等待前值对比"
    )
    return {
        "date": current[0],
        "price": f"{current[1]:.4f}",
        "change": change_text,
        "previous": f"{previous[1]:.4f}" if previous else "",
        "source": "中国货币网人民币汇率中间价",
    }


def fetch_pbc_omo(report_date: str | None = None) -> dict[str, Any] | None:
    date_value = report_date or REPORT_DATE
    index_url = "http://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/index.html"
    try:
        response = requests.get(index_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        index_text = response.content.decode("utf-8", "ignore")
    except Exception:
        return None

    links = []
    for attrs, body in re.findall(r"<a\b([^>]*)>(.*?)</a>", index_text, re.I | re.S):
        href_match = re.search(r"\bhref\s*=\s*(['\"])(.*?)\1", attrs, re.I)
        if not href_match:
            continue
        title_match = re.search(r"\btitle\s*=\s*(['\"])(.*?)\1", attrs, re.I)
        body_text = html_lib.unescape(re.sub(r"<[^>]+>", " ", body)).strip()
        title = html_lib.unescape(title_match.group(2)) if title_match else body_text
        links.append((href_match.group(2), title, body_text))
    dated_link = None
    for href, title, body_text in links:
        if ("公开市场业务交易公告" in title or "公开市场业务交易公告" in body_text) and date_value.replace("-", "") in href:
            dated_link = (href, title or body_text)
            break
    if not dated_link:
        for href, title, body_text in links:
            if "公开市场业务交易公告" in title or "公开市场业务交易公告" in body_text:
                dated_link = (href, title or body_text)
                break
    if not dated_link:
        return None

    href, title = dated_link
    url = href if href.startswith("http") else "http://www.pbc.gov.cn" + href
    try:
        article = requests.get(url, headers=HEADERS, timeout=20)
        article.raise_for_status()
        text = article.content.decode("utf-8", "ignore")
    except Exception:
        return None

    plain = html_lib.unescape(re.sub(r"<[^>]+>", " ", text))
    plain = re.sub(r"\s+", " ", plain)
    term = None
    amount = None
    zero_match = re.search(r"(\d+)\s*天期逆回购操作量为零", plain)
    amount_match = re.search(r"(\d+)\s*天期逆回购操作量为\s*([\d,]+)\s*亿元", plain)
    table_match = re.search(r"(\d+)\s*天\s*[\d,]+\s*亿元\s*([\d,]+)\s*亿元", plain)
    if zero_match:
        term = int(zero_match.group(1))
        amount = 0
    elif amount_match:
        term = int(amount_match.group(1))
        amount = int(amount_match.group(2).replace(",", ""))
    elif table_match:
        term = int(table_match.group(1))
        amount = int(table_match.group(2).replace(",", ""))

    rate_match = re.search(r"(?:利率|中标利率)[^0-9]{0,8}([\d.]+)\s*%", plain)
    rate = rate_match.group(1) if rate_match else ("无中标" if amount == 0 else "等待披露")
    return {
        "date": date_value,
        "title": html_lib.unescape(title),
        "amount": amount if amount is not None else 0,
        "term": term if term is not None else 7,
        "rate": rate,
        "source": url,
        "summary": plain[max(0, plain.find("根据公开市场")) : plain.find("中国人民银行公开市场业务操作室")]
        if "中国人民银行公开市场业务操作室" in plain
        else plain[:260],
    }


def fetch_global_quotes() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    try:
        response = requests.get(
            "https://hq.sinajs.cn/list=fx_susdcnh,fx_susdcny",
            headers=HEADERS,
            timeout=20,
        )
        response.encoding = "gbk"
        response.raise_for_status()
    except Exception:
        return result

    for symbol, raw in re.findall(r'var hq_str_([a-z0-9_]+)="(.*?)";', response.text, re.S):
        parts = raw.split(",")
        if len(parts) < 12:
            continue
        result[symbol] = {
            "name": parts[9] if len(parts) > 9 else symbol,
            "close": _safe_float(parts[1]),
            "pct": _safe_float(parts[10]),
            "change": _safe_float(parts[11]),
            "date": parts[-1] if parts else "",
            "time": parts[0],
            "source": "新浪外汇行情",
        }
    return result


def fetch_stooq(symbol: str) -> dict[str, Any] | None:
    try:
        response = requests.get(
            "https://stooq.com/q/l/",
            params={"s": symbol, "f": "sd2t2ohlcv", "h": "", "e": "csv"},
            headers=HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        lines = [line.strip() for line in response.text.splitlines() if line.strip()]
        if len(lines) < 2:
            return None
        fields = lines[-1].split(",")
    except Exception:
        return None
    if len(fields) < 7 or fields[3] == "N/D":
        return None
    return {
        "symbol": symbol,
        "date": fields[1],
        "time": fields[2],
        "close": _safe_float(fields[6]),
        "source": "Stooq",
    }


def technical(symbol: str, quote: dict[str, Any] | None) -> dict[str, Any]:
    if not quote:
        return {
            "price": MISSING,
            "ma5": "等待K线源",
            "ma20": "等待K线源",
            "rsi": "等待K线源",
            "macd": "等待K线源",
            "support": MISSING,
            "resistance": MISSING,
        }
    close = quote.get("close")
    open_price = _safe_float(quote.get("open"))
    prev_close = _safe_float(quote.get("prev_close"))
    close_num = _safe_float(close)
    bias = "收盘强于开盘" if close_num is not None and open_price is not None and close_num >= open_price else "收盘弱于开盘"
    if close_num is not None and prev_close is not None:
        bias += "；站上昨收" if close_num >= prev_close else "；低于昨收"
    return {
        "price": close,
        "ma5": "等待K线源",
        "ma20": "等待K线源",
        "rsi": "等待K线源",
        "macd": bias,
        "support": quote.get("low"),
        "resistance": quote.get("high"),
    }


def data_quality(html_doc: str, report_date: str) -> dict[str, Any]:
    missing_count = html_doc.count(MISSING)
    checks = {
        "date_present": report_date in html_doc,
        "has_indices": "主要指数" in html_doc or "大盘指数" in html_doc,
        "has_breadth": "全A宽度" in html_doc or "全 A" in html_doc,
        "has_ccpr": "人民币中间价" in html_doc,
        "has_omo": "公开市场" in html_doc,
        "has_focus": "关注主线" in html_doc,
        "has_sources": "数据来源" in html_doc,
    }
    failed = sum(1 for value in checks.values() if not value)
    score = max(0, 100 - failed * 8 - min(10, missing_count))
    return {"score": score, "missing_count": missing_count, "checks": checks}


def _focus_comment(value: float | None) -> str:
    if value is None:
        return "样本报价不足，暂不判断"
    if value >= 3:
        return "收盘强势，次日先看分歧承接"
    if value > 0:
        return "收盘偏强，次日看量能延续"
    if value <= -3:
        return "收盘走弱，次日防惯性下探"
    if value < 0:
        return "收盘偏弱，等待修复信号"
    return "收盘震荡，等待方向选择"


def _tone_from_pct(value: float | None) -> str:
    if value is None:
        return "blue"
    if value > 0:
        return "red"
    if value < 0:
        return "green"
    return "blue"


def build_report() -> tuple[str, dict[str, Any]]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_symbols = list(
        OrderedDict.fromkeys(
            list(INDEX_SYMBOLS.values())
            + list(ETF_SYMBOLS.values())
            + [symbol for group in FOCUS_GROUPS.values() for symbol in group.values()]
        )
    )
    quotes = fetch_sina_quotes(all_symbols)
    index_quotes = {name: quotes.get(symbol) for name, symbol in INDEX_SYMBOLS.items()}
    industry = fetch_bankuai("industry")
    global_quotes = fetch_global_quotes()
    stooq_dxy = fetch_stooq("dx.f")
    market_breadth = fetch_sina_market_breadth()
    ccpr = fetch_chinamoney_ccpr(REPORT_DATE)
    omo = fetch_pbc_omo(REPORT_DATE)

    trading_day = any(q and q.get("date") == REPORT_DATE for q in index_quotes.values())
    sx = index_quotes.get("上证指数")
    sz = index_quotes.get("深证成指")
    cyb = index_quotes.get("创业板指")
    turnover_yuan = None
    if sx and sz:
        turnover_yuan = (sx.get("amount") or 0) + (sz.get("amount") or 0)

    focus_values = {name: avg_pct(list(group.values()), quotes) for name, group in FOCUS_GROUPS.items()}
    focus_amounts = {
        name: sum((quotes.get(symbol) or {}).get("amount") or 0 for symbol in group.values())
        for name, group in FOCUS_GROUPS.items()
    }
    strongest_focus = max(
        focus_values.items(), key=lambda item: item[1] if item[1] is not None else -999, default=(MISSING, None)
    )
    weakest_focus = min(
        focus_values.items(), key=lambda item: item[1] if item[1] is not None else 999, default=(MISSING, None)
    )

    breadth_summary = (
        f"上涨{market_breadth['up']}只 / 下跌{market_breadth['down']}只 / 平盘{market_breadth['flat']}只；"
        f"涨停约{market_breadth['limit_up']}只 / 跌停约{market_breadth['limit_down']}只"
        if market_breadth
        else MISSING
    )
    breadth_source = (market_breadth or {}).get("source", "行情分页统计")
    rmb_midpoint = (ccpr or {}).get("price", MISSING)
    rmb_change = (ccpr or {}).get("change", "等待前值对比")
    rmb_date = (ccpr or {}).get("date", REPORT_DATE)
    if omo:
        if omo["amount"] == 0:
            omo_amount = f"{omo['term']}天期逆回购操作量为0亿元，{omo['rate']}"
        else:
            omo_amount = f"{omo['amount']}亿元{omo['term']}天期逆回购，利率{omo['rate']}%"
    else:
        omo_amount = MISSING

    index_avg = avg_pct(list(INDEX_SYMBOLS.values())[:3], quotes)
    if index_avg is None:
        market_status = "行情数据待确认"
    elif index_avg > 0.8:
        market_status = "指数整体偏强"
    elif index_avg > 0:
        market_status = "指数震荡偏强"
    elif index_avg < -0.8:
        market_status = "指数整体承压"
    else:
        market_status = "指数震荡偏弱"

    up = (market_breadth or {}).get("up") or 0
    down = (market_breadth or {}).get("down") or 0
    risk_level = "中高" if down > up * 1.5 or (weakest_focus[1] is not None and weakest_focus[1] <= -3) else "中"
    turnover_tag = "成交额活跃" if turnover_yuan and turnover_yuan >= 1_500_000_000_000 else "成交额一般"

    summary_points = [
        f"主要指数收盘：上证指数{fmt_pct((sx or {}).get('pct'))}，深证成指{fmt_pct((sz or {}).get('pct'))}，创业板指{fmt_pct((cyb or {}).get('pct'))}；沪深两市成交额约{fmt_yuan_to_yi(turnover_yuan)}。",
        f"全A宽度：{breadth_summary}，赚钱效应以{breadth_source}口径统计。",
        f"关注主线中，{strongest_focus[0]}相对最强，样本均值{fmt_pct(strongest_focus[1])}；{weakest_focus[0]}相对承压，样本均值{fmt_pct(weakest_focus[1])}。",
        f"宏观锚：人民币中间价{rmb_midpoint}，{rmb_change}；央行公开市场操作为{omo_amount}。",
        "次日重点看成交额能否维持、算力通信是否继续扩散、有色资源是否延续趋势，以及银行/国债是否提示防御风格升温。",
    ]

    focus_rows = []
    focus_bar_max = max([abs(v) for v in focus_values.values() if v is not None] or [1])
    for name, group in FOCUS_GROUPS.items():
        symbols = list(group.values())
        value = focus_values.get(name)
        amount = focus_amounts.get(name)
        quoted = [
            (symbol, quotes.get(symbol))
            for symbol in symbols
            if quotes.get(symbol) and quotes.get(symbol, {}).get("pct") is not None
        ]
        strongest = max(quoted, key=lambda item: item[1]["pct"], default=None)
        weakest = min(quoted, key=lambda item: item[1]["pct"], default=None)
        reps = [quotes.get(symbol, {}).get("name", market_code(symbol)) for symbol in symbols[:5]]
        strength = MISSING
        if strongest and weakest:
            strength = (
                f"强：{quote_name(strongest[0], strongest[1])} {fmt_pct(strongest[1].get('pct'))}；"
                f"弱：{quote_name(weakest[0], weakest[1])} {fmt_pct(weakest[1].get('pct'))}"
            )
        focus_rows.append(
            [
                name,
                " / ".join(reps),
                (bar(value, focus_bar_max), pct_class(value)),
                fmt_yuan_to_yi(amount),
                strength,
                _focus_comment(value),
            ]
        )

    index_rows = []
    for name, symbol in INDEX_SYMBOLS.items():
        q = quotes.get(symbol)
        index_rows.append(
            [
                name,
                fmt_num(q.get("close") if q else None),
                (fmt_pct(q.get("pct") if q else None), pct_class(q.get("pct") if q else None)),
                fmt_num(q.get("high") if q else None),
                fmt_num(q.get("low") if q else None),
                fmt_yuan_to_yi(q.get("amount") if q else None),
                f"{q.get('date', '')} {q.get('time', '')}".strip() if q else MISSING,
            ]
        )

    key_rows = [
        ["沪深两市成交额", fmt_yuan_to_yi(turnover_yuan), "新浪指数成交额字段汇总", turnover_tag],
        ["全A成交额", fmt_yuan_to_yi((market_breadth or {}).get("amount")), f"{breadth_source}汇总", "辅助口径"],
        ["全A涨跌家数", breadth_summary, breadth_source, "观察赚钱效应"],
        ["最强关注主线", strongest_focus[0], fmt_pct(strongest_focus[1]), "次日看承接"],
        ["最弱关注主线", weakest_focus[0], fmt_pct(weakest_focus[1]), "次日防分歧"],
        ["国债ETF（511010.SH）", fmt_num((quotes.get("sh511010") or {}).get("close")), fmt_pct((quotes.get("sh511010") or {}).get("pct")), "债券价格锚，不等同收益率"],
        ["30年国债ETF（511090.SH）", fmt_num((quotes.get("sh511090") or {}).get("close")), fmt_pct((quotes.get("sh511090") or {}).get("pct")), "久期更长，利率预期敏感"],
    ]

    metric_cards = [
        card("沪深两市成交额", fmt_yuan_to_yi(turnover_yuan), "新浪指数成交额字段汇总", "blue"),
        card("全A涨跌家数", f"{up} / {down}", "上涨 / 下跌", "red" if up >= down else "green"),
        card("最强关注主线", strongest_focus[0], fmt_pct(strongest_focus[1]), _tone_from_pct(strongest_focus[1])),
        card("最弱关注主线", weakest_focus[0], fmt_pct(weakest_focus[1]), _tone_from_pct(weakest_focus[1])),
    ]
    for name in ["科技硬件 / AI算力", "通信设备 / 光模块", "有色金属 / 黄金", "电力 / 电网"]:
        value = focus_values.get(name)
        metric_cards.append(
            card(
                name,
                fmt_pct(value),
                f"样本成交额：{fmt_yuan_to_yi(focus_amounts.get(name))}",
                _tone_from_pct(value),
            )
        )

    industry_sorted = sorted(industry, key=lambda x: x.get("pct") if x.get("pct") is not None else -999, reverse=True)
    max_ind_abs = max([abs(x["pct"]) for x in industry if x.get("pct") is not None] or [1])
    industry_rows = []
    seen = set()
    for row in industry_sorted:
        matched = next((label for label, words in FOCUS_INDUSTRY_KEYWORDS.items() if any(word in row["name"] for word in words)), None)
        if not matched:
            continue
        key = (matched, row["name"])
        if key in seen:
            continue
        seen.add(key)
        industry_rows.append(
            [
                matched,
                row["name"],
                (bar(row.get("pct"), max_ind_abs), pct_class(row.get("pct"))),
                fmt_yuan_to_yi(row.get("amount")),
                row.get("leader_name", MISSING),
                "新浪行业分类口径，结合关注主线观察",
            ]
        )
        if len(industry_rows) >= 18:
            break
    if not industry_rows:
        industry_rows.append(["关注行业", MISSING, MISSING, MISSING, MISSING, "未匹配到关注行业关键词"])

    etf_rows = []
    for name, symbol in ETF_SYMBOLS.items():
        if name not in FOCUS_ETFS:
            continue
        q = quotes.get(symbol)
        etf_rows.append(
            [
                name,
                market_code(symbol),
                (fmt_pct(q.get("pct") if q else None), pct_class(q.get("pct") if q else None)),
                fmt_yuan_to_yi(q.get("amount") if q else None),
                chip("成交额可得" if q else "数据待核验", "data-ok" if q else "data-missing"),
                "ETF成交额可观察，份额变化需基金公告/终端口径",
            ]
        )

    stock_sections = []
    watch_rows = []
    for group_name, group in FOCUS_GROUPS.items():
        rows = []
        items = sorted(group.items(), key=lambda kv: abs((quotes.get(kv[1]) or {}).get("pct") or 0), reverse=True)[:8]
        for _name, symbol in items:
            q = quotes.get(symbol)
            pct = q.get("pct") if q else None
            rows.append(
                [
                    quote_name(symbol, q) if q else f"{_name}（{market_code(symbol)}）",
                    (fmt_pct(pct), pct_class(pct)),
                    fmt_yuan_to_yi(q.get("amount") if q else None),
                    chip(trend_text(q), status_class(trend_text(q))),
                    "次日看是否守住收盘强弱区间",
                ]
            )
        stock_sections.append(
            f"<h3>{esc(group_name)}</h3>" + table(["股票", "收盘涨跌", "成交额", "状态", "次日观察"], rows)
        )
        for _name, symbol in group.items():
            q = quotes.get(symbol)
            pct = q.get("pct") if q else None
            watch_rows.append(
                [
                    quote_name(symbol, q) if q else f"{_name}（{market_code(symbol)}）",
                    (fmt_pct(pct), pct_class(pct)),
                    trend_text(q),
                    fmt_num(q.get("low") if q else None),
                    fmt_num(q.get("high") if q else None),
                    chip(judgement(pct), status_class(judgement(pct))),
                    "观察量能、板块同步性与次日开盘承接",
                ]
            )

    tech_symbols = list(
        OrderedDict.fromkeys(
            list(INDEX_SYMBOLS.values())[:8]
            + ["sh515880", "sh512480", "sh512800", "sh511010", "sh511090", "sh588000"]
        )
    )
    tech_rows = []
    for symbol in tech_symbols:
        q = quotes.get(symbol)
        t = technical(symbol, q)
        tech_rows.append(
            [
                quote_name(symbol, q),
                fmt_num(t.get("price")),
                fmt_num(t.get("ma5")),
                fmt_num(t.get("ma20")),
                fmt_num(t.get("rsi")),
                t.get("macd", "等待K线源"),
                fmt_num(t.get("support")),
                fmt_num(t.get("resistance")),
            ]
        )

    macro_rows = [
        ["人民币中间价", rmb_midpoint, rmb_change, f"中国货币网授权公布，数据时间：{rmb_date}"],
        ["USD/CNH 离岸人民币", fmt_num(global_quotes.get("fx_susdcnh", {}).get("close")), fmt_pct(global_quotes.get("fx_susdcnh", {}).get("pct")), "观察汇率对外资和风险偏好的影响"],
        ["USD/CNY 在岸人民币", fmt_num(global_quotes.get("fx_susdcny", {}).get("close")), fmt_pct(global_quotes.get("fx_susdcny", {}).get("pct")), "日内行情来自新浪外汇，需以官方中间价核验"],
        ["美元指数 DXY", fmt_num(stooq_dxy.get("close") if stooq_dxy else None), "外盘延时口径", "跟踪美元对黄金、有色和成长估值的影响"],
        ["国债ETF（511010.SH）", fmt_num((quotes.get("sh511010") or {}).get("close")), fmt_pct((quotes.get("sh511010") or {}).get("pct")), "债券价格锚，不等同国债收益率"],
        ["30年国债ETF（511090.SH）", fmt_num((quotes.get("sh511090") or {}).get("close")), fmt_pct((quotes.get("sh511090") or {}).get("pct")), "长久期价格锚，对利率预期更敏感"],
        ["10年期中国国债收益率", "等待官方/中债估值口径", "不使用非官方实时估算", "保留为人工复核项"],
    ]

    risk_rows = [
        ["成交额延续性", "放量后若次日缩量，强势主线容易出现分歧", risk_chip("中")],
        ["科技拥挤度", "算力、CPO、PCB、封测高波动，需看龙头承接", risk_chip("中高")],
        ["资源波动", "有色黄金油气受美元、商品价格和风险偏好影响较大", risk_chip("中")],
        ["电力电网", "偏防御和稳增长线，若无量能配合容易轮动", risk_chip("中")],
        ["银行国债", "银行与国债同步走强可能提示防御风格增强", risk_chip("中")],
        ["数据口径", "行情接口与交易所/终端口径可能存在延时或字段差异", risk_chip("中")],
    ]

    plan_rows = [
        ["成交额", "次日能否维持在今日成交水平附近", "决定强势主线能否继续扩散"],
        ["算力通信", "光模块/通信设备是否继续强于指数", "看中际旭创、新易盛、光迅科技、通信ETF"],
        ["有色黄金", "中国铝业、紫金矿业、洛阳钼业是否继续强于指数", "判断资源线是否继续主线化"],
        ["电力电网", "电力红利和电网设备是否同步承接", "判断防御资金与稳增长线索"],
        ["银行国债", "银行ETF与国债ETF是否同步走强", "判断市场是否转向防御/红利"],
        ["化工材料", "万华、华鲁、云天化能否带动板块", "判断化工是否从个股修复扩散"],
    ]

    sources = [
        ("新浪财经行情中心", "https://finance.sina.com.cn/realstock/"),
        ("新浪沪深行情接口 hq.sinajs.cn", "https://finance.sina.com.cn/"),
        ("新浪板块分类 newFLJK", "http://money.finance.sina.com.cn/q/view/newFLJK.php?param=industry"),
        ("东方财富全A行情接口", "https://quote.eastmoney.com/center/gridlist.html"),
        ("Stooq DXY 行情", "https://stooq.com/"),
        ("中国货币网人民币汇率中间价", "https://www.chinamoney.com.cn/chinese/bkccpr/"),
        ("中国人民银行公开市场业务交易公告", (omo or {}).get("source", "http://www.pbc.gov.cn/")),
        ("上海证券交易所", "https://www.sse.com.cn/"),
        ("深圳证券交易所", "https://www.szse.cn/"),
        ("巨潮资讯网", "https://www.cninfo.com.cn/"),
    ]

    nav_items = [
        ("summary", "核心结论"),
        ("focus", "关注主线"),
        ("metrics", "关键指标"),
        ("indices", "主要指数"),
        ("macro", "宏观国债"),
        ("funds", "ETF成交"),
        ("sectors", "关注行业"),
        ("stocks", "关注个股"),
        ("watchlist", "关注池"),
        ("technical", "技术面"),
        ("plan", "次日计划"),
        ("risk", "风险提示"),
        ("sources", "数据来源"),
    ]
    nav_html = "".join(f'<a href="#{sec}">{label}</a>' for sec, label in nav_items)

    html_sections = [
        section(
            "summary",
            "今日收盘核心结论",
            f"""
            <div class="summary-card">
              <h3>收盘一句话总结</h3>
              <p>{"".join(f"<span>{esc(point)}</span>" for point in summary_points)}</p>
              <div class="state-line"><b>收盘市场状态：</b>{esc(market_status)} + {esc(turnover_tag)} + 风险等级{esc(risk_level)}</div>
            </div>
            """,
        ),
        section(
            "focus",
            "我的关注主线收盘速览",
            "<div class='analysis-box'><p>表内样本均值来自关注股池，不代表完整行业指数；用于跟踪主线强弱和次日复盘。</p></div>"
            + table(["关注主线", "代表样本", "收盘样本涨跌", "样本成交额", "强弱股票", "次日观察"], focus_rows),
        ),
        section(
            "metrics",
            "关键指标与关注池卡片",
            f'<div class="metric-grid">{"".join(metric_cards)}</div>'
            + table(["指标", "今日收盘", "变化/来源", "状态"], key_rows),
        ),
        section(
            "indices",
            "主要指数收盘背景",
            table(["指数", "收盘点位", "涨跌幅", "日内高点", "日内低点", "成交额", "行情时间"], index_rows),
        ),
        section(
            "macro",
            "宏观、汇率与国债观察",
            table(["指标", "最新水平", "日变化", "市场含义"], macro_rows)
            + table(
                ["项目", "当日数据", "来源", "解读"],
                [["公开市场逆回购", omo_amount, (omo or {}).get("title", "央行公开市场公告"), "资金面观察锚，次日结合银行和国债ETF表现复核"]],
            ),
        ),
        section("funds", "关注ETF成交区", table(["ETF / 方向", "代表代码", "收盘涨跌幅", "成交额", "数据状态", "解读"], etf_rows)),
        section("sectors", "关注行业收盘表现", table(["归类", "行业", "收盘涨跌幅", "成交额", "领涨股", "观察要点"], industry_rows)),
        section(
            "stocks",
            "关注个股收盘异动",
            "<div class='analysis-box warning'><p>个股只保留八条关注主线内的核心样本，按收盘波动绝对值排序展示；公告事件以巨潮资讯网和交易所披露为准。</p></div>"
            + "".join(stock_sections),
        ),
        section(
            "watchlist",
            "我的重点关注股",
            '<div class="toolbar"><label>个股搜索 <input id="stockSearch" type="search" placeholder="输入股票名称或代码"></label></div>'
            + table(["股票", "收盘涨跌", "当前趋势", "日内低点", "日内高点", "判断标签", "次日观察"], watch_rows, "sortable searchable"),
        ),
        section(
            "technical",
            "技术面与关键价位",
            table(["标的", "当前价格", "5日线", "20日线", "RSI", "MACD / 趋势", "日内支撑", "日内压力"], tech_rows),
        ),
        section("plan", "次日交易观察计划", table(["观察项", "触发信号", "为什么重要"], plan_rows)),
        section("risk", "风险提示", table(["风险维度", "当前状态", "风险等级"], risk_rows)),
        section(
            "sources",
            "数据来源与免责声明",
            "<h3>数据来源</h3><ul class='source-list'>"
            + "".join(f'<li><a href="{esc(url)}">{esc(name)}</a></li>' for name, url in sources)
            + "</ul>"
            + f"""
            <div class="analysis-box warning">
              <p><b>数据更新时间：</b>{esc(generated_at)} 北京时间。</p>
              <p><b>收盘口径说明：</b>本报告以收盘后可取得的公开行情和官方网页数据为基础；交易所、上市公司公告和官方披露优先于行情终端口径。</p>
              <p><b>数据缺失说明：</b>全A涨跌家数使用东方财富全A行情统计；涨跌停为按涨跌幅阈值近似统计。10年期中国国债收益率、ETF份额变化、北向资金旧式实时净额等未接入稳定官方结构化源，本版不做估算。</p>
              <p><b>免责声明：</b>本报告仅用于市场复盘与研究分析，不构成任何投资建议。市场有风险，投资需谨慎。报告中的数据和观点基于公开信息整理，如有数据延迟、错误或遗漏，请以交易所、上市公司公告及官方披露为准。</p>
            </div>
            """,
        ),
    ]

    css = """
    :root {
      --red:#d93025; --red-bg:#fff1f0; --green:#188038; --green-bg:#edf7ee;
      --orange:#f29900; --blue:#1a73e8; --gray:#5f6368; --light-bg:#f5f7fa;
      --card-bg:#ffffff; --border:#e5e7eb; --text-main:#111827; --text-sub:#6b7280;
      --shadow:0 10px 24px rgba(15,23,42,.08);
    }
    *{box-sizing:border-box} html{scroll-behavior:smooth}
    body{margin:0;background:var(--light-bg);color:var(--text-main);font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif}
    a{color:var(--blue);text-decoration:none}
    .hero{background:linear-gradient(135deg,#111827,#263241 58%,#0f172a);color:#fff;padding:28px 20px 18px}
    .hero-inner{max-width:1360px;margin:0 auto}.eyebrow{color:#cbd5e1;font-size:13px}
    .hero h1{font-size:34px;margin:8px 0;letter-spacing:0}.hero-sub{color:#d1d5db;margin:0 0 16px}
    .tags{display:flex;flex-wrap:wrap;gap:8px}.tag{display:inline-flex;align-items:center;border:1px solid rgba(255,255,255,.22);border-radius:999px;padding:4px 10px;font-weight:600;background:rgba(255,255,255,.08)}
    .status-chip{display:inline-flex;align-items:center;border-radius:999px;border:1px solid transparent;padding:3px 9px;font-size:12px;font-weight:700;white-space:nowrap}
    .status-strong{background:#fee2e2;color:#b42318;border-color:#fecaca}.status-hot{background:#fff7ed;color:#9a3412;border-color:#fed7aa}
    .status-watch{background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe}.status-risk{background:#fff1f2;color:#be123c;border-color:#fecdd3}
    .status-neutral{background:#f3f4f6;color:#4b5563;border-color:#e5e7eb}.risk-mid{background:#fff7ed;color:#9a3412;border-color:#fed7aa}
    .risk-high{background:#fee2e2;color:#991b1b;border-color:#fecaca}.data-ok{background:#ecfdf3;color:#166534;border-color:#bbf7d0}
    .data-missing{background:#f3f4f6;color:#4b5563;border-color:#e5e7eb}
    .top-nav{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.96);border-bottom:1px solid var(--border);backdrop-filter:blur(8px);overflow-x:auto;white-space:nowrap}
    .top-nav .nav-inner{max-width:1360px;margin:0 auto;display:flex;gap:6px;padding:9px 20px}.top-nav a{color:#374151;padding:5px 9px;border-radius:6px}.top-nav a:hover{background:#eef2ff}
    main{max-width:1360px;margin:18px auto 56px;padding:0 20px}.section-anchor{scroll-margin-top:58px}
    .section-card{background:var(--card-bg);border:1px solid var(--border);border-radius:8px;margin:14px 0;box-shadow:var(--shadow);overflow:hidden}
    .section-card summary{cursor:pointer;display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--border)}
    .section-card h2{font-size:18px;margin:0}.chev{color:var(--text-sub);font-size:12px}.section-body{padding:16px 18px}.section-body h3{font-size:15px;margin:18px 0 8px;color:#1f2937}
    .summary-card{border-left:4px solid var(--blue);background:#f8fafc;border-radius:8px;padding:16px}.summary-card h3{margin-top:0}.summary-card p span{display:block;margin:6px 0}
    .state-line{margin-top:12px;padding:10px;border-radius:8px;background:#eef2ff;color:#1e3a8a}
    .metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:14px}
    .metric-card{border:1px solid var(--border);border-radius:8px;background:#fff;padding:14px;min-height:104px}.metric-title{color:var(--text-sub);font-size:12px}
    .metric-value{font-size:22px;font-weight:800;margin:6px 0}.metric-sub{color:var(--text-sub);font-size:12px}
    .metric-card.red{background:var(--red-bg)}.metric-card.green{background:var(--green-bg)}.metric-card.blue{background:#eff6ff}
    .table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:8px;background:#fff;margin:8px 0 12px}
    table{width:100%;border-collapse:collapse;min-width:760px}th,td{padding:9px 10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}
    th{position:sticky;top:0;background:#f9fafb;color:#374151;font-size:12px;white-space:nowrap;cursor:pointer}tr:nth-child(even) td{background:#fcfcfd}
    td.up,.up{color:var(--red);font-weight:700}td.down,.down{color:var(--green);font-weight:700}.neutral{color:var(--gray)}.missing{color:var(--text-sub);font-weight:500}
    .bar{position:relative;min-width:120px;height:22px;background:#f3f4f6;border-radius:5px;overflow:hidden}.bar span{position:absolute;left:0;top:0;bottom:0;opacity:.18}.bar b{position:relative;padding-left:8px;line-height:22px}.bar.up span{background:var(--red)}.bar.down span{background:var(--green)}
    .analysis-box{background:#f9fafb;border:1px solid var(--border);border-radius:8px;padding:12px;margin-top:10px;color:#374151}.warning{border-color:#fed7aa;background:#fff7ed}
    .toolbar{display:flex;justify-content:flex-end;margin-bottom:10px}.toolbar input{border:1px solid var(--border);border-radius:8px;padding:8px 10px;min-width:240px}
    .source-list{columns:2}#backTop{position:fixed;right:18px;bottom:18px;border:0;border-radius:999px;background:#111827;color:#fff;padding:10px 13px;box-shadow:var(--shadow);display:none;cursor:pointer}
    @media (max-width:900px){.metric-grid{grid-template-columns:repeat(2,1fr)}main{padding:0 12px}.section-body{padding:12px}.source-list{columns:1}.hero h1{font-size:26px}}
    @media print{.top-nav,#backTop,.toolbar{display:none}.section-card{box-shadow:none;break-inside:avoid}body{background:#fff}.hero{background:#111827!important;color:#fff!important}}
    """

    js = """
    document.querySelectorAll('table.sortable th').forEach((th, idx) => {
      th.addEventListener('click', () => {
        const table = th.closest('table'); const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const asc = th.dataset.asc !== '1'; th.dataset.asc = asc ? '1' : '0';
        rows.sort((a,b) => {
          const av = a.children[idx].innerText.replace(/[,亿元%+]/g,'').trim();
          const bv = b.children[idx].innerText.replace(/[,亿元%+]/g,'').trim();
          const an = parseFloat(av), bn = parseFloat(bv);
          if(!Number.isNaN(an) && !Number.isNaN(bn)) return asc ? an-bn : bn-an;
          return asc ? av.localeCompare(bv,'zh-Hans-CN') : bv.localeCompare(av,'zh-Hans-CN');
        });
        rows.forEach(r => tbody.appendChild(r));
      });
    });
    const search = document.getElementById('stockSearch');
    if(search){ search.addEventListener('input', () => {
      const key = search.value.trim().toLowerCase();
      document.querySelectorAll('table.searchable tbody tr').forEach(tr => {
        tr.style.display = tr.innerText.toLowerCase().includes(key) ? '' : 'none';
      });
    });}
    const back = document.getElementById('backTop');
    window.addEventListener('scroll', () => { back.style.display = window.scrollY > 500 ? 'block' : 'none'; });
    back.addEventListener('click', () => window.scrollTo({top:0, behavior:'smooth'}));
    """

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>A股收盘日报｜精简关注版｜{REPORT_DATE}</title>
  <style>{css}</style>
</head>
<body>
  <header class="hero">
    <div class="hero-inner">
      <div class="eyebrow">收盘复盘 · 算力通信 · 有色资源 · 电力电网 · 银行国债 · 化工材料</div>
      <h1>A股收盘日报｜精简关注版｜{REPORT_DATE}</h1>
      <p class="hero-sub">生成时间：{esc(generated_at)} 北京时间｜收盘口径：公开行情与官方网页数据｜交易日判断：{"A股交易日" if trading_day else "非交易日或行情未更新"}</p>
      <div class="tags">
        <span class="tag">{esc(market_status)}</span>
        <span class="tag risk-mid">风险等级：{esc(risk_level)}</span>
        <span class="tag">{esc(turnover_tag)}</span>
        <span class="tag">次日计划已更新</span>
      </div>
    </div>
  </header>
  <nav class="top-nav"><div class="nav-inner">{nav_html}</div></nav>
  <main>{"".join(html_sections)}</main>
  <button id="backTop" aria-label="返回顶部">↑</button>
  <script>{js}</script>
</body>
</html>
"""

    quality = data_quality(html_doc, REPORT_DATE)
    stats = {
        "generated_at": generated_at,
        "trading_day": trading_day,
        "turnover_yuan": turnover_yuan,
        "data_completeness": quality["score"],
        "data_quality": quality,
    }
    return html_doc, stats


def main() -> int:
    html_doc, stats = build_report()
    out = Path(f"A股收盘日报_{REPORT_DATE}.html")
    out.write_text(html_doc, encoding="utf-8")
    print("日报生成成功：")
    print(f"文件路径：{out}")
    print(f"生成时间：{stats['generated_at']}")
    print(f"数据完整度：{stats['data_completeness']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
