#!/usr/bin/env python3
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark - randomization quality
#
# Reads the value dumps written by the quality run of each flavour and measures
# how well spread the randomization was, not just how fast it was. A solver can
# be made a great deal faster by giving up distribution - narrowing the values it
# explores, or leaving bits the constraints do not pin at whatever the solver
# reaches for first - and nothing in a timing measurement would notice.
#
# The metrics are deliberately constraint agnostic, because the categories differ
# in shape. Checking each bit against a half-and-half split would be wrong for a
# set membership constraint: "a inside {1, 2, 4 ... 32768}" legitimately leaves
# every bit set only one time in sixteen. So instead:
#
#   distinct  Distinct values drawn, over the number of draws. Cheap to read,
#             but says nothing about how evenly they were spread.
#
#   entropy   Shannon entropy of the values drawn, normalised so that 1.00 is a
#             flat spread across every value any flavour managed to draw for that
#             field. Scale free, so it is comparable between a field with sixteen
#             legal values and one with sixteen million.
#
#   bit skew  The furthest any one bit's proportion of ones strays from what the
#             flavours agree on for that bit. A flavour that pins a bit the
#             others spread - the usual symptom of a cheaper randomization
#             strategy - shows up here and nowhere else. Bits that no flavour
#             ever varied are ignored: the constraints fixed those.
#
# Entropy is close to absolute, because the normalisation accounts for how many
# values the constraints actually allow, so it is what the regression check is
# based on. Bit skew is reported but not failed on by default: with only three
# flavours a median is not a robust centre, and when one of them is badly spread
# the middle value stops being the consensus - the skew then lands on whichever
# well behaved flavour happens to sit further from the outlier. So its ceiling is
# set loosely, to catch a bit that has been pinned outright rather than to police
# small differences.
#
# Neither metric can see a bias that every flavour shares, which is worth
# remembering when reading them.

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

# Defaults for the regression check. A uniform draw scores 1.00 entropy and 0.00
# skew; the biases measured against real alternatives to AVL's approach - bit
# chunking, XOR hashing, a solver timeout - all came in far outside these.
# The check is relative: a flavour fails when its entropy falls this far below
# what the flavours agree on for that field. An absolute floor cannot work,
# because a field's legal values do not all carry the same number of solutions -
# implication's "mode" is a fair example, where mode 0 forces len to a single
# value and mode 3 leaves fifty five. Every flavour scores about 0.8 there and
# all of them are right. Verilator's XOR hashing, by contrast, came in 0.27 below
# its peers on arithmetic's "c".
ENTROPY_TOLERANCE = 0.10

# Absolute backstop, well below anything measured, in case every flavour
# collapses at once - which the relative check could not see.
ENTROPY_FLOOR = 0.50

# Bit skew catches what entropy cannot: a flavour whose values are all different
# but whose individual bits are pushed around. Set loosely, because the noise here
# is the difference between two independent estimates taken over every free bit -
# about 0.07 at the default 1000 draws, and 0.10 at 400. Shorten the quality run
# much below the default and this wants raising, or turning off with 1.0.
BIT_SKEW_CEILING = 0.20

HEADERS = ["benchmark", "flavour", "field", "width", "draws", "distinct", "entropy", "bit skew"]


def read_dump(path: Path) -> tuple[str, str, list[tuple[str, int]], list[tuple[int, ...]]]:
    """Parse one quality.csv, taking benchmark and flavour from its location.

    The dumps live at <group>/<benchmark>/<flavour>/quality.csv.
    """
    flavour = path.parent.name
    benchmark = f"{path.parent.parent.parent.name}/{path.parent.parent.name}"

    with open(path, newline="") as f:
        rows = list(csv.reader(f))

    if not rows:
        raise ValueError(f"{path} is empty")

    fields = []
    for cell in rows[0]:
        name, _, width = cell.partition(":")
        fields.append((name, int(width)))

    samples = [tuple(int(v) for v in row) for row in rows[1:] if row]
    return benchmark, flavour, fields, samples


def entropy(values: list[int], legal: int) -> float:
    """Normalised Shannon entropy of the drawn values.

    Normalised by the most a flat spread could have achieved given the number of
    draws and the number of distinct values anyone drew, so a field with few
    legal values is not penalised for having few.
    """
    if not values:
        return 0.0

    ceiling = math.log2(min(len(values), max(legal, 1)))
    if ceiling <= 0:
        return 1.0  # one legal value - nothing to spread

    counts = Counter(values)
    total = len(values)
    h = -sum((c / total) * math.log2(c / total) for c in counts.values())
    return min(h / ceiling, 1.0)


def bit_proportions(values: list[int], width: int) -> list[float]:
    """Proportion of draws in which each bit was set."""
    total = len(values)
    return [sum((v >> b) & 1 for v in values) / total for b in range(width)]


def measure(dumps: list[Path]) -> list[dict]:
    """One row per benchmark, flavour and field."""
    parsed = [read_dump(p) for p in dumps]

    # Group by benchmark and field, so a flavour can be compared with the others
    # that ran the same item.
    pooled: dict[tuple[str, str], dict] = {}
    for benchmark, flavour, fields, samples in parsed:
        for index, (name, width) in enumerate(fields):
            values = [s[index] for s in samples if index < len(s)]
            entry = pooled.setdefault((benchmark, name),
                                      {"width": width, "by_flavour": {}, "all": []})
            entry["by_flavour"][flavour] = values
            entry["all"].extend(values)

    rows = []
    for (benchmark, name), entry in sorted(pooled.items()):
        width = entry["width"]
        legal = len(set(entry["all"]))

        proportions = {flavour: bit_proportions(values, width)
                       for flavour, values in entry["by_flavour"].items() if values}
        if not proportions:
            continue

        # The median across flavours, not the mean of everything pooled: one
        # badly spread flavour would drag a pooled baseline far enough to make
        # the well behaved ones look like the outliers.
        consensus = [statistics.median(p[b] for p in proportions.values()) for b in range(width)]

        # Bits no flavour ever varied are pinned by the constraints, not by a
        # weak randomization, so they are not evidence either way.
        free = [b for b in range(width)
                if any(0.0 < p[b] < 1.0 for p in proportions.values())]

        # What the flavours agree the spread of this field looks like.
        entropies = {flavour: entropy(values, legal)
                     for flavour, values in entry["by_flavour"].items() if values}
        reference = statistics.median(entropies.values())

        for flavour, values in sorted(entry["by_flavour"].items()):
            if not values:
                continue
            skew = max((abs(proportions[flavour][b] - consensus[b]) for b in free), default=0.0)
            rows.append({
                "benchmark": benchmark,
                "flavour": flavour,
                "field": name,
                "width": width,
                "draws": len(values),
                "distinct": len(set(values)) / len(values),
                "entropy": entropies[flavour],
                "entropy_deficit": max(reference - entropies[flavour], 0.0),
                "bit_skew": skew,
                "free_bits": len(free),
                "flavours": len(proportions),
            })
    return rows


def by_flavour(rows: list[dict]) -> list[dict]:
    """Worst field per benchmark and flavour - what the report charts."""
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["benchmark"], row["flavour"]), []).append(row)

    summary = []
    for (benchmark, flavour), group in sorted(grouped.items()):
        summary.append({
            "benchmark": benchmark,
            "flavour": flavour,
            "fields": len(group),
            "draws": min(r["draws"] for r in group),
            "entropy": min(r["entropy"] for r in group),
            "entropy_deficit": max(r["entropy_deficit"] for r in group),
            "bit_skew": max(r["bit_skew"] for r in group),
            "distinct": min(r["distinct"] for r in group),
        })
    return summary


def table(rows: list[dict]) -> list[list]:
    return [[r["benchmark"], r["flavour"], r["field"], r["width"], f"{r['draws']:,}",
             f"{r['distinct']:.3f}", f"{r['entropy']:.3f}", f"{r['bit_skew']:.3f}"]
            for r in rows]


def failures(summary: list[dict], flavours: list[str], tolerance: float,
             skew_ceiling: float) -> list[str]:
    """Threshold breaches, for the flavours being held to them."""
    out = []
    for row in summary:
        if flavours != ["all"] and row["flavour"] not in flavours:
            continue
        if row["entropy_deficit"] > tolerance:
            out.append(f"{row['benchmark']} [{row['flavour']}] entropy {row['entropy']:.3f}, "
                       f"{row['entropy_deficit']:.3f} below the other flavours "
                       f"(tolerance {tolerance:.2f})")
        elif row["entropy"] < ENTROPY_FLOOR:
            out.append(f"{row['benchmark']} [{row['flavour']}] entropy {row['entropy']:.3f} "
                       f"below the absolute floor of {ENTROPY_FLOOR:.2f}")
        if row["bit_skew"] > skew_ceiling:
            out.append(f"{row['benchmark']} [{row['flavour']}] bit skew {row['bit_skew']:.3f} "
                       f"above {skew_ceiling:.2f}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure how well spread each flavour's randomization was.")
    parser.add_argument("dumps", nargs="*", type=Path, help="quality.csv files to analyse")
    parser.add_argument("--output", type=Path, default=None, help="Directory to write quality.csv")
    parser.add_argument("--check", default="avl",
                        help="Comma separated flavours held to the thresholds, or 'all', "
                             "or 'none' to measure without failing (default: avl)")
    parser.add_argument("--entropy-tolerance", type=float, default=ENTROPY_TOLERANCE,
                        help="How far below the other flavours a flavour's entropy may fall")
    parser.add_argument("--bit-skew-ceiling", type=float, default=BIT_SKEW_CEILING)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    dumps = [p for p in args.dumps if p.exists() and p.stat().st_size > 0]
    if not dumps:
        print("No randomization dumps found - run 'make quality' first.", file=sys.stderr)
        return 1

    rows = measure(dumps)
    summary = by_flavour(rows)

    if not args.quiet:
        try:
            from tabulate import tabulate
            rendered = tabulate(table(rows), headers=HEADERS, tablefmt="github")
        except ImportError:  # pragma: no cover - tabulate ships with avl
            rendered = "\n".join("  ".join(str(c) for c in row) for row in table(rows))
        print()
        print("Quality of randomization - entropy 1.00 is a flat spread, bit skew 0.00 agrees "
              "with the other flavours")
        print(rendered)
        print()

    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
        with open(args.output / "quality.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS)
            writer.writerows(table(rows))

    checked = [f.strip() for f in args.check.split(",") if f.strip()]
    if checked == ["none"]:
        return 0

    breaches = failures(summary, checked, args.entropy_tolerance, args.bit_skew_ceiling)
    if breaches:
        print(f"Randomization quality regressed for {args.check}:", file=sys.stderr)
        for breach in breaches:
            print(f"  {breach}", file=sys.stderr)
        return 1

    if not args.quiet:
        gate = f"entropy within {args.entropy_tolerance:.2f} of the other flavours"
        if args.bit_skew_ceiling < 1.0:
            gate += f", bit skew <= {args.bit_skew_ceiling:.2f}"
        print(f"Randomization quality OK for {args.check} ({gate})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
