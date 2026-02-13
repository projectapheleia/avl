# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library List

from collections.abc import Iterable
from typing import Any, SupportsIndex

from .list import List


class Fifo(List):
    def __init__(self, depth: int, *args: list[Any]) -> None:
        """
        Initializes a FIFO (First In, First Out) list with a specified depth.
        The FIFO will only allow appending elements until it reaches its depth limit.

        :param depth: The maximum number of elements the FIFO can hold.
        :type depth: int
        :param args: Additional arguments to be passed to the List constructor.
        :type args: list[Any]
        """
        super().__init__(*args)
        self.depth = depth

    def append(self, data: Any) -> None:
        """
        Appends an element to the FIFO if it is not full.

        :param data: The element to be appended.
        :type data: Any
        """
        if len(self) < self.depth:
            super().append(data)

    def extend(self, iterable: Iterable) -> None:
        """
        Extends the FIFO with elements from an iterable, ensuring it does not exceed its depth.

        :param iterable: The iterable to extend the FIFO with.
        :type iterable: list[Any]
        """
        for i in iterable:
            if len(self) < self.depth:
                super().append(i)
            else:
                break

    def insert(self, index: SupportsIndex, data: Any) -> None:
        """
        Raises NotImplementedError as insertion at arbitrary positions is not supported.

        :param index: The index at which to insert.
        :type index: int
        :param data: The data to be inserted.
        :type data: Any
        :raises NotImplementedError: This method is not implemented for FIFO.
        """
        raise NotImplementedError

    def remove(self, data: Any) -> None:
        """
        Raises NotImplementedError as removing elements is not supported in FIFO.
        This is because FIFO operates on a first-in, first-out basis and does not allow arbitrary removals.

        :param data: The element to be removed.
        :type data: Any
        :raises NotImplementedError: This method is not implemented for FIFO.
        """
        raise NotImplementedError

    async def blocking_push(self, data: Any) -> None:
        """
        Pushes an element onto the FIFO, blocking if the FIFO is full.

        :param data: The element to be pushed onto the FIFO.
        :type data: Any
        """
        while len(self) >= self.depth:
            await self._pop_event.wait()
            self._pop_event.clear()
        self.append(data)

    async def blocking_put(self, data: Any) -> None:
        """
        Alias for blocking_push. Pushes an element onto the FIFO, blocking if the FIFO is full.

        :param data: The element to be put into the FIFO.
        :type data: Any
        """
        await self.blocking_push(data)


__all__ = ["Fifo"]
