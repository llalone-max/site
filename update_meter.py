#!/usr/bin/env python3
"""Regenerate the live-meter block on lazarlalone.com from the Ops Airtable base.

Runs on a daily GitHub Action. Rewrites:
  - ai.html : everything between <!--METER--> and <!--/METER--> on the AI
    operations lane (chart + stat line + the process-group split and depth line).
    The meter is the centerpiece of that dark terminal lane.

Layout notes:
  - The y-axis figures (9/17/25) sit in a clean right gutter; the plot is inset
    to its left so no bar, end dot, or end label overlaps them. The dollar sign
    is shown once, on the month total in the stat line, not on every figure.
  - The process split renders only genuinely non-zero buckets. A category that
    rounds to 0 percent is never drawn. PROCESS_GROUPS below is the editable map
    from Airtable Process to outward bucket; breadth comes from real data.

Series: daily bars starting July 1, 2026 (capped to the trailing 30 days once the
series outgrows that). Days without Airtable rows are backfilled synthetically per
Lazar's instruction (2026-07-17): anchor on the current outward daily average,
10 percent overall growth from July 1 to now, day-to-day spread up to plus or
minus 20 percent, seeded by the date string so every run regenerates the
identical history. Real (multiplied) daily totals take over wherever real rows
exist; today is always real. The stat line's month total is the sum of the
displayed series so the module stays self-consistent.

Y-axis AUTO-SCALES: each run picks the smallest clean whole-dollar ceiling
comfortably above the peak day, so the tallest bar always fits with headroom and
the chart fills the same vertical space smoothly whatever the numbers are. Every
figure displayed in the meter module is a whole number (no decimal points).
Stdlib only; fail LOUD (a broken refresh should fail the workflow, never write a
broken page).
"""
import os
import json
import math
import hashlib
import random
import datetime as dt
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, BASE_Y, TOP_Y = 640.0, 150.0, 132.0, 24.0   # svg geometry (matches page CSS)
GUTTER_R = 42.0                                    # right gutter reserved for $ labels
PLOT_W = W - GUTTER_R                              # bars/grid/dots stay left of the gutter
PAD_X = 5.2
SERIES_START = dt.date(2026, 7, 1)
MAX_DAYS = 30
AXIS_MIN = 0.0                                    # baseline is $0; the top auto-scales
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

DEPTH_LINE = "High-level for the purposes of this page. Full, per-process drill-down runs internally."


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


def whole(x):
    """Whole number, no dollar sign. The meter shows the $ once (on the month
    total); the y-axis and the in-chart peak label read as bare numbers so the
    dollar sign is not repeated on every figure."""
    return f"{round(x):,}"


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


def nice_axis_max(peak):
    """Smallest clean whole-dollar ceiling comfortably above the peak, so the
    tallest bar always fits with headroom and the axis fills the space smoothly."""
    if peak <= 0:
        return 6.0
    target = peak * 1.10
    mag = 10 ** math.floor(math.log10(target))
    for m in (1, 1.5, 2, 3, 4, 5, 6, 8, 10):
        cand = m * mag
        if cand >= target:
            return float(round(cand))
    return float(round(10 * mag))


def y_of(v, axis_max):
    v = min(max(v, AXIS_MIN), axis_max)
    return BASE_Y - (v - AXIS_MIN) / (axis_max - AXIS_MIN) * (BASE_Y - TOP_Y)


def build_chart(days, vals):
    n = len(days)
    avail = PLOT_W - PAD_X                          # plot ends before the right gutter
    bar_w = round(avail / n * 0.62, 1)
    step = (avail - bar_w) / (n - 1) if n > 1 else 0.0
    spike_i = vals.index(max(vals))
    axis_max = nice_axis_max(max(vals) if vals else 0.0)
    grids = [round(axis_max / 3), round(axis_max * 2 / 3), round(axis_max)]

    svg = ['          <svg class="chart" viewBox="0 0 640 150" role="img"',
           f'               aria-label="Daily bars of metered AI spend in US dollars since {days[0].strftime("%B")} {days[0].day}; peak {money(max(vals))}">']
    for gd in grids:
        y = y_of(gd, axis_max)
        svg.append(f'            <line class="g" x1="0" y1="{y:.0f}" x2="{PLOT_W:.0f}" y2="{y:.0f}"/>')
    svg.append(f'            <line class="base" x1="0" y1="{BASE_Y:.0f}" x2="{PLOT_W:.0f}" y2="{BASE_Y:.0f}"/>')
    for gd in grids:                                # bare axis figures in the right gutter; the title names the unit
        y = y_of(gd, axis_max) - 4
        svg.append(f'            <text x="640" y="{y:.0f}" text-anchor="end">{gd}</text>')
    svg.append(f'            <text x="0" y="146">{days[0].strftime("%b %d").upper()}</text>')
    svg.append(f'            <text x="{PLOT_W:.0f}" y="146" text-anchor="end">{days[-1].strftime("%b %d").upper()}</text>')

    for i, v in enumerate(vals):
        h = max(1.0, BASE_Y - y_of(v, axis_max))
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
        sy = max(12.0, y_of(vals[spike_i], axis_max) - 8)
        svg.append(f'            <text x="{sx:.0f}" y="{sy:.0f}" text-anchor="middle">{whole(vals[spike_i])}</text>')
    ex = PAD_X + (n - 1) * step + bar_w / 2
    ey = BASE_Y - max(1.0, BASE_Y - y_of(vals[-1], axis_max)) - 6
    svg.append(f'            <circle class="enddot" cx="{ex:.1f}" cy="{ey:.1f}" r="2.6"/>')
    svg.append('          </svg>')
    return "\n".join(svg)


def build_title():
    """Plain title above the chart, naming the unit in words.

    This used to end in a small filled amber chip reading "USD". A filled warning
    colour on a chip is the visual language of an error badge, and that is exactly
    how it read: as though the pipeline had thrown something. The unit belongs in
    the sentence.
    """
    return '          <span class="metertitle">Metered AI spend by day, in US dollars</span>' 


def build_stat(days, vals, rows, today):
    month = today.strftime("%Y-%m")
    shown_total = sum(v for d, v in zip(days, vals) if d.strftime("%Y-%m") == month)
    month_tokens = 0
    for f in rows:
        d = (f.get("Date") or "")[:10]
        if d.startswith(month) and (f.get("Unit_Type") or "tokens") == "tokens":
            month_tokens += PUBLIC_MULT_TOKENS * int(f.get("Units") or 0)
    since = f'{days[0].strftime("%b")} {days[0].day}'
    # the headline number reads first; the meta line is dimmer context
    return ('          <span class="opsstat"><span class="live"></span>'
            f'<span class="ostot"><em>{money(shown_total)}</em> metered this month</span>'
            f'<span class="osmeta">since {since} &#183; {tokens_fmt(month_tokens)} tokens</span></span>')


def build_split(rows):
    by_group = defaultdict(float)
    for f in rows:
        c = f.get("Cost_USD", 0) or 0
        p = f.get("Process") or ""
        if isinstance(p, list):
            p = p[0] if p else ""
        by_group[PROCESS_GROUPS.get(p, DEFAULT_GROUP)] += c
    total = sum(by_group.values())

    # Only buckets with real spend; known groups keep their editorial order,
    # any unmapped group that still carries spend comes after.
    present = [g for g in GROUP_ORDER if by_group.get(g, 0) > 0]
    present += [g for g in by_group if g not in GROUP_ORDER and by_group[g] > 0]
    if total <= 0 or not present:
        return ('          <span class="split"><span class="splithead">Where the spend goes</span>\n'
                '          <span class="segbar" aria-hidden="true"></span>\n'
                '          <span class="splitrow"></span>\n'
                f'          <span class="depth">{DEPTH_LINE}</span></span>')

    raw = {g: by_group[g] / total * 100 for g in present}
    pct = {g: int(raw[g]) for g in present}
    rest = 100 - sum(pct.values())
    for g in sorted(present, key=lambda g: raw[g] - pct[g], reverse=True)[:rest]:
        pct[g] += 1
    # never render a category that rounds to 0 percent
    present = [g for g in present if pct[g] > 0]
    # biggest share first, so the darkest swatch leads
    present.sort(key=lambda g: pct[g], reverse=True)

    segs = "".join(f'<i class="s{i+1}" style="flex-grow:{pct[g]}"></i>' for i, g in enumerate(present))
    labels = " ".join(f'<span class="sl"><i class="sw s{i+1}"></i>{g} <b>{pct[g]}%</b></span>'
                      for i, g in enumerate(present))
    return ('          <span class="split"><span class="splithead">Where the spend goes</span>\n'
            '          <span class="segbar" aria-hidden="true">' + segs + '</span>\n'
            '          <span class="splitrow">' + labels + '</span>\n'
            f'          <span class="depth">{DEPTH_LINE}</span></span>')


def splice(path, marker_a, marker_b, block, lead, tail):
    s = open(path).read()
    i1, i2 = s.index(marker_a) + len(marker_a), s.index(marker_b)
    out = s[:i1] + lead + block + tail + s[i2:]
    if out != s:
        open(path, "w").write(out)
        return True
    return False


def log_processes(rows):
    """Log the actual Airtable Process names and their share, to guide PROCESS_GROUPS."""
    by_proc, by_group = defaultdict(float), defaultdict(float)
    for f in rows:
        c = f.get("Cost_USD", 0) or 0
        p = f.get("Process") or ""
        if isinstance(p, list):
            p = p[0] if p else ""
        by_proc[p] += c
        by_group[PROCESS_GROUPS.get(p, DEFAULT_GROUP)] += c
    tot = sum(by_proc.values()) or 1.0
    print("process names present (real cost, share):")
    for p, v in sorted(by_proc.items(), key=lambda x: -x[1]):
        grp = PROCESS_GROUPS.get(p, DEFAULT_GROUP)
        print(f"  {p or '(blank)':28} ${v:8.4f}  {100*v/tot:5.1f}%  -> {grp}")
    print("bucket rollup:")
    for g, v in sorted(by_group.items(), key=lambda x: -x[1]):
        print(f"  {g:28} ${v:8.4f}  {100*v/tot:5.1f}%")


def main():
    today = dt.date.today()
    rows = fetch_table("Spend_Variable")
    log_processes(rows)

    days, vals = build_series(rows, today)
    title = build_title()
    chart = build_chart(days, vals)
    stat = build_stat(days, vals, rows, today)
    split = build_split(rows)

    block = title + "\n" + chart + "\n" + stat + "\n" + split

    changed = splice(os.path.join(HERE, "ai.html"),
                     "<!--METER-->", "<!--/METER-->", block, "\n", "\n        ")
    print("meter updated" if changed else "no change")


if __name__ == "__main__":
    main()
