# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library VCD Driver

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import cocotb
from cocotb.handle import LogicObject
from cocotb.simtime import convert, get_sim_time
from cocotb.triggers import Combine, Event, FallingEdge, RisingEdge, Timer

from .component import Component
from .driver import Driver
from .factory import Factory
from .vcd import Vcd, VcdSignal, VcdValue


class VcdClockGroup:
    """
    A set of VCD signals driven on the edges of a testbench clock.

    Created by :meth:`VcdDriver.add_clock`, never directly.
    """

    def __init__(self, driver: VcdDriver, clock: VcdSignal, hdl_clock: Any, rising: bool = True) -> None:
        """
        Initialize the VCD clock group.

        :param driver: The owning driver.
        :type driver: VcdDriver
        :param clock: The clock in the VCD whose edges define the cycles of the capture.
        :type clock: VcdSignal
        :param hdl_clock: The HDL clock whose edges pace the replay.
        :type hdl_clock: cocotb handle
        :param rising: Use rising edges if True, falling if False, of both clocks.
        :type rising: bool
        """
        self.driver = driver
        self.clock = clock
        self.hdl_clock = hdl_clock
        self.rising = rising
        self.signals: list[tuple[VcdSignal, Any]] = []

    def add_signal(self, name: str, hdl: Any) -> VcdSignal:
        """
        Bind a VCD signal to an HDL signal, driven on this group's clock.

        :param name: Name of the signal in the VCD - full hierarchical, or any unambiguous trailing part.
        :type name: str
        :param hdl: The HDL signal to drive.
        :type hdl: cocotb handle
        :return: The VCD signal bound.
        :rtype: VcdSignal
        """
        sig = self.driver._bind_(name, hdl)
        self.signals.append((sig, hdl))
        return sig

    def add_scope(self, scope: str, hdl: Any, exclude: Iterable[str] = ()) -> list[VcdSignal]:
        """
        Bind every signal declared directly in a VCD scope to the signal of the same name under an HDL handle,
        driven on this group's clock.

        A capture of a running design records its outputs alongside its inputs; name them in ``exclude`` and
        they are left to the DUT. The group's own clock is always left out, under whatever name the scope declares
        it, as is anything ``hdl`` does not have.

        :param scope: Full hierarchical name of the scope in the VCD, e.g. ``tb.dut``.
        :type scope: str
        :param hdl: The HDL hierarchy holding the signals to drive.
        :type hdl: cocotb handle
        :param exclude: Names of signals not to drive, by leaf or full VCD name.
        :type exclude: Iterable[str]
        :return: The VCD signals bound.
        :rtype: list[VcdSignal]
        """
        return [self.add_signal(sig.name, h) for sig, h in self.driver._scope_(scope, hdl, exclude, skip=(self.clock,))]

    def frames(self) -> list[tuple[int, list[VcdValue | None]]]:
        """
        The cycles of the capture.

        One entry per edge of the VCD clock within the driver's window, holding the edge time and the
        value of each signal (in the order added) as sampled at that edge - the value immediately before
        it, which is what a flop clocked by that edge saw. None where the file had not yet recorded a value.

        :return: List of (edge time, sampled values).
        :rtype: list[tuple[int, list[VcdValue | None]]]
        """
        start, end = self.driver._window_
        edges = self.clock.edges(self.rising)
        if start is not None:
            edges = [t for t in edges if t >= start]
        if end is not None:
            edges = [t for t in edges if t <= end]
        return [(t, [sig.value_at(t, inclusive=False) for sig, _ in self.signals]) for t in edges]

    async def play(self) -> None:
        """
        Replay the group onto the DUT.

        The first cycle's values are driven immediately, so they are present at the first edge of the
        testbench clock; each later cycle's values are driven after the edge before it. After the last
        cycle one more edge is awaited, so the final values are sampled before the driver reports done.
        """
        frames = self.frames()
        if not frames:
            self.driver.warning(f"{self.clock.name} has no {'rising' if self.rising else 'falling'} edges in the window - nothing driven")
            return

        trigger = RisingEdge(self.hdl_clock) if self.rising else FallingEdge(self.hdl_clock)
        previous: list[VcdValue | None] = [None] * len(self.signals)

        for i, (_, values) in enumerate(frames):
            if i:
                await trigger
            for k, ((_, hdl), v) in enumerate(zip(self.signals, values, strict=True)):
                if v is None or v == previous[k]:
                    continue
                VcdDriver._drive_(hdl, v)
                previous[k] = v

        await trigger
        self.driver.info(f"{self.clock.name}: {len(frames)} cycles replayed")


class VcdDriver(Driver):
    """
    Replay a VCD file onto the DUT.

    The file is named by the factory variable ``<full name>.vcd_file`` or passed to :meth:`load`. Signals
    are bound in whichever phase has the HDL handles, typically ``connect_phase``:

    .. code-block:: python

        # Timed: everything, clock included, at the time the file says
        self.drv.add_signal("tb.clk", self.hdl.clk)
        self.drv.add_signal("tb.a", self.hdl.a)

        # Clocked: the testbench drives hdl.clk; a and b follow it cycle for cycle
        grp = self.drv.add_clock("tb.clk", self.hdl.clk)
        grp.add_signal("tb.a", self.hdl.a)

    The driver holds an objection to the run phase while it has anything left to drive, so a test with
    no sequence runs for as long as the capture does, and sets :attr:`done` when it finishes.
    """

    def __init__(self, name: str, parent: Component) -> None:
        """
        Initialize the VCD driver.

        :param name: Name of the driver.
        :type name: str
        :param parent: Parent component.
        :type parent: Component
        """
        super().__init__(name, parent)

        # Path of the VCD to replay
        self.vcd_file: str | None = Factory.get_variable(f"{self.get_full_name()}.vcd_file", None)

        # Hold an objection to the run phase while replaying
        self.objection: bool = Factory.get_variable(f"{self.get_full_name()}.objection", True)

        # Notify waiting tasks when all playback has completed
        self.done = Event()

        self._vcd_: Vcd | None = None
        self._timed_: list[tuple[VcdSignal, Any]] = []
        self._groups_: list[VcdClockGroup] = []
        self._window_: tuple[int | None, int | None] = (None, None)

    @property
    def vcd(self) -> Vcd:
        """
        The loaded VCD, read from :attr:`vcd_file` on first use.

        :raises ValueError: If no file has been named.
        """
        if self._vcd_ is None:
            if self.vcd_file is None:
                raise ValueError(f"{self.get_full_name()}: no VCD file - set factory variable '{self.get_full_name()}.vcd_file' or call load()")
            self.load(self.vcd_file)
        assert self._vcd_ is not None
        return self._vcd_

    def load(self, filename: str) -> Vcd:
        """
        Read a VCD file, replacing any loaded before.

        :param filename: Path to the file.
        :type filename: str
        :return: The loaded VCD.
        :rtype: Vcd
        """
        self.vcd_file = filename
        self._vcd_ = Vcd(filename)
        self.info(f"Loaded {self._vcd_}")
        return self._vcd_

    def set_window(self, start: float | None = None, end: float | None = None, unit: str | None = None) -> None:
        """
        Replay only part of the capture.

        In timed mode the state of every bound signal at ``start`` is driven when playback begins and the
        changes after it follow at their recorded intervals, so a window into the middle of a capture
        starts from the right state. In clocked mode only the clock edges within the window are replayed.

        :param start: Start of the window, None for the beginning of the file.
        :type start: float | None
        :param end: End of the window, None for the end of the file.
        :type end: float | None
        :param unit: Unit of ``start`` and ``end``: a cocotb unit (``ns``, ``ps`` ...) or None for the file's own timescale units.
        :type unit: str | None
        """
        def to_units(t: float | None) -> int | None:
            if t is None:
                return None
            return int(t) if unit is None else self.vcd.to_units(t, unit)

        self._window_ = (to_units(start), to_units(end))

    def add_signal(self, name: str, hdl: Any) -> VcdSignal:
        """
        Bind a VCD signal to an HDL signal, driven at the times the file records (timed mode).

        :param name: Name of the signal in the VCD - full hierarchical, or any unambiguous trailing part.
        :type name: str
        :param hdl: The HDL signal to drive.
        :type hdl: cocotb handle
        :return: The VCD signal bound.
        :rtype: VcdSignal
        """
        sig = self._bind_(name, hdl)
        self._timed_.append((sig, hdl))
        return sig

    def add_scope(self, scope: str, hdl: Any, exclude: Iterable[str] = ()) -> list[VcdSignal]:
        """
        Bind every signal declared directly in a VCD scope to the signal of the same name under an HDL handle,
        driven at the times the file records (timed mode).

        A capture of a running design records its outputs alongside its inputs; name them in ``exclude`` and
        they are left to the DUT. Anything ``hdl`` does not have is skipped with a warning.

        .. code-block:: python

            self.drv.add_scope("tb.dut", self.hdl, exclude=("valid_out", "c"))

        :param scope: Full hierarchical name of the scope in the VCD, e.g. ``tb.dut``.
        :type scope: str
        :param hdl: The HDL hierarchy holding the signals to drive.
        :type hdl: cocotb handle
        :param exclude: Names of signals not to drive, by leaf or full VCD name.
        :type exclude: Iterable[str]
        :return: The VCD signals bound.
        :rtype: list[VcdSignal]
        """
        return [self.add_signal(sig.name, h) for sig, h in self._scope_(scope, hdl, exclude)]

    def _scope_(self, scope: str, hdl: Any, exclude: Iterable[str], skip: Iterable[VcdSignal] = ()) -> list[tuple[VcdSignal, Any]]:
        """
        The signals of a VCD scope paired with the HDL signals of the same name, less the excluded, the skipped,
        and those the HDL does not have.
        """
        excluded = set(exclude)
        # Exclude aliases by their shared identifier code
        skipped = {s.code for s in skip}
        pairs = []
        for sig in self.vcd.scope(scope):
            leaf = sig.name.rsplit(".", 1)[-1]
            if sig.code in skipped or leaf in excluded or sig.name in excluded:
                continue
            target = self._hdl_leaf_(hdl, leaf)
            if target is None:
                self.warning(f"{sig.name} has no counterpart under {hdl._path} - not driven")
                continue
            pairs.append((sig, target))
        return pairs

    def add_clock(self, name: str, hdl_clock: Any, rising: bool = True) -> VcdClockGroup:
        """
        Create a group of signals driven on the edges of a testbench clock (clocked mode).

        The testbench drives ``hdl_clock`` itself, with :meth:`avl.Env.clock` or however it likes. The
        signals added to the returned group are driven after each edge of it with the values the file
        shows being sampled at the corresponding edge of ``name``.

        :param name: Name of the clock in the VCD.
        :type name: str
        :param hdl_clock: The HDL clock that paces the replay.
        :type hdl_clock: cocotb handle
        :param rising: Use rising edges if True, falling if False.
        :type rising: bool
        :return: The group, to add signals to.
        :rtype: VcdClockGroup
        """
        clock = self.vcd.lookup(name)
        if clock.width != 1:
            raise ValueError(f"{self.get_full_name()}: clock {clock.name} is {clock.width} bits wide")
        group = VcdClockGroup(self, clock, hdl_clock, rising)
        self._groups_.append(group)
        return group

    @staticmethod
    def _hdl_leaf_(hdl: Any, leaf: str) -> Any:
        """
        The HDL signal named ``leaf`` under ``hdl``, or None.

        A leaf of the form ``a[3]`` - one bit or element of ``a``, as a simulator that dumps a bus bit by bit
        declares it - is looked up as element 3 of ``hdl.a``, where the handle allows indexing.
        """
        target = getattr(hdl, leaf, None)
        if target is not None or not leaf.endswith("]") or "[" not in leaf:
            return target
        base, index = leaf[:-1].split("[", 1)
        parent = getattr(hdl, base, None)
        if parent is None or not index.isdigit():
            return None
        try:
            return parent[int(index)]
        except (TypeError, IndexError, KeyError):
            return None

    def _bind_(self, name: str, hdl: Any) -> VcdSignal:
        """
        Look a signal up and check it against the handle it will drive.
        """
        sig = self.vcd.lookup(name)
        if sig.var_type == "string":
            raise ValueError(f"{self.get_full_name()}: {sig.name} is a string variable and cannot be driven")

        if sig.var_type != "real":
            if hasattr(hdl, "__len__"):
                hdl_width = len(hdl)
            elif isinstance(hdl, LogicObject):
                hdl_width = 1
            else:
                hdl_width = None
            if hdl_width is not None and hdl_width != sig.width:
                self.warning(f"{sig.name} is {sig.width} bits in {self.vcd.filename} but {hdl._path} is {hdl_width} bits")

        return sig

    @staticmethod
    def _drive_(hdl: Any, value: VcdValue) -> None:
        """
        Put a VCD value onto a handle: int for known values, a binary string carrying x/z otherwise.
        """
        hdl.value = value

    def _steps_(self, time: int) -> int:
        """
        A duration in VCD timescale units as simulator steps.
        """
        mag, unit = self.vcd.timescale
        return int(convert(time * mag, unit, to="step", round_mode="round"))

    async def _play_timed_(self) -> None:
        """
        Replay the timed signals: the state at the window start now, then each change at its recorded interval.
        """
        vcd = self.vcd
        start, end = self._window_
        t0 = 0 if start is None else start
        t_end = vcd.end_time if end is None else end
        base = get_sim_time("step")

        mag, unit = vcd.timescale
        try:
            convert(mag, unit, to="step", round_mode="error")
        except ValueError:
            self.warning(f"{vcd.filename} timescale {mag}{unit} is finer than the simulator precision - times are rounded")

        targets: dict[int, list[Any]] = {}
        signals: list[VcdSignal] = []
        for sig, hdl in self._timed_:
            if id(sig) not in targets:
                targets[id(sig)] = []
                signals.append(sig)
            targets[id(sig)].append(hdl)
            v = sig.value_at(t0, inclusive=True)
            if v is not None:
                self._drive_(hdl, v)

        for t, changes in vcd.timeline(signals, start=t0, end=t_end):
            target = base + self._steps_(t - t0)
            now = get_sim_time("step")
            if target > now:
                await Timer(target - now, "step")
            for sig, v in changes:
                for hdl in targets[id(sig)]:
                    self._drive_(hdl, v)

        # Preserve the window duration even if its final timestamp has no changes
        target = base + self._steps_(t_end - t0)
        now = get_sim_time("step")
        if target > now:
            await Timer(target - now, "step")

        self.info(f"{len(signals)} timed signals replayed to {t_end}{unit if mag == 1 else f' x {mag}{unit}'}")

    async def run_phase(self) -> None:
        """
        Replay everything bound, holding an objection until it is all driven.
        """
        if not self._timed_ and not any(g.signals for g in self._groups_):
            self.warning("No signals bound - nothing to drive")
            self.done.set()
            return

        if self.objection:
            self.raise_objection()

        tasks = []
        if self._timed_:
            tasks.append(cocotb.start_soon(self._play_timed_()))
        for g in self._groups_:
            if g.signals:
                tasks.append(cocotb.start_soon(g.play()))
        await Combine(*(t.complete for t in tasks))

        self.info("Playback complete")
        self.done.set()

        if self.objection:
            self.drop_objection()

__all__ = ["VcdDriver", "VcdClockGroup"]
