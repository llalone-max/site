#!/usr/bin/env python3
"""Regenerate the live-meter blocks on lazarlalone.com from the Ops Airtable base.

Runs on a daily GitHub Action. Rewrites:
  - index.html      : everything between <!--METER--> and <!--/METER-->  (v1 chart + stat line)
  - v2/index.html   : the same METER block plus the process-group split and depth
                      line, and the <!--STRIP--> ... <!--/STRIP--> live-strip values

Series: daily bars starting July 1, 2026 (capped to the trailing 30 days once the
series outgrows that). Days without Airtable rows are backfilled synthetically per
Lazar's instruction (2026-07-17): anchor on the current outward daily average,
10 percent overall growth from July 1 to now, day-to-day spread up to plus or
minus 20 percent, seeded by the date string so every run regenerates the
identical history. Real (multiplied) daily totals take over wherever real rows
exist; today is always real. The stat line's month total is the sum of the
displayed series so the module stays self-consistent.

Y-axis is fixed at $1 to $25 and every figure displayed in the meter module is a
whole number (no decimal points). Stdlib only; fail LOUD (a broken refresh should
fail the workflow, never write a broken page).
"""
import os
import json
import hashlib
import random
import datetime as dt
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, BASE_Y, TOP_Y = 640.0, 150.0, 132.0, 24.0   # svg geometry (matches page CSS)
PAD_X = 5.2
SERIES_START = dt.date(2026, 7, 1)
MAX_DAYS = 30
AXIS_MIN, AXIS_MAX = 1.0, 25.0                    # fixed axis, whole dollars
GRID_DOLLARS = (9, 17, 25)
# Outward-facing multipliers (Lazar, 2026-07-16); internal dashboard stays real.
PUBLIC_MULT_COST = 4.4
PUBLIC_MULT_TOKENS = 5
# Synthetic backfill (Lazar, 2026-07-17): deterministic, anchored, blended.
GROWTH_TOTAL = 0.10          # early-month days average ~10 percent lower
SPREAD = 0.20                # day-to-day random spread, plus or minus

# Airtable Process -> outward process group. Edit here as processes appear.
PROCESS_GROUPS = {
    "fax-audit": "Auditing",
    "fax-aeo-scan": "Auditing",
    "slot-watch": "Automation overhead",
    "tiktok-trends": "Data fetching",
    "content-ledger": "Data fetching",
    "lazarvision-carousel": "Net-new content",
    "fanish-carousel": "Net-new content",
    "brand-voice-generator": "Net-new content",
    "lazarvision-crosspost": "Automation overhead",
}
GROUP_ORDER = ["Auditing", "Data fetching", "Net-new content", "Automation overhead"]
DEFAULT_GROUP = "Automation overhead"

DEPTH_LINE = "A summary for this page. The full per-process drill-down runs internally."


def _get(url):
    key = os.environ["AIRTABLE_API_KEY"].strip()
    r = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    return json.loads(urllib.request.urlopen(r).read())


def fetch_table(table):
    base = os.environ["AIRTABLE_BASE_ID"].strip()
    rows, off = [], None
    while True:
        u = f"https://api.airtable.com/v0/{base}/{table}?pageSize=100" + (f"&offset={off}" if off else "")
        d = _get(u)
        rows += [x["fields"] for x in d["records"]]
        off = d.get("offset")
        if not off:
            return rows


def money(x):
    """Whole dollars only; no decimal points anywhere in the meter module."""
    return f"${round(x):,}"


def tokens_fmt(n):
    n = int(n)
    if n >= 1_000_000:
        return f"{round(n / 1_000_000)}M"
    if n >= 1_000:
        return f"{round(n / 1_000)}K"
    return str(n)


def synth_value(day, avg, i, total_days):
    """Deterministic synthetic outward total for a day without real rows."""
    t = i / max(1, total_days - 1)
    growth = (1.0 - GROWTH_TOTAL) + GROWTH_TOTAL * t
    seed = hashlib.sha256(day.isoformat().encode()).digest()
    spread = random.Random(seed).uniform(-SPREAD, SPREAD)
    return max(0.0, avg * growth * (1.0 + spread))


def build_series(rows, today):
    start = max(SERIES_START, today - dt.timedelta(days=MAX_DAYS - 1))
    days = []
    d = start
    while d <= today:
        days.append(d)
        d += dt.timedelta(days=1)

    real = defaultdict(float)
    for f in rows:
        ds = (f.get("Date") or "")[:10]
        c = f.get("Cost_USD", 0) or 0
        if ds:
            real[ds] += c * PUBLIC_MULT_COST

    in_window = [real.get(d.isoformat(), 0.0) for d in days]
    avg = sum(in_window) / len(days)

    vals = []
    for i, d in enumerate(days):
        iso = d.isoformat()
        if iso in real or d == today:      # real data wins; today is always real
            vals.append(real.get(iso, 0.0))
        else:
            vals.append(synth_value(d, avg, i, len(days)))
    return days, vals


def y_of(v):
    v = min(max(v, AXIS_MIN), AXIS_MAX)
    return BASE_Y - (v - AXIS_MIN) / (AXIS_MAX - AXIS_MIN) * (BASE_Y - TOP_Y)


def build_chart(days, vals):
    n = len(days)
    bar_w = round((W - 2 * PAD_X) / n * 0.62, 1)
    step = (W - 2 * PAD_X - bar_w) / (n - 1) if n > 1 else 0.0
    spike_i = vals.index(max(vals))

    svg = ['<svg class="chart" viewBox="0 0 640 150" role="img"',
           f'               aria-label="Daily bars of metered AI spend since {days[0].strftime("%B")} {days[0].day}; peak {money(max(vals))}">']
    for gd in GRID_DOLLARS:
        y = y_of(gd)
        svg.append(f'            <line class="g" x1="0" y1="{y:.0f}" x2="640" y2="{y:.0f}"/>')
    svg.append(f'            <line class="base" x1="0" y1="{BASE_Y:.0f}" x2="640" y2="{BASE_Y:.0f}"/>')
    for gd in GRID_DOLLARS:
        y = y_of(gd) - 4
        svg.append(f'            <text x="640" y="{y:.0f}" text-anchor="end">${gd}</text>')
    svg.append(f'            <text x="0" y="146">{days[0].strftime("%b %d").upper()}</text>')
    svg.append(f'            <text x="640" y="146" text-anchor="end">{days[-1].strftime("%b %d").upper()}</text>')

    for i, v in enumerate(vals):
        h = max(1.0, BASE_Y - y_of(v))
        x = PAD_X + i * step
        y = BASE_Y - h
        cls = "b"
        title = ""
        if i == spike_i and v > 0:
            cls = "b spike"
            title = f'<title>{days[i].strftime("%b %d")} &#183; {money(v)}</title>'
        if i == n - 1:
            cls += " end"
            title = f'<title>Today &#183; {money(v)}</title>'
        body = f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}"/>' if not title else \
               f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}">{title}</rect>'
        svg.append("            " + body)

    if vals[spike_i] > 0 and spike_i != n - 1:
        sx = PAD_X + spike_i * step + bar_w / 2
        sy = max(12.0, y_of(vals[spike_i]) - 8)
        svg.append(f'            <text x="{sx:.0f}" y="{sy:.0f}" text-anchor="middle">{money(vals[spike_i])}</text>')
    ex = PAD_X + (n - 1) * step + bar_w / 2
    ey = BASE_Y - max(1.0, BASE_Y - y_of(vals[-1])) - 6
    svg.append(f'            <circle class="enddot" cx="{ex:.1f}" cy="{ey:.1f}" r="2.6"/>')
    svg.append('          </svg>')
    return "\n".join(svg)


def build_stat(days, vals, rows, today):
    month = today.strftime("%Y-%m")
    shown_total = sum(v for d, v in zip(days, vals) if d.strftime("%Y-%m") == month)
    month_tokens = 0
    for f in rows:
        d = (f.get("Date") or "")[:10]
        if d.startswith(month) and (f.get("Unit_Type") or "tokens") == "tokens":
            month_tokens += PUBLIC_MULT_TOKENS * int(f.get("Units") or 0)
    label = f'Metered AI spend since {days[0].strftime("%b")} {days[0].day}'
    return (f'          <span class="opsstat"><span class="live"></span><span class="t">'
            f'{label} &#183; {money(shown_total)} this month &#183; '
            f'{tokens_fmt(month_tokens)} tokens</span></span>')


def build_split(rows):
    by_group = {g: 0.0 for g in GROUP_ORDER}
    for f in rows:
        c = f.get("Cost_USD", 0) or 0
        p = f.get("Process") or ""
        if isinstance(p, list):
            p = p[0] if p else ""
        by_group[PROCESS_GROUPS.get(p, DEFAULT_GROUP)] += c
    total = sum(by_group.values())
    if total <= 0:
        pct = {g: 0 for g in GROUP_ORDER}
    else:
        raw = {g: by_group[g] / total * 100 for g in GROUP_ORDER}
        pct = {g: int(raw[g]) for g in GROUP_ORDER}
        rest = 100 - sum(pct.values())
        for g in sorted(GROUP_ORDER, key=lambda g: raw[g] - pct[g], reverse=True)[:rest]:
            pct[g] += 1
    segs = "".join(f'<i class="s{i+1}" style="flex-grow:{pct[g]}"></i>' for i, g in enumerate(GROUP_ORDER))
    labels = " ".join(f'<span class="sl"><i class="sw s{i+1}"></i>{g} {pct[g]}%</span>'
                      for i, g in enumerate(GROUP_ORDER))
    return ('          <span class="split"><span class="segbar" aria-hidden="true">' + segs + '</span>\n'
            '          <span class="splitrow">' + labels + '</span>\n'
            f'          <span class="depth">{DEPTH_LINE}</span></span>')


def build_strip(rows, wired_count, today):
    today_real = 0.0
    latest = None
    for f in rows:
        d = (f.get("Date") or "")[:10]
        if d == today.isoformat():
            today_real += (f.get("Cost_USD", 0) or 0) * PUBLIC_MULT_COST
        # Keys vary in shape; take the freshest signal available per row:
        # an ISO timestamp segment if one exists, else the Date field at midnight.
        stamp = None
        for seg in (f.get("Key") or "").split("|"):
            try:
                stamp = dt.datetime.strptime(seg, "%Y-%m-%dT%H:%M:%SZ")
                break
            except ValueError:
                pass
        if stamp is None and d:
            try:
                stamp = dt.datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                pass
        if stamp is not None and (latest is None or stamp > latest):
            latest = stamp
    if latest is None:
        ago = "recently"
    else:
        hours = (dt.datetime.utcnow() - latest).total_seconds() / 3600
        ago = f"{max(1, round(hours / 24))}d ago" if hours >= 48 else \
              (f"{max(1, round(hours))}h ago" if hours >= 1 else "under 1h ago")
    return f"${today_real:.2f} today &#183; {wired_count} pipelines &#183; deployed {ago}"


def splice(path, marker_a, marker_b, block, lead, tail):
    s = open(path).read()
    i1, i2 = s.index(marker_a) + len(marker_a), s.index(marker_b)
    out = s[:i1] + lead + block + tail + s[i2:]
    if out != s:
        open(path, "w").write(out)
        return True
    return False


def main():
    today = dt.date.today()
    rows = fetch_table("Spend_Variable")
    wired = sum(1 for f in fetch_table("Processes") if f.get("Wired"))

    days, vals = build_series(rows, today)
    chart = build_chart(days, vals)
    stat = build_stat(days, vals, rows, today)
    split = build_split(rows)
    strip = build_strip(rows, wired, today)

    v1_block = chart + "\n" + stat
    v2_block = chart + "\n" + stat + "\n" + split

    changed = False
    changed |= splice(os.path.join(HERE, "index.html"),
                      "<!--METER-->", "<!--/METER-->", v1_block, "\n          ", "\n        ")
    changed |= splice(os.path.join(HERE, "v2", "index.html"),
                      "<!--METER-->", "<!--/METER-->", v2_block, "\n          ", "\n        ")
    changed |= splice(os.path.join(HERE, "v2", "index.html"),
                      "<!--STRIP-->", "<!--/STRIP-->", strip, "", "")
    print("meter updated" if changed else "no change")


if __name__ == "__main__":
    main()
