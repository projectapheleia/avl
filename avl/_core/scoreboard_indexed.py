# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Indexed Scoreboard

from typing import Any

from .component import Component
from .scoreboard import Scoreboard
from cocotb import start_soon


class IndexedScoreboard(Scoreboard):
    def __init__(self, name: str, parent: Component) -> None:
        """
        Initializes the indexed scoreboard component.

        :param name: Name of the indexed scoreboard.
        :type name: str
        :param parent: Parent component.
        :type parent: Component
        """
        super().__init__(name, parent)
        self.scoreboards = {}

    def set_indices(self, indices: list[Any]) -> None:
        """
        Sets the indices for the scoreboards.

        :param indices: List of indices.
        :type indices: list[Any]
        """
        for idx in indices:
            self.scoreboards[idx] = Scoreboard(f"{self.name}_{idx}", self)
            self.scoreboards[idx].set_verbose(self.verbose)
            self.scoreboards[idx].set_min_compare_count(self.min_compare_count)

    def set_verbose(self, verbose: bool) -> None:
        """
        Sets the verbosity of the scoreboards.

        :param verbose: Verbosity flag.
        :type verbose: bool
        """
        super().set_verbose(verbose)
        for v in self.scoreboards.values():
            v.set_verbose(verbose)

    def set_min_compare_count(self, count: int) -> None:
        """
        Sets the minimum number of comparisons required for the scoreboards.

        :param count: Minimum number of comparisons.
        :type count: int
        """
        super().set_min_compare_count(count)
        for v in self.scoreboards.values():
            v.set_min_compare_count(count)

    def get_index(self, item: Any) -> int:
        """
        Gets the index for the given item.

        :param item: The item to get the index for.
        :type item: Any
        :returns: The index of the item.
        :rtype: int
        """
        raise NotImplementedError

    async def _forward_before(self) -> None:
        while True:
            before_item = await self.before_port.blocking_pop()
            self.scoreboards[self.get_index(before_item)].before_port.append(before_item)

    async def _forward_after(self) -> None:
        while True:
            after_item = await self.after_port.blocking_pop()
            self.scoreboards[self.get_index(after_item)].after_port.append(after_item)

    async def run_phase(self) -> None:
        """
        The idea here is very simple - indexed scoreboard isn't a scoreboard by itself,
        but rather a filter that sends inputs into the right scoreboard.
        For this reason, it doesn't follow the scoreboard's system of wait for before_item -> wait for after_item.
        The moment it receives any item, it passes it to the correct scoreboard.
        """
        start_soon(self._forward_before())
        start_soon(self._forward_after())

    async def report_phase(self) -> None:
        """
        Reports the results of the scoreboard.
        compare_count part is removed, due to no comparisons being made here.
        """
        if len(self.before_port) + int(self.before_item is not None) > 0 or len(
            self.after_port
        ) + int(self.after_item is not None):
            self.error(
                f"Outstanding items: before_port={len(self.before_port) + int(self.before_item is not None)} after_port={len(self.after_port) + int(self.after_item is not None)}"
            )



__all__ = ["IndexedScoreboard"]
