# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library List

from typing import Any, Iterable, SupportsIndex

from cocotb.triggers import Event


class List(list):
    def __init__(self, *args: list[Any]) -> None:
        """
        Initializes the List.

        :param args: Initial elements of the list.
        :type args: list[Any]
        """
        super().__init__(args)
        self._push_event = Event()
        self._pop_event = Event()

    def append(self, data: Any) -> None:
        """
        Appends an element to the list and sets the event.

        :param data: The element to be appended.
        :type data: Any
        """
        super().append(data)
        self._push_event.set()

    def clear(self) -> None:
        """
        Clears the list and clears the event.
        """
        super().clear()
        self._pop_event.set()

    def extend(self, iterable: Iterable) -> None:
        """
        Extends the list with elements from an iterable and sets the event.

        :param iterable: The iterable to extend the list with.
        :type iterable: list[Any]
        """
        super().extend(iterable)
        self._push_event.set()

    def insert(self, index: SupportsIndex, data: Any) -> None:
        """
        Inserts an element at a given position in the list and sets the event.

        :param index: Position at which to insert the element.
        :type index: int
        :param data: The element to be inserted.
        :type data: Any
        """
        super().insert(index, data)
        self._push_event.set()

    def pop(self, index: SupportsIndex = -1) -> Any:
        """
        Pops an element from the list at a given position.

        :param index: Position from which to pop the element. Defaults to -1 (last element).
        :type index: int
        :returns: The popped element.
        :rtype: Any
        """
        v = super().pop(index)
        self._pop_event.set()
        return v

    def remove(self, data: Any) -> None:
        """
        Removes the first occurrence of an element from the list and sets the event.

        :param data: The element to be removed.
        :type data: Any
        """
        super().remove(data)
        self._pop_event.set()

    async def blocking_pop(self) -> Any:
        """
        Pops an element from the list, blocking if the list is empty.

        :returns: The popped element.
        :rtype: Any
        """
        await self._push_event.wait()
        v = self.pop(0)
        if len(self) == 0:
            self._push_event.clear()
        return v

    async def blocking_get(self) -> Any:
        """
        Gets an element from the list, blocking if the list is empty.

        :returns: The retrieved element.
        :rtype: Any
        """
        return await self.blocking_pop()

Queue = List

__all__ = ["List"]
