from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from generate_a_share_report import (
    ETF_SYMBOLS,
    FOCUS_ETFS,
    FOCUS_GROUPS,
    FOCUS_INDUSTRY_KEYWORDS,
    INDEX_SYMBOLS,
    MISSING,
    avg_pct,
    bar,
    card,
    chip,
    esc,
    fetch_bankuai,
    fetch_chinamoney_ccpr,
    fetch_global_quotes,
    fetch_pbc_omo,
    fetch_sina_market_breadth,
    fetch_sina_quotes,
    fetch_stooq,
    fmt_num,
    fmt_pct,
    fmt_yuan_to_yi,
    judgement,
    market_code,
    pct_class,
    quote_name,
    risk_chip,
    section,
    status_class,
    table,
    technical,
    trend_text,
    data_quality,
)


REPORT_DATE = datetime.now().strftime("%Y-%m-%d")


def focus_comment(value: float | None) -> str:
    if value is None:
        return "样本报价不足，暂不判断"
    if value >= 2:
        return "午盘明显走强，下午看承接"
    if value > 0:
        return "午盘小幅走强，下午看量能"
    if value <= -2:
        return "午盘明显走弱，下午防分歧扩大"
    return "午盘震荡分化，等待方向选择"


def source_link(text: str, url: str) -> str:
    return f'<a href="{esc(url)}">{esc(text)}</a>'


def build_midday_report() -> tuple[str, dict[str, Any]]:
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
    ccpr = fetch_chinamoney_ccpr()
    omo = fetch_pbc_omo(REPORT_DATE)

    trading_day = any(q and q.get("date") == REPORT_DATE for q in index_quotes.values())
    sx = index_quotes.get("上证指数")
    sz = index_quotes.get("深证成指")
    turnover_yuan = None
    if sx and sz:
        turnover_yuan = (sx.get("amount") or 0) + (sz.get("amount") or 0)

    focus_values = {name: avg_pct(list(group.values()), quotes) for name, group in FOCUS_GROUPS.items()}
    focus_amounts = {
        name: sum((quotes.get(symbol) or {}).get("amount") or 0 for symbol in group.values())
        for name, group in FOCUS_GROUPS.items()
    }
    strongest_focus = max(focus_values.items(), key=lambda item: item[1] if item[1] is not None else -999, default=(MISSING, None))
    weakest_focus = min(focus_values.items(), key=lambda item: item[1] if item[1] is not None else 999, default=(MISSING, None))

    turnover_tag = "午盘成交活跃" if turnover_yuan and turnover_yuan >= 1_500_000_000_000 else "午盘成交待确认"
    risk_level = "中"
    market_status = f"午盘聚焦：{strongest_focus[0]}相对强，{weakest_focus[0]}承压"

    rmb_midpoint = (ccpr or {}).get("price", MISSING)
    rmb_change = (ccpr or {}).get("change", MISSING)
    rmb_date = (ccpr or {}).get("date", MISSING)
    omo_amount = f"{omo['amount']}亿元{omo['term']}天期逆回购，利率{omo['rate']}%" if omo else MISSING
    omo_net = "净额不估算"
    omo_maturity = "到期量未接入官方结构化源"
    breadth_summary = (
        f"上涨{market_breadth['up']}只 / 下跌{market_breadth['down']}只 / 平盘{market_breadth['flat']}只"
        if market_breadth
        else MISSING
    )

    summary_points = [
        "本午盘版沿用八条关注主线：科技硬件/AI算力、通信设备/光模块、互联网软件/信创、有色黄金、资源能源、电力电网、化工材料、银行国债。",
        "截至当前行情接口，主要指数和关注池数据来自新浪实时行情；午盘数据仍会随下午交易变化，不能当作收盘定论。",
        "从关注池样本看，"
        + f"{strongest_focus[0]}相对更强，样本均值{fmt_pct(strongest_focus[1])}；"
        + f"{weakest_focus[0]}相对承压，样本均值{fmt_pct(weakest_focus[1])}。",
        f"宏观锚方面，人民币中间价报{rmb_midpoint}，{rmb_change}；央行公开市场操作为{omo_amount}。",
        "下午重点看：午盘强势主线能否延续、算力通信是否修复分歧、有色资源是否扩散、电力银行国债是否继续提示防御风格。",
    ]

    focus_rows = []
    focus_bar_max = max([abs(v) for v in focus_values.values() if v is not None] or [1])
    for name, group in FOCUS_GROUPS.items():
        symbols = list(group.values())
        value = focus_values.get(name)
        amount = focus_amounts.get(name)
        quoted = [(symbol, quotes.get(symbol)) for symbol in symbols if quotes.get(symbol) and quotes.get(symbol, {}).get("pct") is not None]
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
                focus_comment(value),
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
                q.get("time", MISSING) if q else MISSING,
            ]
        )

    key_rows = [
        ["沪深两市半日成交额", fmt_yuan_to_yi(turnover_yuan), "新浪指数成交额字段汇总", "需以交易所/行情终端复核"],
        ["最强关注主线", strongest_focus[0], fmt_pct(strongest_focus[1]), "关注下午承接"],
        ["最弱关注主线", weakest_focus[0], fmt_pct(weakest_focus[1]), "观察是否扩大分歧"],
        ["全A宽度", breadth_summary, "新浪市场中心全A分页行情", "下午观察赚钱效应是否延续"],
        ["国债ETF（511010.SH）", fmt_num((quotes.get("sh511010") or {}).get("close")), fmt_pct((quotes.get("sh511010") or {}).get("pct")), "债券价格锚，不等同收益率"],
        ["30年国债ETF（511090.SH）", fmt_num((quotes.get("sh511090") or {}).get("close")), fmt_pct((quotes.get("sh511090") or {}).get("pct")), "久期更长，利率预期敏感"],
        ["10年期中国国债收益率", MISSING, "等待官方/中债估值", "不使用非官方实时估算"],
    ]

    metric_cards = [
        card("沪深两市半日成交额", fmt_yuan_to_yi(turnover_yuan), "新浪指数成交额字段汇总", "blue"),
        card("最强关注主线", esc(strongest_focus[0]), fmt_pct(strongest_focus[1]), "red" if (strongest_focus[1] or 0) > 0 else "green"),
        card("最弱关注主线", esc(weakest_focus[0]), fmt_pct(weakest_focus[1]), "green" if (weakest_focus[1] or 0) < 0 else "blue"),
    ]
    for name in ["科技硬件 / AI算力", "通信设备 / 光模块", "有色金属 / 黄金", "电力 / 电网", "银行 / 国债"]:
        value = focus_values.get(name)
        metric_cards.append(
            card(name, fmt_pct(value), f"样本成交额：{fmt_yuan_to_yi(focus_amounts.get(name))}", "red" if (value or 0) > 0 else "green" if (value or 0) < 0 else "blue")
        )

    industry_sorted = sorted(industry, key=lambda x: x.get("pct") if x.get("pct") is not None else -999, reverse=True)
    max_ind_abs = max([abs(x["pct"]) for x in industry if x.get("pct") is not None] or [1])
    industry_rows = []
    for row in industry_sorted:
        matched = next((label for label, words in FOCUS_INDUSTRY_KEYWORDS.items() if any(word in row["name"] for word in words)), None)
        if not matched:
            continue
        industry_rows.append(
            [
                matched,
                esc(row["name"]),
                (bar(row.get("pct"), max_ind_abs), pct_class(row.get("pct"))),
                fmt_yuan_to_yi(row.get("amount")),
                esc(row.get("leader_name", MISSING)),
                "新浪行业分类口径，午盘仅供方向参考",
            ]
        )
        if len(industry_rows) >= 16:
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
        items = sorted(group.items(), key=lambda kv: abs((quotes.get(kv[1]) or {}).get("pct") or 0), reverse=True)[:10]
        for name, symbol in items:
            q = quotes.get(symbol)
            pct = q.get("pct") if q else None
            rows.append(
                [
                    quote_name(symbol, q) if q else f"{name}（{market_code(symbol)}）",
                    (fmt_pct(pct), pct_class(pct)),
                    fmt_yuan_to_yi(q.get("amount") if q else None),
                    chip(trend_text(q), status_class(trend_text(q))),
                    "下午看是否守住午盘低点/突破午盘高点",
                ]
            )
        stock_sections.append(
            f"<h3>{esc(group_name)}</h3>"
            + table(["股票", "午盘涨跌", "成交额", "状态", "下午观察"], rows)
        )
        for name, symbol in group.items():
            q = quotes.get(symbol)
            pct = q.get("pct") if q else None
            watch_rows.append(
                [
                    quote_name(symbol, q) if q else f"{name}（{market_code(symbol)}）",
                    (fmt_pct(pct), pct_class(pct)),
                    trend_text(q),
                    fmt_num(q.get("low") if q else None),
                    fmt_num(q.get("high") if q else None),
                    chip(judgement(pct)),
                    "下午观察量能、分时承接与板块同步性",
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
                t.get("macd", MISSING),
                fmt_num(t.get("support")),
                fmt_num(t.get("resistance")),
            ]
        )

    macro_rows = [
        ["人民币中间价", rmb_midpoint, rmb_change, f"中国货币网授权公布，数据时间：{rmb_date}"],
        ["USD/CNH 离岸人民币", fmt_num(global_quotes.get("fx_susdcnh", {}).get("close")), fmt_pct(global_quotes.get("fx_susdcnh", {}).get("pct")), "观察汇率对外资和风险偏好的影响"],
        ["USD/CNY 在岸人民币", fmt_num(global_quotes.get("fx_susdcny", {}).get("close")), fmt_pct(global_quotes.get("fx_susdcny", {}).get("pct")), "日内行情来自新浪外汇，需以官方中间价核验"],
        ["美元指数 DXY", fmt_num(stooq_dxy.get("close") if stooq_dxy else None), MISSING, "跟踪美元对黄金、有色和成长估值的影响"],
        ["国债ETF（511010.SH）", fmt_num((quotes.get("sh511010") or {}).get("close")), fmt_pct((quotes.get("sh511010") or {}).get("pct")), "债券价格锚，不等同国债收益率"],
        ["30年国债ETF（511090.SH）", fmt_num((quotes.get("sh511090") or {}).get("close")), fmt_pct((quotes.get("sh511090") or {}).get("pct")), "长久期价格锚，对利率预期更敏感"],
    ]

    risk_rows = [
        ["午后成交承接", "上午强势主线若午后缩量回落，容易形成冲高回落", risk_chip("中")],
        ["科技拥挤度", "算力、CPO、PCB、封测高位分化，需看龙头承接", risk_chip("中高")],
        ["资源波动", "有色黄金油气受美元和商品价格影响较大", risk_chip("中")],
        ["电力电网", "偏防御和稳增长线，若无量能配合容易轮动", risk_chip("中")],
        ["银行国债", "银行与国债同步走强可能提示防御风格增强", risk_chip("中")],
        ["数据口径", "午盘数据仍会随下午交易变化", risk_chip("中")],
    ]

    plan_rows = [
        ["成交额", "午后是否继续放量", "决定上午强势主线能否延续"],
        ["算力通信", "光模块/通信设备能否从分化转修复", "看中际旭创、新易盛、光迅科技、通信ETF"],
        ["有色黄金", "中国铝业、紫金矿业、洛阳钼业是否继续强于指数", "判断资源线是否继续主线化"],
        ["电力电网", "电力红利和电网设备是否同步承接", "判断防御资金与稳增长线索"],
        ["银行国债", "银行ETF与国债ETF是否同步走强", "判断市场是否转向防御/红利"],
        ["化工材料", "万华、华鲁、云天化能否带动板块", "判断化工是否从个股修复扩散"],
    ]

    sources = [
        ("新浪财经行情中心", "https://finance.sina.com.cn/realstock/"),
        ("新浪沪深行情接口 hq.sinajs.cn", "https://finance.sina.com.cn/"),
        ("新浪板块分类 newFLJK", "http://money.finance.sina.com.cn/q/view/newFLJK.php?param=industry"),
        ("Stooq DXY 行情", "https://stooq.com/"),
        ("新浪市场中心全A分页行情", "http://vip.stock.finance.sina.com.cn/mkt/"),
        ("中国货币网人民币汇率中间价", "https://www.chinamoney.com.cn/chinese/bkccpr/"),
        ("中国人民银行公开市场业务交易公告", (omo or {}).get("source", "http://www.pbc.gov.cn/")),
        ("中国人民银行", "http://www.pbc.gov.cn/"),
        ("中国外汇交易中心", "https://www.chinamoney.com.cn/"),
        ("上海证券交易所", "https://www.sse.com.cn/"),
        ("深圳证券交易所", "https://www.szse.cn/"),
        ("巨潮资讯网", "https://www.cninfo.com.cn/"),
    ]

    nav_items = [
        ("summary", "核心结论"),
        ("focus", "关注主线"),
        ("metrics", "关键指标"),
        ("indices", "指数背景"),
        ("macro", "宏观国债"),
        ("funds", "ETF成交"),
        ("sectors", "关注行业"),
        ("stocks", "关注个股"),
        ("watchlist", "关注股"),
        ("technical", "技术面"),
        ("plan", "下午计划"),
        ("risk", "风险提示"),
        ("sources", "数据来源"),
    ]
    nav_html = "".join(f'<a href="#{sec}">{label}</a>' for sec, label in nav_items)

    html_sections = [
        section(
            "summary",
            "今日午盘核心结论",
            f"""
            <div class="summary-card">
              <h3>午盘一句话总结</h3>
              <p>{"".join(f"<span>{esc(p)}</span>" for p in summary_points)}</p>
              <div class="state-line"><b>午盘市场状态：</b>{esc(market_status)} + {esc(turnover_tag)} + 风险等级{esc(risk_level)}</div>
            </div>
            """,
        ),
        section(
            "focus",
            "我的关注主线午盘速览",
            "<div class='analysis-box'><p>表内样本均值来自关注股池，不代表完整行业指数。午盘数据以当前行情接口为准，下午可能变化。</p></div>"
            + table(["关注主线", "代表样本", "午盘样本涨跌", "样本成交额", "强弱股票", "下午观察"], focus_rows),
        ),
        section(
            "metrics",
            "关键指标与关注池卡片",
            f'<div class="metric-grid">{"".join(metric_cards)}</div>'
            + table(["指标", "今日午盘", "变化/来源", "状态"], key_rows),
        ),
        section(
            "indices",
            "大盘指数午盘背景",
            table(["指数", "午盘点位", "涨跌幅", "日内高点", "日内低点", "成交额", "行情时间"], index_rows),
        ),
        section(
            "macro",
            "宏观、汇率与国债观察",
            table(["指标", "最新水平", "日变化", "市场含义"], macro_rows)
            + table(
                ["项目", "当日数据", "到期量", "净投放 / 净回笼", "解读"],
                [["公开市场逆回购", omo_amount, omo_maturity, omo_net, "资金面偏呵护，需观察午后债券与银行表现"]],
            ),
        ),
        section("funds", "关注ETF成交区", table(["ETF / 方向", "代表代码", "午盘涨跌幅", "成交额", "数据状态", "解读"], etf_rows)),
        section("sectors", "关注行业午盘表现", table(["归类", "行业", "午盘涨跌幅", "成交额", "领涨股", "观察要点"], industry_rows)),
        section(
            "stocks",
            "关注个股午盘异动",
            "<div class='analysis-box warning'><p>个股只保留八条关注主线内的核心样本，按午盘波动绝对值排序展示；公告事件以巨潮资讯网和交易所披露为准。</p></div>"
            + "".join(stock_sections),
        ),
        section(
            "watchlist",
            "我的重点关注股",
            '<div class="toolbar"><label>个股搜索 <input id="stockSearch" type="search" placeholder="输入股票名称或代码"></label></div>'
            + table(["股票", "午盘涨跌", "当前趋势", "午盘低点", "午盘高点", "判断标签", "下午观察"], watch_rows, "sortable searchable"),
        ),
        section(
            "technical",
            "技术面与关键价位",
            table(["标的", "当前价格", "5日线", "20日线", "RSI", "MACD / 趋势", "支撑位", "压力位"], tech_rows),
        ),
        section("plan", "下午交易观察计划", table(["观察项", "触发信号", "为什么重要"], plan_rows)),
        section("risk", "午后风险提示", table(["风险维度", "当前状态", "风险等级"], risk_rows)),
        section(
            "sources",
            "数据来源与免责声明",
            "<h3>数据来源</h3><ul class='source-list'>"
            + "".join(f'<li><a href="{esc(url)}">{esc(name)}</a></li>' for name, url in sources)
            + "</ul>"
            + f"""
            <div class="analysis-box warning">
              <p><b>数据更新时间：</b>{esc(generated_at)} 北京时间。</p>
              <p><b>午盘口径说明：</b>本报告在午间生成，行情、成交额、板块强弱和技术状态均可能随下午交易变化；收盘后仍需以收盘日报复核。</p>
              <p><b>数据缺失说明：</b>全A涨跌家数已改用新浪市场中心分页行情统计；涨跌停为按涨跌幅阈值近似统计。10年期中国国债收益率、ETF份额变化、北向资金旧式实时净额等未接入稳定官方结构化源，本版不做估算。</p>
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
      --shadow:0 12px 30px rgba(15,23,42,.08);
    }
    *{box-sizing:border-box} html{scroll-behavior:smooth} body{margin:0;background:var(--light-bg);color:var(--text-main);font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif}
    a{color:var(--blue);text-decoration:none}.hero{background:linear-gradient(135deg,#111827,#1f2937 55%,#0f172a);color:#fff;padding:28px 20px 18px}.hero-inner{max-width:1360px;margin:0 auto}.eyebrow{color:#cbd5e1;font-size:13px}.hero h1{font-size:34px;margin:8px 0;letter-spacing:0}.hero-sub{color:#d1d5db;margin:0 0 16px}.tags{display:flex;flex-wrap:wrap;gap:8px}.tag{display:inline-flex;align-items:center;border:1px solid rgba(255,255,255,.22);border-radius:999px;padding:4px 10px;font-weight:600;background:rgba(255,255,255,.08)}
    .status-chip{display:inline-flex;align-items:center;border-radius:999px;border:1px solid transparent;padding:3px 9px;font-size:12px;font-weight:700;white-space:nowrap}.status-strong{background:#fee2e2;color:#b42318;border-color:#fecaca}.status-hot{background:#fff7ed;color:#9a3412;border-color:#fed7aa}.status-watch{background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe}.status-risk{background:#fff1f2;color:#be123c;border-color:#fecdd3}.status-neutral{background:#f3f4f6;color:#4b5563;border-color:#e5e7eb}.risk-mid{background:#fff7ed;color:#9a3412;border-color:#fed7aa}.risk-high{background:#fee2e2;color:#991b1b;border-color:#fecaca}.data-ok{background:#ecfdf3;color:#166534;border-color:#bbf7d0}.data-missing{background:#f3f4f6;color:#4b5563;border-color:#e5e7eb}
    .top-nav{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.96);border-bottom:1px solid var(--border);backdrop-filter:blur(8px);overflow-x:auto;white-space:nowrap}.top-nav .nav-inner{max-width:1360px;margin:0 auto;display:flex;gap:6px;padding:9px 20px}.top-nav a{color:#374151;padding:5px 9px;border-radius:6px}.top-nav a:hover{background:#eef2ff}
    main{max-width:1360px;margin:18px auto 56px;padding:0 20px}.section-anchor{scroll-margin-top:58px}.section-card{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;margin:14px 0;box-shadow:var(--shadow);overflow:hidden}.section-card summary{cursor:pointer;display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--border)}.section-card h2{font-size:18px;margin:0}.chev{color:var(--text-sub);font-size:12px}.section-body{padding:16px 18px}.section-body h3{font-size:15px;margin:18px 0 8px;color:#1f2937}
    .summary-card{border-left:4px solid var(--blue);background:#f8fafc;border-radius:10px;padding:16px}.summary-card h3{margin-top:0}.summary-card p span{display:block;margin:6px 0}.state-line{margin-top:12px;padding:10px;border-radius:8px;background:#eef2ff;color:#1e3a8a}
    .metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:14px}.metric-card{border:1px solid var(--border);border-radius:10px;background:#fff;padding:14px;min-height:104px}.metric-title{color:var(--text-sub);font-size:12px}.metric-value{font-size:22px;font-weight:800;margin:6px 0}.metric-sub{color:var(--text-sub);font-size:12px}.metric-card.red{background:var(--red-bg)}.metric-card.green{background:var(--green-bg)}.metric-card.blue{background:#eff6ff}
    .table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:10px;background:#fff;margin:8px 0 12px}table{width:100%;border-collapse:collapse;min-width:760px}th,td{padding:9px 10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}th{position:sticky;top:0;background:#f9fafb;color:#374151;font-size:12px;white-space:nowrap;cursor:pointer}tr:nth-child(even) td{background:#fcfcfd}td.up,.up{color:var(--red);font-weight:700}td.down,.down{color:var(--green);font-weight:700}.neutral{color:var(--gray)}.missing{color:var(--text-sub);font-weight:500}
    .bar{position:relative;min-width:120px;height:22px;background:#f3f4f6;border-radius:5px;overflow:hidden}.bar span{position:absolute;left:0;top:0;bottom:0;opacity:.18}.bar b{position:relative;padding-left:8px;line-height:22px}.bar.up span{background:var(--red)}.bar.down span{background:var(--green)}
    .analysis-box{background:#f9fafb;border:1px solid var(--border);border-radius:10px;padding:12px;margin-top:10px;color:#374151}.warning{border-color:#fed7aa;background:#fff7ed}.toolbar{display:flex;justify-content:flex-end;margin-bottom:10px}.toolbar input{border:1px solid var(--border);border-radius:8px;padding:8px 10px;min-width:240px}.source-list{columns:2}#backTop{position:fixed;right:18px;bottom:18px;border:0;border-radius:999px;background:#111827;color:#fff;padding:10px 13px;box-shadow:var(--shadow);display:none;cursor:pointer}
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
  <title>A股午盘日报｜精简关注版｜{REPORT_DATE}</title>
  <style>{css}</style>
</head>
<body>
  <header class="hero">
    <div class="hero-inner">
      <div class="eyebrow">午盘观察 · 算力通信 · 有色资源 · 电力电网 · 银行国债 · 化工材料</div>
      <h1>A股午盘日报｜精简关注版｜{REPORT_DATE}</h1>
      <p class="hero-sub">生成时间：{esc(generated_at)} 北京时间｜午盘口径：当前行情接口数据，下午可能变化｜交易日判断：{"A股交易日" if trading_day else "非交易日或行情未更新"}</p>
      <div class="tags">
        <span class="tag">{esc(market_status)}</span>
        <span class="tag risk-mid">风险等级：{esc(risk_level)}</span>
        <span class="tag">{esc(turnover_tag)}</span>
        <span class="tag">午后仍需复核</span>
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
    html_doc, stats = build_midday_report()
    out = Path(f"A股午盘日报_{REPORT_DATE}.html")
    out.write_text(html_doc, encoding="utf-8")
    print("午盘日报生成成功：")
    print(f"文件路径：{out}")
    print(f"生成时间：{stats['generated_at']}")
    print(f"数据完整度：{stats['data_completeness']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
