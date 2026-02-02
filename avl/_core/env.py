# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Environment

from __future__ import annotations

from cocotb.clock import Clock
from cocotb.handle import HierarchyObject, LogicObject
from cocotb.triggers import RisingEdge, Timer
from cocotb.simtime import TimeUnitWithoutSteps, Steps

from .component import Component


class Env(Component):
    def __init__(self, name: str, parent: Component) -> None:
        """
        Initializes the environment with the given name, parent.

        :param name: The name of the environment.
        :type name: str
        :param parent: The parent object of the environment.
        :type parent: object
        """
        super().__init__(name, parent)

    async def sync_reset(
        self, clk: LogicObject, rst: HierarchyObject, cycles: int, active_high: bool = True
    ) -> None:
        """
        Perform a synchronous reset.

        :param clk: Clock signal
        :type clk: object
        :param rst: Reset signal
        :type rst: object
        :param cycles: Number of clock cycles to hold the reset
        :type cycles: int
        :param active_high: Reset is active high if True, active low if False
        :type active_high: bool
        """
        rst.value = int(active_high)
        for _ in range(cycles):
            await RisingEdge(clk)
        rst.value = int(not active_high)

    async def async_reset(
        self, rst: HierarchyObject, duration: int, units: TimeUnitWithoutSteps|Steps = "ns", active_high: bool = True
    ) -> None:
        """
        Perform an asynchronous reset.

        :param rst: Reset signal
        :type rst: object
        :param duration: Duration of the reset
        :type duration: int
        :param units: Time units for the duration, defaults to 'ns'
        :type units: str
        :param active_high: Reset is active high if True, active low if False
        :type active_high: bool
        """
        rst.value = int(active_high)
        await Timer(duration, units)
        rst.value = int(not active_high)

    async def clock(self, clk: LogicObject, freq_mHz: int) -> None:
        """
        Generate a clock signal.

        :param clk: Clock signal
        :type clk: object
        :param freq_mHz: Frequency in megaHertz
        :type freq_mHz: int
        """
        freq_Hz = 1000000 * freq_mHz
        period_ps = 1000000000000 / freq_Hz

        clk.value = 0
        await Clock(clk, period_ps, "ps").start()

    async def ticker(self, duration: int, msg: str, units: TimeUnit = "ns") -> None:
        """
        Log a message at regular intervals.

        :param duration: Interval duration
        :type duration: int
        :param msg: Message to log
        :type msg: str
        :param units: Time units for the duration, defaults to 'ns'
        :type units: str
        """
        while True:
            await Timer(duration, units)
            self.info(msg)

    async def timeout(self, duration: int, units: TimeUnit = "ns") -> None:
        """
        Raise a timeout exception after a specified duration.

        :param duration: Timeout duration
        :type duration: int
        :param units: Time units for the duration, defaults to 'ns'
        :type units: str
        """
        await Timer(duration, units)
        self.fatal("Timeout")

__all__ = ["Env"]
