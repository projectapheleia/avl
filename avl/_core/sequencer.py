# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Sequencer

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from cocotb.triggers import Event

from .component import Component
from .port import Port

if TYPE_CHECKING:
    from .sequence import Sequence
    from .sequence_item import SequenceItem

class Sequencer(Component):
    def __init__(self, name: str, parent: Component) -> None:
        """
        Initialize the Sequencer instance.

        :param name: Name of the sequencer.
        :type name: str
        :param parent: Parent component.
        :type parent: Component
        """

        super().__init__(name, parent)
        self.seq_item_export = Port("seq_item_export", self)
        # Locks
        self._locks_ = []
        self._lock_ev_ = Event()
        self.current_lock = None

        # Sequences
        self._seqs_ = []
        self._seq_ev_ = Event()

    def send_request(self, item: SequenceItem) -> None:
        """
        Sends a request to the sequencer.

        :param item: The item to be sent.
        """
        self.seq_item_export.write(item)

    def arbitrate(self) -> tuple[Sequence|None, Event|None, int|None]:
        """
        Arbitrates between available sequences based on their priorities.

        :returns: A tuple containing the selected sequence, its event, and its priority.
                 If no sequence is available, returns (None, None, None).
        """
        ids = []
        weights = []
        for i in range(len(self._seqs_)):
            if (self.current_lock) is None or (self._seqs_[i][0] == self.current_lock):
                ids.append(i)
                weights.append(self._seqs_[i][2])

        if len(ids) == 0:
            return (None, None, None)
        else:
            id = random.choices(ids, weights=weights, k=1)[0]
            return self._seqs_.pop(id)

    async def lock(self, seq: Sequence) -> None:
        """
        Locks the sequencer for the sequence.

        :param seq: The sequence locking the sequencer.
        """
        if seq in self._locks_:
            raise Exception("Sequence already requested sequencer lock")

        ev = Event()
        self._locks_.append((seq, ev))
        await ev.wait()
        ev.clear()
        self._lock_ev_.set()

    def unlock(self, seq: Sequence) -> None:
        """
        Unlocks the sequencer for the sequence.

        :param seq: The sequence unlocking the sequencer.
        """
        if self.current_lock == seq:
            self.current_lock = None

        for s, ev in self._locks_:
            if s == seq:
                self._locks_.remove((s, ev))
                break

    def get_lock(self) -> Sequence|None:
        """
        Gets the current lock.

        :returns: The current lock.
        """
        return self.current_lock

    async def wait_for_grant(self, seq: Sequence, priority: int|None = None) -> None:
        """
        Waits for a grant to run the sequence.

        :param seq: The sequence requesting the grant.
        :param priority: The priority of the sequence (optional).
        """
        if priority is None:
            priority = seq.get_priority()

        ev = Event()
        self._seqs_.append((seq, ev, priority))
        self._seq_ev_.set()

        await ev.wait()
        ev.clear()

    async def run_phase(self) -> None:
        """
        Runs the sequencer phase.
        """
        while True:
            # Wait until there is a sequence to run
            await self._seq_ev_.wait()
            self._seq_ev_.clear()

            while True:
                # Check locks
                if (self.current_lock is None) and (len(self._locks_) > 0):
                    (self.current_lock, lock_ev) = self._locks_.pop(0)
                    lock_ev.set()
                    await self._lock_ev_.wait()
                    self._lock_ev_.clear()

                # Arbitrate for the next sequence
                (_, ev, _) = self.arbitrate()
                if ev is not None:
                    ev.set()
                else:
                    break


__all__ = ["Sequencer"]
