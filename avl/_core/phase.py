# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Phase Functions

from __future__ import annotations

from typing import Any

from cocotb.triggers import Event


class Phase:
    def __init__(self, name: str, top_down: bool = True) -> None:
        """
        Initializes the Phase instance.

        :param name: Name of the phase.
        :type name: str
        :param top_down: Indicates if the phase is top-down (default is True).
        :type top_down: bool
        """
        self.name = name
        self.top_down = top_down
        self.prev: None | Phase = None
        self.next: None | Phase = None
        self.objections = {}
        self._objection_ev = Event()

    def insert(self, after: Phase|None = None) -> None:
        """
        Inserts the phase after another phase.

        :param after: The phase to insert after (optional).
        :type after: Phase, optional
        """
        if after is not None:
            self.prev = after
            self.next = after.next
            if after.next is not None:
                after.next.prev = self
            after.next = self

    def remove(self) -> None:
        """
        Removes the phase.
        """
        if self.prev is not None:
            self.prev.next = self.next
        if self.next is not None:
            self.next.prev = self

    def raise_objection(self, obj: Any) -> None:
        """
        Raises an objection for the phase.

        :param obj: The object raising the objection.
        :type obj: Any
        """
        if obj not in self.objections.keys():
            self.objections[obj] = 0
        self.objections[obj] += 1

    def drop_objection(self, obj: Any) -> None:
        """
        Drops an objection for the phase.

        :param obj: The object dropping the objection.
        :type obj: Any
        """
        if obj in self.objections.keys():
            self.objections[obj] -= 1
        else:
            raise ValueError(f"Object {obj} does not have an objection to drop")

        if self.objections[obj] == 0:
            self.objections.pop(obj)

        if len(self.objections) == 0:
            self._objection_ev.set()

    async def wait_for_objections(self) -> None:
        """
        Waits for all objections to be dropped.
        """
        if len(self.objections) != 0:
            await self._objection_ev.wait()


__all__ = ["Phase"]
