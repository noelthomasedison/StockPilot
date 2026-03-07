from __future__ import annotations

from typing import Dict


def format_price(res: Dict) -> str:
    ccy = f" {res.get('currency')}" if res.get("currency") else ""
    return (
        f"**{res['ticker']}**\n\n"
        f"- Price: **{res['price']:.2f}{ccy}**\n"
        f"- Daily change: **{res['change']:+.2f}** (**{res['change_pct']:+.2f}%**)\n"
    )


def format_summary(res: Dict) -> str:
    return (
        f"**{res['ticker']} — {res['period']} performance**\n\n"
        f"- Start → End: **{res['start_close']:.2f} → {res['end_close']:.2f}**\n"
        f"- Return: **{res['return_pct']:+.2f}%**\n"
        f"- Volatility (ann.): **{res['volatility_pct']:.2f}%**\n"
        f"- Max drawdown: **{res['max_drawdown_pct']:.2f}%**\n"
        f"- Range (low–high): **{res['low']:.2f} – {res['high']:.2f}**\n"
    )


def format_compare(res: Dict) -> str:
    a = res["a"]
    b = res["b"]
    period = res["period"]
    return (
        f"**Comparison — {period}**\n\n"
        f"**{a['ticker']}**\n"
        f"- Price: **{a['price']:.2f}** (daily **{a['change_pct']:+.2f}%**)\n"
        f"- Return: **{a['return_pct']:+.2f}%** | Vol: **{a['volatility_pct']:.2f}%** | DD: **{a['max_drawdown_pct']:.2f}%**\n\n"
        f"**{b['ticker']}**\n"
        f"- Price: **{b['price']:.2f}** (daily **{b['change_pct']:+.2f}%**)\n"
        f"- Return: **{b['return_pct']:+.2f}%** | Vol: **{b['volatility_pct']:.2f}%** | DD: **{b['max_drawdown_pct']:.2f}%**\n"
    )


def format_news(res: Dict) -> str:
    items = res.get("items", [])
    if not items:
        return f"**News for:** {res.get('query','')}\n\n- No recent news found."
    lines = [f"**News for:** {res.get('query','')}\n"]
    for it in items:
        title = it.get("title", "Untitled")
        link = it.get("link", "")
        source = it.get("source")
        suffix = f" — {source}" if source else ""
        lines.append(f"- [{title}]({link}){suffix}")
    return "\n".join(lines)