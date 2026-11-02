# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library Value Change Dump (VCD) reader

from __future__ import annotations

import heapq
import re
from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

# A signal's value as this reader reports it:
#   int    for a scalar or vector made only of 0s and 1s
#   str    for a scalar or vector carrying x or z, as a binary string, msb first
#   float  for a real
#   str    for a string variable, verbatim
VcdValue = int | str | float

# Time units a VCD may declare, mapped to the names cocotb uses
_UNITS = {"s": "sec", "ms": "ms", "us": "us", "ns": "ns", "ps": "ps", "fs": "fs"}

# Each unit in femtoseconds, for conversions between units
_UNIT_FS = {"sec": 10**15, "ms": 10**12, "us": 10**9, "ns": 10**6, "ps": 10**3, "fs": 1}

# A declared name followed by a range: "a [7:0]", "a[7:0]", "a [3]" or "a[3]"
_RANGE_RE = re.compile(r"^(.*?)\s*\[\s*(\d+(?:\s*:\s*\d+)?)\s*\]$")


@dataclass
class VcdSignal:
    """
    One variable declared in the VCD.

    Several declarations may share one identifier code - the file then records
    the value once and every alias reads the same list of changes.
    """

    name: str
    """Full hierarchical name, scopes joined with a dot, e.g. ``tb.dut.a``."""

    code: str
    """Identifier code used in the value change section."""

    width: int
    """Width in bits (1 for a scalar)."""

    var_type: str
    """Variable type as declared: ``wire``, ``reg``, ``logic``, ``real``, ``string`` ..."""

    times: list[int] = field(default_factory=list, repr=False)
    """Times of each change, in timescale units, ascending."""

    values: list[VcdValue] = field(default_factory=list, repr=False)
    """Value after each change, aligned with :attr:`times`."""

    @property
    def changes(self) -> list[tuple[int, VcdValue]]:
        """
        Every change of the signal, oldest first.

        :return: List of (time, value) pairs.
        :rtype: list[tuple[int, VcdValue]]
        """
        return list(zip(self.times, self.values, strict=True))

    def value_at(self, time: int, inclusive: bool = True) -> VcdValue | None:
        """
        Value of the signal at a time.

        :param time: Time in timescale units.
        :type time: int
        :param inclusive: If True a change recorded at exactly ``time`` has already happened; if False
                          the value is the one immediately before ``time``, which is the value a flop
                          clocked at ``time`` sampled.
        :type inclusive: bool
        :return: The value, or None if nothing had been recorded for the signal by then.
        :rtype: VcdValue | None
        """
        idx = bisect_right(self.times, time) if inclusive else bisect_left(self.times, time)
        if idx == 0:
            return None
        return self.values[idx - 1]

    def edges(self, rising: bool = True) -> list[int]:
        """
        Times at which a scalar signal has an edge.

        An edge is a change to 1 from anything that was not 1 (rising), or to 0 from anything that was not
        0 (falling), as Verilog defines posedge and negedge. The first value recorded for the signal is its
        initial state and is not an edge.

        :param rising: True for rising edges, False for falling.
        :type rising: bool
        :return: Times in timescale units, ascending.
        :rtype: list[int]
        """
        target = 1 if rising else 0
        result = []
        prev: VcdValue | None = None
        for t, v in zip(self.times, self.values, strict=True):
            if prev is not None and v == target and prev != target:
                result.append(t)
            prev = v
        return result


class Vcd:
    """
    A Value Change Dump read into memory.

    .. code-block:: python

        vcd = avl.Vcd("capture.vcd")
        a = vcd.lookup("tb.dut.a")              # or just "a" if that is unambiguous
        a.value_at(1250)                        # value at 1250 timescale units
        vcd.lookup("tb.clk").edges()            # every rising edge of the clock
    """

    def __init__(self, filename: str) -> None:
        """
        Read a VCD file.

        :param filename: Path to the file.
        :type filename: str
        :raises ValueError: If the file is not a VCD this reader understands.
        """
        self.filename = filename
        self.timescale: tuple[int, str] = (1, "ns")
        """Declared timescale as (magnitude, unit), the unit named as cocotb names it."""
        self.date = ""
        self.version = ""
        self.signals: dict[str, VcdSignal] = {}
        """Every declared variable, by full hierarchical name."""
        self.end_time = 0
        """Time of the last change, in timescale units."""
        self._by_code: dict[str, VcdSignal] = {}

        with open(filename) as f:
            self._parse(f.read())

    @staticmethod
    def _skip_to_end(tokens: list[str], i: int) -> int:
        """
        Index of the token after the next ``$end``.
        """
        n = len(tokens)
        while i < n and tokens[i] != "$end":
            i += 1
        return i + 1

    @staticmethod
    def _collect_to_end(tokens: list[str], i: int) -> tuple[str, int]:
        """
        The tokens up to the next ``$end`` joined with spaces, and the index after it.
        """
        n = len(tokens)
        j = i
        while j < n and tokens[j] != "$end":
            j += 1
        return " ".join(tokens[i:j]), j + 1

    def _parse_timescale(self, text: str) -> None:
        """
        Parse a timescale declaration such as ``1ns`` or ``10 ps``.
        """
        text = text.replace(" ", "")
        digits = "".join(c for c in text if c.isdigit())
        unit = text[len(digits):]
        if not digits or unit not in _UNITS:
            raise ValueError(f"{self.filename}: unsupported $timescale '{text}'")
        self.timescale = (int(digits), _UNITS[unit])

    @staticmethod
    def _var_name(declared: str) -> str:
        """
        The name a declaration gives a variable, with any range it carries resolved.

        ``a [7:0]`` describes the whole vector ``a`` and the range is dropped. ``a [3]`` is one bit, or one
        element, of ``a`` - some simulators dump a bus bit by bit - and is kept as ``a[3]`` so that the bits
        stay distinct.
        """
        m = _RANGE_RE.match(declared)
        if m is None:
            return declared.strip()
        name, index = m.group(1).strip(), m.group(2)
        if ":" in index:
            return name
        return f"{name}[{index}]"

    @staticmethod
    def _vector(bits: str, width: int) -> VcdValue:
        """
        Normalise a vector value to the declared width and to int where it is fully known.

        A value shorter than its width is extended on the left with 0 if its msb is 0 or 1, and with x or z
        if its msb is x or z, as the standard says.
        """
        bits = bits.lower()
        if len(bits) < width:
            fill = bits[0] if bits[0] in "xz" else "0"
            bits = fill * (width - len(bits)) + bits
        elif len(bits) > width:
            bits = bits[-width:]
        if "x" in bits or "z" in bits:
            return bits
        return int(bits, 2)

    def _parse(self, text: str) -> None:
        """
        Parse the whole file.
        """
        tokens = text.split()
        n = len(tokens)
        i = 0
        scope: list[str] = []
        time = 0

        # Header
        while i < n:
            tok = tokens[i]
            if tok == "$enddefinitions":
                i = self._skip_to_end(tokens, i + 1)
                break
            elif tok == "$scope":
                # $scope <type> <name> $end
                scope.append(tokens[i + 2])
                i = self._skip_to_end(tokens, i + 3)
            elif tok == "$upscope":
                if scope:
                    scope.pop()
                i = self._skip_to_end(tokens, i + 1)
            elif tok == "$var":
                # $var <type> <width> <code> <name> [<range>] $end
                var_type = tokens[i + 1]
                width = int(tokens[i + 2])
                code = tokens[i + 3]
                rest, i = self._collect_to_end(tokens, i + 4)
                full = ".".join([*scope, self._var_name(rest)])
                sig = self._by_code.get(code)
                if sig is None:
                    sig = VcdSignal(full, code, width, var_type)
                    self._by_code[code] = sig
                else:
                    # Alias: a second name for the same recorded value
                    sig = VcdSignal(full, code, width, var_type, sig.times, sig.values)
                self.signals[full] = sig
            elif tok == "$timescale":
                value, i = self._collect_to_end(tokens, i + 1)
                self._parse_timescale(value)
            elif tok == "$date":
                self.date, i = self._collect_to_end(tokens, i + 1)
            elif tok == "$version":
                self.version, i = self._collect_to_end(tokens, i + 1)
            elif tok.startswith("$"):
                # $comment, $attrbegin and anything else we do not need
                i = self._skip_to_end(tokens, i + 1)
            else:
                raise ValueError(f"{self.filename}: unexpected token '{tok}' in VCD header")

        if not self.signals:
            raise ValueError(f"{self.filename}: no variables declared - is this a VCD file?")

        # Value changes
        while i < n:
            tok = tokens[i]
            c = tok[0]
            if c == "#":
                time = int(tok[1:])
                if time > self.end_time:
                    self.end_time = time
                i += 1
            elif c in "01xXzZ":
                sig = self._by_code.get(tok[1:])
                if sig is not None:
                    sig.times.append(time)
                    sig.values.append(int(c) if c in "01" else c.lower())
                i += 1
            elif c in "bB":
                sig = self._by_code.get(tokens[i + 1])
                if sig is not None:
                    sig.times.append(time)
                    sig.values.append(self._vector(tok[1:], sig.width))
                i += 2
            elif c in "rR":
                sig = self._by_code.get(tokens[i + 1])
                if sig is not None:
                    sig.times.append(time)
                    sig.values.append(float(tok[1:]))
                i += 2
            elif c in "sS":
                sig = self._by_code.get(tokens[i + 1])
                if sig is not None:
                    sig.times.append(time)
                    sig.values.append(tok[1:])
                i += 2
            elif tok == "$comment":
                i = self._skip_to_end(tokens, i + 1)
            elif c == "$":
                # $dumpvars, $dumpall, $dumpon, $dumpoff and their $end
                i += 1
            else:
                raise ValueError(f"{self.filename}: unexpected token '{tok}' at time {time}")

        # A well formed file is already in time order; make sure of it so that
        # the bisections above are sound.
        for sig in self._by_code.values():
            if any(a > b for a, b in zip(sig.times, sig.times[1:], strict=False)):
                order = sorted(range(len(sig.times)), key=lambda k: sig.times[k])
                sig.times[:] = [sig.times[k] for k in order]
                sig.values[:] = [sig.values[k] for k in order]

    def lookup(self, name: str) -> VcdSignal:
        """
        Find a signal by name.

        The full hierarchical name is tried first. Failing that, a name is accepted if exactly one signal
        ends with it (``dut.a`` or ``a`` for ``tb.dut.a``), so a testbench need not spell out the whole
        path of the capture.

        :param name: Full or trailing hierarchical name.
        :type name: str
        :return: The signal.
        :rtype: VcdSignal
        :raises KeyError: If no signal, or more than one, matches.
        """
        if name in self.signals:
            return self.signals[name]

        suffix = "." + name
        matches = [s for n, s in self.signals.items() if n.endswith(suffix)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise KeyError(f"{self.filename}: '{name}' is ambiguous, matches {', '.join(s.name for s in matches)}")
        raise KeyError(f"{self.filename}: no signal '{name}', the file declares {', '.join(sorted(self.signals))}")

    def scope(self, name: str) -> list[VcdSignal]:
        """
        The signals declared directly in a scope, in declaration order.

        :param name: Full hierarchical name of the scope, e.g. ``tb.dut``.
        :type name: str
        :return: The signals whose name is ``<name>.<leaf>``; signals of nested scopes are not included.
        :rtype: list[VcdSignal]
        :raises KeyError: If nothing is declared in the scope.
        """
        prefix = name + "."
        found = [s for n, s in self.signals.items() if n.startswith(prefix) and "." not in n[len(prefix):]]
        if not found:
            scopes = sorted({n.rsplit(".", 1)[0] for n in self.signals if "." in n})
            raise KeyError(f"{self.filename}: no scope '{name}', the file declares {', '.join(scopes) or 'no scopes'}")
        return found

    def timeline(self, signals: Iterable[VcdSignal], start: int | None = None, end: int | None = None) -> Iterator[tuple[int, list[tuple[VcdSignal, VcdValue]]]]:
        """
        The changes of a set of signals merged into one time ordered sequence.

        :param signals: Signals to include.
        :type signals: Iterable[VcdSignal]
        :param start: Only changes strictly after this time (timescale units); None for all.
        :type start: int | None
        :param end: Only changes at or before this time; None for all.
        :type end: int | None
        :return: Iterator of (time, [(signal, value), ...]), one entry per time at which anything changed.
        :rtype: Iterator[tuple[int, list[tuple[VcdSignal, VcdValue]]]]
        """
        def stream(sig: VcdSignal) -> Iterator[tuple[int, VcdSignal, VcdValue]]:
            lo = 0 if start is None else bisect_right(sig.times, start)
            hi = len(sig.times) if end is None else bisect_right(sig.times, end)
            for k in range(lo, hi):
                yield sig.times[k], sig, sig.values[k]

        streams = [stream(sig) for sig in signals]

        current_time: int | None = None
        batch: list[tuple[VcdSignal, VcdValue]] = []
        for t, sig, v in heapq.merge(*streams, key=lambda e: e[0]):
            if t != current_time:
                if batch:
                    assert current_time is not None
                    yield current_time, batch
                current_time = t
                batch = []
            batch.append((sig, v))
        if batch:
            assert current_time is not None
            yield current_time, batch

    def to_units(self, time: float, unit: str) -> int:
        """
        Convert a time in a cocotb unit into this file's timescale units.

        :param time: Time value.
        :type time: float
        :param unit: One of ``fs``, ``ps``, ``ns``, ``us``, ``ms``, ``sec``.
        :type unit: str
        :return: Time in timescale units, rounded to the nearest.
        :rtype: int
        """
        mag, ts_unit = self.timescale
        return round(time * _UNIT_FS[unit] / (mag * _UNIT_FS[ts_unit]))

    def __repr__(self) -> str:
        mag, unit = self.timescale
        return f"Vcd({self.filename!r}, {len(self.signals)} signals, timescale {mag}{unit}, end {self.end_time})"

__all__ = ["Vcd", "VcdSignal", "VcdValue"]
