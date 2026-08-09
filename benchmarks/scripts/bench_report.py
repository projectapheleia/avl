#!/usr/bin/env python3
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark Report Generator
#
# Aggregates the CSV files written by bench_time.py into a summary table, and
# writes it out as CSV, markdown and a self contained HTML page.
#
# Each testbench is measured twice - once driving the requested number of clock
# cycles with randomization enabled ("run") and once driving exactly the same
# number with it disabled ("baseline"). The baseline captures everything that is
# not randomization: process startup, elaboration of the model, the Python
# interpreter, cocotb bringup and the cost of the loop itself. Subtracting it
# leaves the cost of the randomization, which is the number the flavours can be
# compared on directly.


from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_html  # noqa: E402

try:
    from tabulate import tabulate
except ImportError:  # pragma: no cover - tabulate ships with avl
    tabulate = None

METRICS = ["real_s", "user_s", "sys_s", "cpu_pct", "max_rss_kb"]

NET_HEADERS = ["benchmark", "flavour", "sim", "iters", "real (s)", "user (s)", "sys (s)",
               "cpu (%)", "us/rand", "relative", "harness (s)"]

RAW_HEADERS = ["benchmark", "flavour", "sim", "phase", "iters", "runs", "real (s)", "user (s)",
               "sys (s)", "cpu (%)", "rss (MB)", "failed"]


def read(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                for key in METRICS:
                    row[key] = float(row[key])
                row["iterations"] = int(row["iterations"])
                rows.append(row)
    return rows


def medians(rows: list[dict]) -> dict[tuple, dict]:
    """Median of every metric, grouped by benchmark / flavour / tool / phase."""
    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (row["benchmark"], row["flavour"], row["tool"], row["phase"])
        grouped.setdefault(key, []).append(row)

    summary = {}
    for key, group in grouped.items():
        ok = [r for r in group if r["status"] == "ok"]
        if ok:
            values = {m: statistics.median([r[m] for r in ok]) for m in METRICS}
        else:
            values = dict.fromkeys(METRICS, 0.0)

        summary[key] = {
            **values,
            "iterations": group[0]["iterations"],
            "repeats": len(group),
            "failed": len(group) - len(ok),
        }
    return summary


def raw_metrics(summary: dict[tuple, dict]) -> list[dict]:
    return [
        {"benchmark": benchmark, "flavour": flavour, "tool": tool, "phase": phase, **value}
        for (benchmark, flavour, tool, phase), value in sorted(summary.items())
    ]


def net_metrics(summary: dict[tuple, dict]) -> list[dict]:
    """Randomization cost, with the harness subtracted."""
    nets = []
    for (benchmark, flavour, tool, phase), value in sorted(summary.items()):
        if phase != "run":
            continue

        base = summary.get((benchmark, flavour, tool, "baseline"))
        iterations = value["iterations"]

        net = {"benchmark": benchmark, "flavour": flavour, "tool": tool, "iterations": iterations}
        for metric in ["real_s", "user_s", "sys_s"]:
            net[metric] = max(value[metric] - (base[metric] if base else 0.0), 0.0)

        total = net["user_s"] + net["sys_s"]
        net["cpu_pct"] = 100.0 * total / net["real_s"] if net["real_s"] else 0.0
        net["per_iter_us"] = 1e6 * net["real_s"] / iterations if iterations else 0.0
        net["overhead_s"] = base["real_s"] if base else 0.0
        nets.append(net)

    # Cost relative to the fastest flavour of the same benchmark.
    for benchmark in {n["benchmark"] for n in nets}:
        entries = [n for n in nets if n["benchmark"] == benchmark]
        best = min((n["per_iter_us"] for n in entries if n["per_iter_us"] > 0), default=0.0)
        for n in entries:
            n["relative"] = (n["per_iter_us"] / best) if best else 0.0

    return nets


def net_table(nets: list[dict]) -> list[list]:
    return [[
        n["benchmark"], n["flavour"], n["tool"], n["iterations"],
        f"{n['real_s']:.3f}", f"{n['user_s']:.3f}", f"{n['sys_s']:.3f}",
        f"{n['cpu_pct']:.1f}", f"{n['per_iter_us']:.1f}",
        f"{n['relative']:.2f}x" if n["relative"] else "-",
        f"{n['overhead_s']:.3f}",
    ] for n in nets]


def raw_table(raws: list[dict]) -> list[list]:
    return [[
        r["benchmark"], r["flavour"], r["tool"], r["phase"], r["iterations"], r["repeats"],
        f"{r['real_s']:.3f}", f"{r['user_s']:.3f}", f"{r['sys_s']:.3f}",
        f"{r['cpu_pct']:.1f}", f"{r['max_rss_kb'] / 1024:.1f}", r["failed"] or "",
    ] for r in raws]


def render(headers: list[str], table: list[list], fmt: str = "github") -> str:
    if tabulate is not None:
        return tabulate(table, headers=headers, tablefmt=fmt)

    widths = [max(len(str(h)), *(len(str(r[i])) for r in table)) if table else len(str(h))
              for i, h in enumerate(headers)]
    lines = ["  ".join(str(h).ljust(w) for h, w in zip(headers, widths, strict=True)),
             "  ".join("-" * w for w in widths)]
    lines += ["  ".join(str(c).ljust(w) for c, w in zip(row, widths, strict=True)) for row in table]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarise AVL benchmark results.")
    parser.add_argument("csv", nargs="*", type=Path, help="results.csv files to aggregate")
    parser.add_argument("--output", type=Path, default=None, help="Directory to write reports to")
    parser.add_argument("--title", default="AVL Benchmark Results", help="Report title")
    args = parser.parse_args()

    paths = [p for p in args.csv if p.exists() and p.stat().st_size > 0]
    if not paths:
        print("No benchmark results found - run 'make bench' first.", file=sys.stderr)
        return 1

    rows = read(paths)
    summary = medians(rows)
    nets = net_metrics(summary)
    raws = raw_metrics(summary)

    print()
    print(f"{args.title} - cost of randomization, harness subtracted")
    print(render(NET_HEADERS, net_table(nets)))
    print()
    print("As measured, including simulator and interpreter startup")
    print(render(RAW_HEADERS, raw_table(raws)))
    print()

    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)

        with open(args.output / "summary.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(NET_HEADERS)
            writer.writerows(net_table(nets))

        markdown = [
            f"# {args.title}",
            "",
            "## Cost of randomization",
            "",
            "Both flavours compile the same RTL and run the same cocotb testbench. The harness -",
            "startup, elaboration, cocotb bringup and the loop itself - has been subtracted using a",
            "baseline run of the same testbench with randomization disabled.",
            "",
            render(NET_HEADERS, net_table(nets)),
            "",
            "## As measured",
            "",
            render(RAW_HEADERS, raw_table(raws)),
            "",
        ]
        (args.output / "summary.md").write_text("\n".join(markdown))

        (args.output / "report.html").write_text(
            bench_html.render(args.title, nets, raws, rows)
        )

        print(f"Wrote {args.output / 'summary.csv'}, {args.output / 'summary.md'} "
              f"and {args.output / 'report.html'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
