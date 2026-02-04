# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Sequence Item

from __future__ import annotations

from typing import TYPE_CHECKING

from .sequencer import Sequencer
from .transaction import Transaction
from .component import Component

if TYPE_CHECKING:
    from .sequence import Sequence

class SequenceItem(Transaction):
    def __init__(self, name: str, parent: Sequencer|Sequence|Component|None) -> None:
        """
        Initializes the SequenceItem with a name and an optional parent component.

        :param name: Name of the sequence item.
        :type name: str
        :param parent: Parent component (optional).
        :type parent: Component
        """
        self._parent_sequence_ = None
        self._parent_sequencer_ = None

        parent_component = parent

        if isinstance(parent, SequenceItem):
            self._parent_sequence_ = parent
            self._parent_sequencer_ = parent.get_sequencer()
            parent_component = self._parent_sequencer_
        elif isinstance(parent, Sequencer):
            self._parent_sequencer_ = parent

        super().__init__(name, parent_component)

        self.add_event("done")
        self.add_event("response")

    def set_sequencer(self, sequencer: Sequencer) -> None:
        """
        Sets the sequencer for the item.

        :param sequencer: The sequencer to be set.
        :type sequencer: Sequencer
        """
        self._parent_sequencer_ = sequencer

    def get_sequencer(self) -> Sequencer|None:
        """
        Gets the sequencer of the item.

        :returns: The sequencer of the item.
        :rtype: Sequencer
        """
        return self._parent_sequencer_

    def set_parent_sequence(self, sequence: Sequence) -> None:
        """
        Sets the parent sequence for the item.

        :param sequence: The parent sequence to be set.
        :type sequence: Sequence
        """
        self._parent_sequence_ = sequence

    def get_parent_sequence(self) -> Sequence| None:
        """
        Gets the parent sequence of the item.

        :returns: The parent sequence of the item.
        :rtype: Sequence
        """
        return self._parent_sequence_

    def get_root_sequece(self) -> Sequence|None:
        """
        Gets the root sequence of the item.

        :returns: The root sequence of the item.
        :rtype: Sequence
        """
        retVal = self._parent_sequence_
        while retVal is not None:
            if retVal._parent_sequence_ is not None:
                retVal = self._parent_sequence_
        return retVal


__all__ = ["SequenceItem"]
