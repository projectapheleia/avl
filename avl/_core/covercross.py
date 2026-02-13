# Apheleia Verification Library Hierachical component
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Coverpoint

from __future__ import annotations

from itertools import product
from typing import TYPE_CHECKING

from .coverbin import Coverbin
from .coverpoint import Coverpoint

if TYPE_CHECKING:
    from .covergroup import Covergroup

class Covercross(Coverpoint):
    def __init__(self, name: str, parent: Covergroup) -> None:
        """
        Initialize an instance of the class.

        :param name: The name of the instance
        :type name: str
        :param parent: The parent instance
        :type parent: object
        """
        super().__init__(name, parent, var=None)
        self._points_ = []

    def add_points(self, args: list[Coverpoint]) -> None:
        """
        Add coverpoints to the cross.

        :param args: Coverpoints to be crossed
        :type args: list[Coverpoint]
        :raises ValueError: If the covercross already exists
        """
        self._points_ = args

        p = [arg._bins_ for arg in args]

        for c in product(*p):
            name = ", ".join([str(x) for x in c])
            self._bins_[name] = Coverbin(name, self, c)

    def sample(self) -> None:
        """
        Sample values from each bin in the `_bins_` attribute.

        This method iterates over all bins stored in the `_bins_` attribute and
        calls the `sample` method on each bin, passing the result of `self.var()`
        as an argument.
        """
        bins = []
        for p in self._points_:
            b = p.get_hit()
            if b is not None:
                bins.append(b.get_name())
            else:
                return

        v = tuple(bins)
        for b in self._bins_.values():
            b.sample(v)


__all__ = ["Covercross"]
