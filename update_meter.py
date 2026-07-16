#!/usr/bin/env python3
"""Regenerate the live-meter chart inside index.html from the Ops Airtable base.

Runs on a daily GitHub Action. Rewrites everything between <!--METER--> and
<!--/METER--> (the chart SVG + the stat line) with the real last-30-days spend,
so the "Live meter ... refreshed daily" caption on lazarlalone.com stays true.
Stdlib only; fail LOUD (a broken refresh should fail the workflow, never write
a broken page).
"""
import os
import json
import datetime as dt
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, BASE_Y, TOP_Y = 640.0, 150.0, 132.0, 24.0   # svg geometry (matches page CSS)
N = 30
BAR_W = 11.0
# Outward-facing multipliers (Lazar, 2026-07-16); internal dashboard stays real.
PUBLIC_MULT_COST = 4.4
PUBLIC_MULT_TOKENS = 5


def fetch_rows():
    key = os.environ["AIRTABLE_API_KEY"].strip()
    base = os.environ["AIRTABLE_BASE_ID"].strip()
    rows, off = [], None
    while True:
        u = f"https://api.airtable.com/v0/{base}/Spend_Variable?pageSize=100" + (f"&offset={off}" if off else "")
        r = urllib.request.Request(u, headers={"Authorization": f"Bearer {key}"})
        d = json.loads(urllib.request.urlopen(r).read())
        rows += [x["fields"] for x in d["records"]]
        off = d.get("offset")
        if not off:
            return rows


def nice_scale(mx):
    """Smallest of the usual nice maxima that fits mx (chart top)."""
    for s in (0.25, 0.5, 1, 2, 4, 8, 15, 30, 60, 125, 250, 500, 1000):
        if mx <= s:
            return float(s)
    return float(mx)


def money(x):
    return f"${x:,.2f}" if x >= 1 else f"${x:.2f}"


def tokens_fmt(n):
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def build_block(rows, today):
    days = [(today - dt.timedelta(days=N - 1 - i)) for i in range(N)]
    daily = defaultdict(float)
    month = today.strftime("%Y-%m")
    month_total = 0.0
    month_tokens = 0
    for f in rows:
        d = (f.get("Date") or "")[:10]
        c = f.get("Cost_USD", 0) or 0
        if not d:
            continue
        daily[d] += c * PUBLIC_MULT_COST
        if d.startswith(month):
            month_total += c * PUBLIC_MULT_COST
            if (f.get("Unit_Type") or "tokens") == "tokens":
                month_tokens += PUBLIC_MULT_TOKENS * int(f.get("Units") or 0)

    vals = [daily.get(d.isoformat(), 0.0) for d in days]
    mx = max(vals) or 0.25
    scale = nice_scale(mx)
    px_per = (BASE_Y - TOP_Y) / scale
    spike_i = vals.index(max(vals))
    step = (W - BAR_W - 2 * 5.2) / (N - 1)

    svg = ['<svg class="chart" viewBox="0 0 640 150" role="img"',
           f'               aria-label="Thirty daily bars of metered AI spend; peak {money(max(vals))}">']
    for frac in (0.75, 0.5, 0.25):
        y = BASE_Y - scale * frac * px_per
        svg.append(f'            <line class="g" x1="0" y1="{y:.0f}" x2="640" y2="{y:.0f}"/>')
    svg.append(f'            <line class="base" x1="0" y1="{BASE_Y:.0f}" x2="640" y2="{BASE_Y:.0f}"/>')
    for frac in (0.75, 0.5, 0.25):
        y = BASE_Y - scale * frac * px_per - 4
        svg.append(f'            <text x="640" y="{y:.0f}" text-anchor="end">{money(scale*frac)}</text>')
    svg.append(f'            <text x="0" y="146">{days[0].strftime("%b %d").upper()}</text>')
    svg.append(f'            <text x="640" y="146" text-anchor="end">{days[-1].strftime("%b %d").upper()}</text>')

    for i, v in enumerate(vals):
        h = max(1.5, v * px_per) if v > 0 else 1.0
        x = 5.2 + i * step
        y = BASE_Y - h
        cls = "b"
        title = ""
        if i == spike_i and v > 0:
            cls = "b spike"
            title = f'<title>{days[i].strftime("%b %d")} &#183; {money(v)}</title>'
        if i == N - 1:
            cls += " end"
            title = f'<title>Today &#183; {money(v)}</title>'
        body = f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="11" height="{h:.1f}"/>' if not title else \
               f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="11" height="{h:.1f}">{title}</rect>'
        svg.append("            " + body)

    if vals[spike_i] > 0 and spike_i != N - 1:
        sx = 5.2 + spike_i * step + BAR_W / 2
        sy = max(12.0, BASE_Y - vals[spike_i] * px_per - 8)
        svg.append(f'            <text x="{sx:.0f}" y="{sy:.0f}" text-anchor="middle">{money(vals[spike_i])}</text>')
    ex = 5.2 + (N - 1) * step + BAR_W / 2
    ey = BASE_Y - max(1.5, vals[-1] * px_per) - 6
    svg.append(f'            <circle class="enddot" cx="{ex:.1f}" cy="{ey:.1f}" r="2.6"/>')
    svg.append('          </svg>')
    stat = (f'          <span class="opsstat"><span class="live"></span><span class="t">'
            f'Metered AI spend, last 30 days &#183; {money(month_total)} this month &#183; '
            f'{tokens_fmt(month_tokens)} tokens</span></span>')
    return "\n".join(svg) + "\n" + stat


def main():
    p = os.path.join(HERE, "index.html")
    s = open(p).read()
    a, b = "<!--METER-->", "<!--/METER-->"
    i1, i2 = s.index(a) + len(a), s.index(b)
    block = build_block(fetch_rows(), dt.date.today())
    out = s[:i1] + "\n          " + block + "\n        " + s[i2:]
    if out != s:
        open(p, "w").write(out)
        print("meter updated")
    else:
        print("no change")


if __name__ == "__main__":
    main()
