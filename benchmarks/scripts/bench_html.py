#!/usr/bin/env python3
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark HTML Report
#
# Renders the aggregated benchmark results as a self contained HTML page - a
# table of results plus charts comparing the flavours. Charts are inline SVG, so
# the page needs no scripts, no network and no image files.

from __future__ import annotations

import datetime
import html
import platform

try:
    from avl.tools.coverage_analysis import logo
except Exception:  # pragma: no cover - report should still render without avl
    logo = ""

# House palette, matching the AVL coverage and trace reports.
NAVY = "#0b2c52"
BLUE = "#4a82c4"
BLUE_LIGHT = "#9fc2e8"
SLOWER = "#b3261e"
SERIES_COLOURS = [NAVY, BLUE, BLUE_LIGHT]

# The flavours AVL is charted against at the top of the page, in the order they
# appear there. One that was not run is simply left out.
OPPONENTS = [("sv", "SystemVerilog"), ("pyuvm", "pyuvm / pyvsc")]

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  --navy: #0b2c52;
  --blue: #4a82c4;
  --blue-light: #cfe3ff;
  --blue-pale: #eef4fc;
  --grey: #838383;
  --bg: #eef1f5;
  --panel: #ffffff;
  --border: #dde3ea;
  --text: #26313d;
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color: var(--text);
  background: var(--bg);
}

.app-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  height: 60px;
  padding: 0 1.25rem;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 4px rgba(20, 30, 50, 0.06);
}
.app-header img { height: 34px; width: auto; display: block; }
.app-header h1 { font-size: 1.05rem; font-weight: 600; margin: 0; color: var(--navy); }

.content { padding: 1rem 1.25rem; display: flex; flex-direction: column; gap: 1rem; }

.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.panel-header {
  padding: 0.6rem 1.1rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.panel-header h2 { font-size: 0.95rem; margin: 0; color: var(--navy); }
.panel-header .panel-subtitle { font-size: 0.8rem; color: var(--grey); }
.panel-body { padding: 0.9rem 1.1rem; }
.table-scroll { overflow-x: auto; padding: 0 1.1rem 0.9rem; }

table { width: 100%; border-collapse: collapse; font-size: 0.82rem; font-variant-numeric: tabular-nums; }
thead th {
  background: var(--blue-pale);
  color: var(--navy);
  text-align: left;
  padding: 0.5rem 0.6rem;
  font-weight: 600;
  white-space: nowrap;
  border-bottom: 1px solid var(--border);
}
tbody td { padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--border); white-space: nowrap; }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: var(--blue-pale); }
td.num, th.num { text-align: right; }
td.best { color: var(--navy); font-weight: 600; }
td.fail { color: #b3261e; font-weight: 600; }

.meta { display: flex; flex-wrap: wrap; gap: 1.5rem; font-size: 0.8rem; color: var(--grey); }
.meta b { color: var(--text); font-weight: 600; }

.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1.25rem; }
.charts-wide { max-width: 900px; }
.charts-wide svg { width: 100%; height: auto; display: block; }
.charts-head { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 1.5rem; align-items: start; max-width: 1500px; }
.chart-note { margin: 0.6rem 0 0; max-width: 900px; }
figure { margin: 0; }
figcaption { font-size: 0.82rem; font-weight: 600; color: var(--navy); margin-bottom: 0.35rem; }
figure svg { width: 100%; height: auto; display: block; }

.legend { display: flex; gap: 0.9rem; flex-wrap: wrap; font-size: 0.75rem; color: var(--grey); margin-top: 0.3rem; }
.legend span { display: inline-flex; align-items: center; gap: 0.3rem; }
.legend i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }

.notes { font-size: 0.8rem; color: var(--grey); line-height: 1.55; }
.notes p { margin: 0 0 0.6rem; }
.notes p:last-child { margin-bottom: 0; }
.notes b { color: var(--text); }
</style>
</head>
<body>
<header class="app-header">
__LOGO__
<h1>__TITLE__</h1>
</header>
<div class="content">
__BODY__
</div>
</body>
</html>
"""


def esc(value) -> str:
    return html.escape(str(value))


def svg_bar_chart(categories: list[str], series: list[tuple[str, list[float]]],
                  unit: str = "", width: int = 480) -> str:
    """Grouped horizontal bar chart as inline SVG."""
    label_w = 74
    value_w = 66
    bar_h = 17
    bar_gap = 4
    group_gap = 14
    top = 6

    plot_w = width - label_w - value_w
    group_h = len(series) * bar_h + (len(series) - 1) * bar_gap
    height = top + len(categories) * (group_h + group_gap)

    peak = max((v for _, values in series for v in values), default=0.0)
    scale = (plot_w / peak) if peak > 0 else 0.0

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'preserveAspectRatio="xMinYMin meet" xmlns="http://www.w3.org/2000/svg">'
    ]

    y = top
    for index, category in enumerate(categories):
        # Category label, vertically centred on its group of bars.
        parts.append(
            f'<text x="{label_w - 8}" y="{y + group_h / 2:.1f}" text-anchor="end" '
            f'dominant-baseline="middle" font-size="11" fill="{NAVY}" '
            f'font-weight="600">{esc(category)}</text>'
        )

        for s, (name, values) in enumerate(series):
            value = values[index]
            bar_w = max(value * scale, 1.0) if value > 0 else 1.0
            colour = SERIES_COLOURS[s % len(SERIES_COLOURS)]
            bar_y = y + s * (bar_h + bar_gap)

            parts.append(
                f'<rect x="{label_w}" y="{bar_y}" width="{bar_w:.1f}" height="{bar_h}" '
                f'rx="2" fill="{colour}"><title>{esc(name)}: {value:,.3f}{esc(unit)}</title></rect>'
            )
            parts.append(
                f'<text x="{label_w + bar_w + 6:.1f}" y="{bar_y + bar_h / 2:.1f}" '
                f'dominant-baseline="middle" font-size="10.5" fill="#45505c">'
                f'{_fmt(value)}{esc(unit)}</text>'
            )

        y += group_h + group_gap

    parts.append("</svg>")
    return "".join(parts)


def svg_diverging_chart(categories: list[str], values: list[float], width: int = 760) -> str:
    """Signed percentage bars either side of a zero line.

    A single wildly larger magnitude - which happens when one side is close to
    the measurement floor - would flatten every other bar to nothing, so the
    scale is capped just past the second largest and anything beyond it is drawn
    to the cap with a chevron. The label always carries the true figure.
    """
    label_w = 112
    margin = 10
    row_h = 30
    bar_h = 17
    top = 8
    text_gutter = 66

    plot_w = width - label_w - margin
    centre = label_w + plot_w / 2
    half = plot_w / 2 - text_gutter
    height = top + len(categories) * row_h + 4

    magnitudes = sorted((abs(v) for v in values), reverse=True)
    cap = magnitudes[0] if magnitudes else 0.0
    if len(magnitudes) > 1 and magnitudes[0] > 3 * magnitudes[1]:
        cap = magnitudes[1] * 1.2
    scale = (half / cap) if cap > 0 else 0.0

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'preserveAspectRatio="xMinYMin meet" xmlns="http://www.w3.org/2000/svg">'
    ]

    # Zero line, behind the bars.
    parts.append(
        f'<line x1="{centre:.1f}" y1="{top - 4}" x2="{centre:.1f}" y2="{height - 6}" '
        f'stroke="#c7d2de" stroke-width="1"/>'
    )

    for index, (category, value) in enumerate(zip(categories, values, strict=True)):
        y = top + index * row_h
        mid = y + bar_h / 2

        parts.append(
            f'<text x="{label_w - 10}" y="{mid:.1f}" text-anchor="end" '
            f'dominant-baseline="middle" font-size="11.5" fill="{NAVY}" '
            f'font-weight="600">{esc(category)}</text>'
        )

        clipped = abs(value) > cap
        drawn = min(abs(value), cap) * scale
        drawn = max(drawn, 1.0)
        positive = value >= 0
        colour = NAVY if positive else SLOWER

        x = centre if positive else centre - drawn
        parts.append(
            f'<rect x="{x:.1f}" y="{y}" width="{drawn:.1f}" height="{bar_h}" rx="2" '
            f'fill="{colour}"><title>{esc(category)}: {_signed(value)}</title></rect>'
        )

        if clipped:
            tip = centre + drawn + 3 if positive else centre - drawn - 3
            direction = 1 if positive else -1
            parts.append(
                f'<path d="M {tip:.1f} {y + 2} l {5 * direction} {bar_h / 2 - 2} '
                f'l {-5 * direction} {bar_h / 2 - 2} z" fill="{colour}" opacity="0.55"/>'
            )

        label_x = centre + drawn + 10 if positive else centre - drawn - 10
        anchor = "start" if positive else "end"
        parts.append(
            f'<text x="{label_x:.1f}" y="{mid:.1f}" text-anchor="{anchor}" '
            f'dominant-baseline="middle" font-size="11" fill="#45505c">'
            f'{esc(_signed(value))}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def _signed(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    magnitude = abs(value)
    figure = f"{magnitude:.1f}" if magnitude < 10 else f"{magnitude:,.0f}"
    return f"{sign}{figure}%"


def svg_range_chart(categories: list[str], ranges: list[tuple[float, float, float]],
                    unit: str = "", width: int = 480) -> str:
    """Min to max range with a median marker, one row per category."""
    label_w = 74
    value_w = 66
    row_h = 28
    top = 8

    plot_w = width - label_w - value_w
    height = top + len(categories) * row_h + 4

    peak = max((high for _, _, high in ranges), default=0.0)
    scale = (plot_w / peak) if peak > 0 else 0.0

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'preserveAspectRatio="xMinYMin meet" xmlns="http://www.w3.org/2000/svg">'
    ]

    for index, category in enumerate(categories):
        low, median, high = ranges[index]
        y = top + index * row_h + row_h / 2

        parts.append(
            f'<text x="{label_w - 8}" y="{y:.1f}" text-anchor="end" dominant-baseline="middle" '
            f'font-size="11" fill="{NAVY}" font-weight="600">{esc(category)}</text>'
        )

        x0 = label_w + low * scale
        x1 = label_w + high * scale
        parts.append(
            f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{max(x1, x0 + 1):.1f}" y2="{y:.1f}" '
            f'stroke="{BLUE_LIGHT}" stroke-width="7" stroke-linecap="round"/>'
        )
        for x in (x0, x1):
            parts.append(
                f'<line x1="{x:.1f}" y1="{y - 6:.1f}" x2="{x:.1f}" y2="{y + 6:.1f}" '
                f'stroke="{BLUE}" stroke-width="1.5"/>'
            )
        parts.append(
            f'<circle cx="{label_w + median * scale:.1f}" cy="{y:.1f}" r="4" fill="{NAVY}">'
            f'<title>median {median:,.3f}{esc(unit)} (min {low:,.3f}, max {high:,.3f})</title></circle>'
        )
        parts.append(
            f'<text x="{max(x1, x0 + 1) + 6:.1f}" y="{y:.1f}" dominant-baseline="middle" '
            f'font-size="10.5" fill="#45505c">{_fmt(median)}{esc(unit)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def _fmt(value: float) -> str:
    if value == 0:
        return "0"
    if value >= 1000:
        return f"{value:,.0f}"
    if value >= 10:
        return f"{value:.1f}"
    if value >= 1:
        return f"{value:.2f}"
    return f"{value:.3f}"


def legend(names: list[str]) -> str:
    items = "".join(
        f'<span><i style="background:{SERIES_COLOURS[i % len(SERIES_COLOURS)]}"></i>{esc(n)}</span>'
        for i, n in enumerate(names)
    )
    return f'<div class="legend">{items}</div>'


def figure(caption: str, svg: str, names: list[str] | None = None) -> str:
    tail = legend(names) if names and len(names) > 1 else ""
    return f'<figure><figcaption>{esc(caption)}</figcaption>{svg}{tail}</figure>'


def table(headers: list[str], rows: list[list], numeric: set[int],
          highlight: dict[int, set[int]] | None = None) -> str:
    highlight = highlight or {}

    head = "".join(
        f'<th class="num">{esc(h)}</th>' if i in numeric else f"<th>{esc(h)}</th>"
        for i, h in enumerate(headers)
    )

    body = []
    for r, row in enumerate(rows):
        cells = []
        for i, cell in enumerate(row):
            classes = ["num"] if i in numeric else []
            if i in highlight and r in highlight[i]:
                classes.append("best")
            attr = f' class="{" ".join(classes)}"' if classes else ""
            cells.append(f"<td{attr}>{esc(cell)}</td>")
        body.append(f"<tr>{''.join(cells)}</tr>")

    return (
        '<div class="table-scroll"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def panel(title: str, subtitle: str, body: str, padded: bool = True) -> str:
    inner = f'<div class="panel-body">{body}</div>' if padded else body
    sub = f'<span class="panel-subtitle">{esc(subtitle)}</span>' if subtitle else ""
    return f'<section class="panel"><div class="panel-header"><h2>{esc(title)}</h2>{sub}</div>{inner}</section>'


def head_to_head(nets: list[dict], benchmarks: list[str],
                 opponent: str) -> tuple[list[str], list[float]]:
    """AVL against one other flavour, benchmark by benchmark.

    The figure is the difference in time per randomization, expressed
    symmetrically so that twice as fast reads +100% and half as fast reads
    -100%. Benchmarks the opponent did not run are left out.
    """
    labels = []
    deltas = []
    for benchmark in benchmarks:
        entries = {n["flavour"]: n for n in nets if n["benchmark"] == benchmark}
        avl = entries.get("avl")
        other = entries.get(opponent)
        if avl is None or other is None:
            continue

        ours, theirs = avl["per_iter_us"], other["per_iter_us"]
        if ours <= 0 or theirs <= 0:
            continue

        labels.append(benchmark.split("/")[-1])
        deltas.append((theirs / ours - 1) * 100 if ours <= theirs else -((ours / theirs - 1) * 100))

    return labels, deltas


def is_clipped(deltas: list[float]) -> bool:
    """Whether svg_diverging_chart will have to cap a bar to keep the rest legible."""
    magnitudes = sorted((abs(d) for d in deltas), reverse=True)
    return len(magnitudes) > 1 and magnitudes[0] > 3 * magnitudes[1]


def render(title: str, nets: list[dict], raws: list[dict], rows: list[dict],
           quality: list[dict] | None = None,
           quality_summary: list[dict] | None = None) -> str:
    """Build the whole page.

    nets            - one entry per benchmark and flavour, randomization cost only
    raws            - one entry per benchmark, flavour and phase, as measured
    rows            - every individual run, used for the run to run spread
    quality         - one entry per benchmark, flavour and field, spread of the draws
    quality_summary - the worst field per benchmark and flavour
    """
    quality = quality or []
    quality_summary = quality_summary or []
    benchmarks = sorted({n["benchmark"] for n in nets})
    iterations = sorted({n["iterations"] for n in nets})
    tools = sorted({n["tool"] for n in nets})
    repeats = sorted({r["repeats"] for r in raws})

    body = []

    # ------------------------------------------------------------- head to head
    # Time per randomization, AVL against each of the other flavours, side by
    # side. Expressed symmetrically, so twice as fast reads +100% and half as
    # fast reads -100%.
    comparisons = []
    for opponent, caption in OPPONENTS:
        labels, deltas = head_to_head(nets, benchmarks, opponent)
        if deltas:
            comparisons.append((caption, labels, deltas))

    if comparisons:
        clipped = any(is_clipped(deltas) for _, _, deltas in comparisons)

        note = (
            "Bars are capped just past the second largest so one outlier cannot flatten the "
            "rest; a chevron marks a capped bar and its label carries the true figure. "
            if clipped else ""
        )

        # One comparison on its own is given the width the page used to give it.
        width = 680 if len(comparisons) > 1 else 760
        charts = "".join(
            figure(f"AVL against {caption}", svg_diverging_chart(labels, deltas, width=width))
            for caption, labels, deltas in comparisons
        )

        body.append(panel(
            "Head to head",
            "time per randomization, harness subtracted",
            f'<div class="{"charts-head" if len(comparisons) > 1 else "charts-wide"}">'
            f"{charts}</div>"
            '<div class="legend">'
            f'<span><i style="background:{NAVY}"></i>AVL faster</span>'
            f'<span><i style="background:{SLOWER}"></i>AVL slower</span>'
            "</div>"
            f'<p class="notes chart-note">Symmetric, so twice as fast reads +100% and half as '
            f"fast reads -100%. {note}</p>",
        ))

    # ------------------------------------------------------- randomization quality
    if quality_summary:
        benches = sorted({q["benchmark"] for q in quality_summary})
        flavours = sorted({q["flavour"] for q in quality_summary})
        labels = [b.split("/")[-1] for b in benches]

        def series(metric):
            return [(f, [next((q[metric] for q in quality_summary
                               if q["benchmark"] == b and q["flavour"] == f), 0.0)
                         for b in benches]) for f in flavours]

        charts = [
            figure("Bit skew - lower is better",
                   svg_bar_chart(labels, series("bit_skew"), "", width=520), flavours),
            figure("Entropy - 1.00 is a flat spread",
                   svg_bar_chart(labels, series("entropy"), "", width=520), flavours),
        ]

        headers = ["benchmark", "flavour", "field", "width", "draws", "distinct", "entropy",
                   "bit skew"]
        table_rows = [[q["benchmark"], q["flavour"], q["field"], q["width"], f"{q['draws']:,}",
                       f"{q['distinct']:.3f}", f"{q['entropy']:.3f}", f"{q['bit_skew']:.3f}"]
                      for q in quality]

        body.append(panel(
            "Quality of randomization",
            "measured on a separate untimed run",
            f'<div class="charts">{"".join(charts)}</div>'
            '<p class="notes chart-note">A solver can be made much faster by exploring less, or '
            'by leaving the bits a constraint does not pin at whatever it reaches for first, and '
            'a timing measurement cannot see either. <b>Entropy</b> is the spread of the values '
            'drawn, normalised so 1.00 is flat across every value any flavour managed for that '
            'field. <b>Bit skew</b> is how far the flavour strays from what the others agree on '
            'for any one bit, ignoring bits the constraints pinned - which is where a cheaper '
            'strategy shows up. Neither can see a bias every flavour shares.</p>'
            + table(headers, table_rows, numeric=set(range(3, 8))),
        ))

    # ---------------------------------------------------------------- summary
    body.append(panel(
        "Run",
        "",
        '<div class="meta">'
        f'<span>Generated <b>{esc(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))}</b></span>'
        f'<span>Host <b>{esc(platform.node())}</b></span>'
        f'<span>Platform <b>{esc(platform.system())} {esc(platform.machine())}</b></span>'
        f'<span>Simulator <b>{esc(", ".join(tools))}</b></span>'
        f'<span>Benchmarks <b>{len(benchmarks)}</b></span>'
        f'<span>Randomizations per run <b>{esc(", ".join(str(i) for i in iterations))}</b></span>'
        f'<span>Runs per testbench <b>{esc(", ".join(str(r) for r in repeats))}</b></span>'
        "</div>",
    ))

    # ------------------------------------------------------------- net results
    headers = ["benchmark", "flavour", "simulator", "iterations", "real (s)", "user (s)",
               "sys (s)", "cpu (%)", "us / randomization", "relative", "harness (s)"]
    table_rows = []
    best_rows = set()
    for i, n in enumerate(nets):
        if n["relative"] == 1.0:
            best_rows.add(i)
        table_rows.append([
            n["benchmark"], n["flavour"], n["tool"], f"{n['iterations']:,}",
            f"{n['real_s']:.3f}", f"{n['user_s']:.3f}", f"{n['sys_s']:.3f}",
            f"{n['cpu_pct']:.1f}", f"{n['per_iter_us']:,.1f}",
            f"{n['relative']:.2f}x" if n["relative"] else "-",
            f"{n['overhead_s']:.3f}",
        ])

    body.append(panel(
        "Cost of randomization",
        "harness subtracted - this is the solver alone",
        table(headers, table_rows, numeric=set(range(3, 11)), highlight={8: best_rows}),
        padded=False,
    ))

    # ----------------------------------------------------------------- charts
    for benchmark in benchmarks:
        entries = [n for n in nets if n["benchmark"] == benchmark]
        labels = [n["flavour"] for n in entries]

        charts = [
            figure(
                "Time per randomization",
                svg_bar_chart(labels, [("us", [n["per_iter_us"] for n in entries])], " us"),
            ),
            figure(
                "CPU time consumed",
                svg_bar_chart(
                    labels,
                    [("user", [n["user_s"] for n in entries]),
                     ("system", [n["sys_s"] for n in entries])],
                    " s",
                ),
                ["user", "system"],
            ),
            figure(
                "Cores used",
                svg_bar_chart(labels, [("cpu", [n["cpu_pct"] for n in entries])], " %"),
            ),
        ]

        # Run to run spread of the measured runs, before the harness is removed.
        ranges = []
        for n in entries:
            reals = sorted(
                r["real_s"] for r in rows
                if r["benchmark"] == benchmark and r["flavour"] == n["flavour"]
                and r["phase"] == "run" and r["status"] == "ok"
            )
            if reals:
                mid = reals[len(reals) // 2] if len(reals) % 2 else (
                    reals[len(reals) // 2 - 1] + reals[len(reals) // 2]) / 2
                ranges.append((reals[0], mid, reals[-1]))
            else:
                ranges.append((0.0, 0.0, 0.0))

        charts.append(figure(
            "Wall clock spread across runs",
            svg_range_chart(labels, ranges, " s"),
        ))

        body.append(panel(
            benchmark,
            f"{entries[0]['iterations']:,} randomizations per run",
            f'<div class="charts">{"".join(charts)}</div>',
        ))

    # ------------------------------------------------------------ raw results
    headers = ["benchmark", "flavour", "simulator", "phase", "iterations", "runs", "real (s)",
               "user (s)", "sys (s)", "cpu (%)", "rss (MB)", "failed"]
    table_rows = [[
        r["benchmark"], r["flavour"], r["tool"], r["phase"], f"{r['iterations']:,}",
        r["repeats"], f"{r['real_s']:.3f}", f"{r['user_s']:.3f}", f"{r['sys_s']:.3f}",
        f"{r['cpu_pct']:.1f}", f"{r['max_rss_kb'] / 1024:.1f}", r["failed"] or "",
    ] for r in raws]

    body.append(panel(
        "As measured",
        "including simulator and interpreter startup",
        table(headers, table_rows, numeric=set(range(4, 12))),
        padded=False,
    ))

    # ------------------------------------------------------------------ notes
    body.append(panel(
        "How this is measured",
        "",
        '<div class="notes">'
        "<p>Every flavour of a benchmark compiles the <b>same RTL</b> and runs the <b>same "
        "harness</b>, which drives clock and reset and randomizes once per rising edge. The only "
        "difference is where the randomization happens: the <b>sv</b> flavour randomizes inside the "
        "RTL with SystemVerilog classes and constraints solved by the simulator, the <b>avl</b> "
        "flavour randomizes the identical object from Python with AVL, and the <b>pyuvm</b> flavour "
        "randomizes it again as a pyvsc randobj, from the run_phase of a pyuvm test. Everything "
        "else - the simulator, the elaboration, the clock, the loop - is common.</p>"
        "<p>Each testbench is measured twice. The <b>baseline</b> drives exactly the same number of "
        "clock cycles with randomization switched off, so it captures startup, elaboration, cocotb "
        "bringup and the cost of the loop itself. The <b>run</b> does the same with randomization "
        "on. The difference between them, shown above as the cost of randomization, is the solver "
        "and nothing else.</p>"
        "<p>CPU time is accounted across the whole process tree. A simulator solves constraints in "
        "a separate solver process which it never reaps, so <b>getrusage</b> and <b>/usr/bin/time</b> "
        "attribute none of that solver's CPU time to the run. Sampling every process in the run's "
        "process group recovers it - through <b>/proc</b> on Linux and <b>libproc</b> on macOS. "
        "CPU usage above 100% means more than one core was busy.</p>"
        "<p>Randomization quality is measured separately, on an untimed run that records every "
        "value drawn. It is kept out of the timed runs so that recording cannot be measured as "
        "randomization cost.</p>"
        "<p>Reported figures are the median across runs; the spread chart shows the full range. "
        "Benchmarks, flavours and repeats are always run one at a time. A flavour may run a "
        "different number of randomizations where its cost is out of proportion to the rest - "
        "everything compared here is a time <b>per</b> randomization, so the counts need not "
        "match.</p>"
        "</div>",
    ))

    return (TEMPLATE
            .replace("__TITLE__", esc(title))
            .replace("__LOGO__", logo)
            .replace("__BODY__", "".join(body)))
