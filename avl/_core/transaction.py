# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Transacation

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cocotb.triggers import Event
from cocotb.utils import get_sim_time

from .object import Object


class Transaction(Object):
    # Defaults held on the class - a transaction that is never given an id or
    # an event stores neither.

    _id_ = -1
    """Transaction id, shared until ``set_id`` gives the transaction its own."""

    _events_ = {}
    """Empty event table, shared by every transaction that has no events.
    ``add_event`` replaces it with a per-instance copy.
    """

    def __init__(self, name: str, parent: Object|None) -> None:
        """
        Initialize a new Transaction.

        :param name: The name of the transaction.
        :type name: str
        """
        super().__init__(name, parent)

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
        events = self._events_
        if events is Transaction._events_:
            events = self._events_ = {}

        if name not in events:
            events[name] = [0, Event(), []]

        if callback is not None:
            events[name][2].append(callback)

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

    def set_event(self, name: str, *args: list[Any], **kwargs: list[Any]) -> None:
        """
        Set an event and trigger its callbacks.

        :param name: The name of the event.
        :type name: str
        :param args: Additional arguments for the callback.
        :param kwargs: Additional keyword arguments for the callback.
        """
        if "unit" in kwargs:
            self._events_[name][0] = get_sim_time(unit=kwargs["unit"])
        else:
            self._events_[name][0] = get_sim_time(unit="ns")

        self._events_[name][1].set()

        for cb in self._events_[name][2]:
            if cb is not None:
                cb(*args, **kwargs)

    async def wait_on_event(self, name: str) -> None:
        """
        Wait for an event to be set.

        :param name: The name of the event.
        :type name: str
        """
        await self._events_[name][1].wait()


__all__ = ["Transaction"]
