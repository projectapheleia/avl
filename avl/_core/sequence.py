# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Sequence

from __future__ import annotations

from typing import TYPE_CHECKING

from .sequence_item import SequenceItem

if TYPE_CHECKING:
    from .sequencer import Sequencer

class Sequence(SequenceItem):
    def __init__(self, name, parent_sequence: Sequence) -> None:
        """
        Initializes the Sequence with a name and parent sequence.

        :param name: Name of the sequence.
        :type name: str
        :param parent_sequence: Parent sequence, if any.
        :type parent_sequence: Sequence
        """
        super().__init__(name, parent_sequence)
        self.priority = 100
        self._idx_ = 0

    def set_priority(self, priority: int) -> None:
        """
        Sets the priority of the sequence.

        :param priority: The priority to be set.
        :type priority: int
        """
        self.priority = priority

    def get_priority(self) -> int:
        """
        Gets the priority of the sequence.

        :returns: The priority of the sequence.
        :rtype: int
        """
        return self.priority

    async def start_item(
        self, item: SequenceItem, priority: int|None = None, sequencer: Sequencer|None = None
    ) -> None:
        """
        Starts an item in the sequence.

        :param item: The item to be started.
        :type item: SequenceItem
        :param priority: The priority of the item (optional).
        :type priority: int
        :param sequencer: The sequencer to be used (optional).
        :type sequencer: Sequencer
        """
        item.set_id(self._idx_)
        self._idx_ += 1

        if sequencer is not None:
            _sqr = sequencer
        else:
            _sqr = self.get_sequencer()
            assert _sqr is not None

        item.set_sequencer(_sqr)

        await _sqr.wait_for_grant(self, priority)

        self.pre_do(item)

    async def finish_item(self, item: SequenceItem) -> None:
        """
        Finishes an item in the sequence.

        :param item: The item to be finished.
        :type item: SequenceItem
        """
        self.mid_do(item)

        _sqr = item.get_sequencer()
        if _sqr is None:
            raise Exception("Sequence item has no sequencer")

        _sqr.send_request(item)

        await item.wait_on_event("done")

        self.post_do(item)

    async def pre_start(self) -> None:
        """
        Pre-start hook for the sequence.
        """
        pass

    async def post_start(self) -> None:
        """
        Post-start hook for the sequence.
        """
        pass

    async def start(self) -> None:
        """
        Starts the sequence.
        """
        await self.pre_start()
        await self.pre_body()
        await self.body()
        await self.post_body()
        await self.post_start()

    async def pre_body(self) -> None:
        """
        Pre-body hook for the sequence.
        """
        pass

    async def post_body(self) -> None:
        """
        Post-body hook for the sequence.
        """
        pass

    async def body(self) -> None:
        """
        Body of the sequence.
        """
        pass

    def pre_do(self, item: SequenceItem) -> None:
        """
        Pre-do hook for an item.

        :param item: The item to be processed.
        """
        pass

    def mid_do(self, item: SequenceItem) -> None:
        """
        Mid-do hook for an item.

        :param item: The item to be processed.
        """
        pass

    def post_do(self, item: SequenceItem) -> None:
        """
        Post-do hook for an item.

        :param item: The item to be processed.
        """
        pass


__all__ = ["Sequence"]
