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
import bench_quality  # noqa: E402

try:
    from tabulate import tabulate
except ImportError:  # pragma: no cover - tabulate ships with avl
    tabulate = None

METRICS = ["real_s", "user_s", "sys_s", "cpu_pct", "max_rss_kb"]

RAW_HEADERS = ["benchmark", "flavour", "sim", "phase", "iters", "runs", "real (s)", "user (s)",
               "sys (s)", "cpu (%)", "rss (MB)", "failed"]

# What a benchmark measures, in the words its report is written in. Each
# testbench records which of these it is timing, as the "unit" column of
# results.csv - see bench_time.py - so an aggregate report over a mixed set of
# benchmarks can fall back to the neutral wording rather than claim they all
# measure the same thing.
#
# singular / plural / short  the unit itself, "short" for a narrow column heading
# cost                       what the measurement is the cost of
# isolates                   what is left once the harness has been subtracted
# differs                    what changes from one flavour to the next
PROFILES = {
    "randomization": {
        "singular": "randomization",
        "plural": "randomizations",
        "short": "rand",
        "cost": "cost of randomization",
        "isolates": "the solver",
        "differs":
            "Every flavour of a benchmark compiles the <b>same RTL</b> and runs the <b>same "
            "harness</b>, which drives clock and reset and randomizes once per rising edge. The "
            "only difference is where the randomization happens: the <b>sv</b> flavour randomizes "
            "inside the RTL with SystemVerilog classes and constraints solved by the simulator, "
            "the <b>avl</b> flavour randomizes the identical object from Python with AVL, and the "
            "<b>pyuvm</b> flavour randomizes it again as a pyvsc randobj, from the run_phase of a "
            "pyuvm test. Everything else - the simulator, the elaboration, the clock, the loop - "
            "is common.",
    },
    "item": {
        "singular": "item",
        "plural": "items",
        "short": "item",
        "cost": "cost of building and sending an item",
        "isolates": "item creation and signal driving",
        "differs":
            "Every flavour of a benchmark compiles the <b>same RTL</b> and runs the <b>same "
            "harness</b>, which drives clock and reset and builds and sends one item per rising "
            "edge. Nothing is randomized. The only difference is who builds and sends it: the "
            "<b>sv</b> flavour builds a SystemVerilog object inside the RTL and assigns its "
            "fields to the signals directly, the <b>avl</b> flavour builds an AVL sequence item "
            "in the cocotb testbench and writes the same signals through the simulator's "
            "programming interface, and the <b>pyuvm</b> flavour builds a uvm_sequence_item and "
            "writes them the same way, from the run_phase of a pyuvm test. Everything else - the "
            "simulator, the elaboration, the clock, the loop - is common.",
    },
    "transaction": {
        "singular": "transaction",
        "plural": "transactions",
        "short": "txn",
        "cost": "cost of a transaction",
        "isolates": "solving the item and driving it",
        "differs":
            "Every flavour of a benchmark compiles the <b>same RTL</b> and runs the <b>same "
            "harness</b>, which drives clock and reset and builds, randomizes and sends one item "
            "per rising edge. The only difference is who does that: the <b>sv</b> flavour builds a "
            "SystemVerilog object inside the RTL, has the simulator solve its constraints and "
            "assigns the result to the signals directly, the <b>avl</b> flavour builds and solves "
            "the identical object in the cocotb testbench with AVL and writes the same signals "
            "through the simulator's programming interface, and the <b>pyuvm</b> flavour does it "
            "again as a pyvsc randobj, from the run_phase of a pyuvm test. Everything else - the "
            "simulator, the elaboration, the clock, the loop - is common. This is both halves of "
            "the tree in one figure, and the solve is the larger part of it by some way.",
    },
}

# Benchmarks that measure different things, reported together.
MIXED = {
    "singular": "operation",
    "plural": "operations",
    "short": "op",
    "cost": "cost of the work under test",
    "isolates": "the work under test",
    "differs":
        "Every flavour of a benchmark compiles the <b>same RTL</b> and runs the <b>same "
        "harness</b>, which drives clock and reset and performs one operation per rising edge. "
        "The only difference is which implementation performs it - <b>sv</b> inside the RTL, "
        "<b>avl</b> from the cocotb testbench, <b>pyuvm</b> from the run_phase of a pyuvm test. "
        "Everything else - the simulator, the elaboration, the clock, the loop - is common. The "
        "benchmarks below do not all measure the same operation, so each is comparable across "
        "flavours rather than against another benchmark.",
}


def profile_of(rows: list[dict]) -> dict:
    """The wording for what these rows measured.

    A single unit is described in its own terms; a mixed set is described
    neutrally, because nothing here can compare one to another.
    """
    units = {row.get("unit") or "randomization" for row in rows}
    if len(units) != 1:
        return MIXED

    unit = units.pop()
    return PROFILES.get(unit, {**MIXED, "singular": unit, "plural": f"{unit}s", "short": unit})


def net_headers(profile: dict) -> list[str]:
    return ["benchmark", "flavour", "sim", "iters", "real (s)", "user (s)", "sys (s)",
            "cpu (%)", f"us/{profile['short']}", "relative", "harness (s)"]


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
    parser.add_argument("--quality", nargs="*", type=Path, default=[],
                        help="quality.csv dumps of drawn values, from the quality runs")
    parser.add_argument("--quality-check", default="none",
                        help="Flavours whose randomization quality must meet the thresholds, "
                             "or 'none' to report without failing (default: none)")
    args = parser.parse_args()

    paths = [p for p in args.csv if p.exists() and p.stat().st_size > 0]
    if not paths:
        print("No benchmark results found - run 'make bench' first.", file=sys.stderr)
        return 1

    rows = read(paths)
    summary = medians(rows)
    nets = net_metrics(summary)
    raws = raw_metrics(summary)

    # The words this report is written in - see PROFILES.
    profile = profile_of(rows)
    headers = net_headers(profile)

    # How well spread the randomization was, alongside how fast it was. Absent
    # unless the quality runs have been done.
    dumps = [p for p in args.quality if p.exists() and p.stat().st_size > 0]
    quality = bench_quality.measure(dumps) if dumps else []
    quality_by_flavour = bench_quality.by_flavour(quality) if quality else []

    print()
    print(f"{args.title} - {profile['cost']}, harness subtracted")
    print(render(headers, net_table(nets)))
    print()
    print("As measured, including simulator and interpreter startup")
    print(render(RAW_HEADERS, raw_table(raws)))
    print()

    if quality:
        print("Quality of randomization - entropy 1.00 is a flat spread, bit skew 0.00 agrees "
              "with the other flavours")
        print(render(bench_quality.HEADERS, bench_quality.table(quality)))
        print()

    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)

        with open(args.output / "summary.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(net_table(nets))

        markdown = [
            f"# {args.title}",
            "",
            f"## {profile['cost'][0].upper()}{profile['cost'][1:]}",
            "",
            "Every flavour compiles the same RTL and runs the same cocotb testbench. The harness -",
            "startup, elaboration, cocotb bringup and the loop itself - has been subtracted using a",
            "baseline run of the same testbench with the work under test disabled.",
            "",
            render(headers, net_table(nets)),
            "",
            "## As measured",
            "",
            render(RAW_HEADERS, raw_table(raws)),
            "",
        ]
        if quality:
            markdown += [
                "## Quality of randomization",
                "",
                "Measured on a separate untimed run. `entropy` 1.00 is a flat spread across every",
                "value any flavour drew for that field; `bit skew` 0.00 agrees with the other",
                "flavours on how often each bit was set. A cheaper randomization buys its speed",
                "here, where a timing measurement cannot see it.",
                "",
                render(bench_quality.HEADERS, bench_quality.table(quality)),
                "",
            ]
        (args.output / "summary.md").write_text("\n".join(markdown))

        # Named apart from the per flavour quality.csv dumps this was measured
        # from, which sit one directory up in <benchmark>/<flavour>/ - the report
        # is run over a glob of those, and would otherwise be handed its own
        # output to read back as if it were a dump of drawn values.
        if quality:
            with open(args.output / "quality_summary.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(bench_quality.HEADERS)
                writer.writerows(bench_quality.table(quality))

        (args.output / "report.html").write_text(
            bench_html.render(args.title, nets, raws, rows, quality, quality_by_flavour,
                              profile)
        )

        print(f"Wrote {args.output / 'summary.csv'}, {args.output / 'summary.md'} "
              f"and {args.output / 'report.html'}")

    checked = [f.strip() for f in args.quality_check.split(",") if f.strip()]
    if quality and checked and checked != ["none"]:
        breaches = bench_quality.failures(quality_by_flavour, checked,
                                          bench_quality.ENTROPY_TOLERANCE,
                                          bench_quality.BIT_SKEW_CEILING)
        if breaches:
            print(f"Randomization quality regressed for {args.quality_check}:", file=sys.stderr)
            for breach in breaches:
                print(f"  {breach}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
