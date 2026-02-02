# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Transacation

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from cocotb.triggers import Event
from cocotb.simtime import TimeUnitWithoutSteps, Steps
from cocotb.utils import get_sim_time

from .object import Object

if TYPE_CHECKING:
    from .component import Component

class Transaction(Object):
    def __init__(self, name: str, parent: Component) -> None:
        """
        Initialize a new Transaction.

        :param name: The name of the transaction.
        :type name: str
        """
        super().__init__(name, parent)
        self._id_ = -1
        self._events_ = {}

    def set_id(self, id: int) -> None:
        """
        Set the ID of the transaction.

        :param id: The ID to set.
        :type id: int
        """
        self._id_ = id

    def get_id(self) -> int:
        """
        Get the ID of the transaction.

        :return: The ID of the transaction.
        :rtype: int
        """
        return self._id_

    def add_event(self, name: str, callback: Callable[..., Any]|None = None) -> None:
        """
        Add an event to the transaction.

        :param name: The name of the event.
        :type name: str
        :param callback: The callback function to be called when the event is set.
        :type callback: function or None
        """
        if name not in self._events_:
            self._events_[name] = [0, Event(), []]

        if callback is not None:
            self._events_[name][2].append(callback)

    def get_event(self, name: str) -> None:
        """
        Get an event by name.

        :param name: The name of the event.
        :type name: str
        :return: The event details or None if the event does not exist.
        :rtype: list or None
        """
        if name in self._events_:
            return self._events_[name]
        else:
            return None

    def set_event(self, name: str, unit: TimeUnitWithoutSteps|Steps = "ns",*args: Any, **kwargs: Any) -> None:
        """
        Set an event and trigger its callbacks.

        :param name: The name of the event.
        :type name: str
        :param args: Additional arguments for the callback.
        :param kwargs: Additional keyword arguments for the callback.
        """
        self._events_[name][0] = get_sim_time(unit=unit)
        self._events_[name][1].set()

        for cb in self._events_[name][2]:
            if cb is not None:
                cb(self, *args, **kwargs)

    async def wait_on_event(self, name: str) -> None:
        """
        Wait for an event to be set.

        :param name: The name of the event.
        :type name: str
        """
        await self._events_[name][1].wait()


__all__ = ["Transaction"]
