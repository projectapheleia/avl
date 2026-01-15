# Apheleia Verification Library Hierachical component
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Coverpoint

from collections.abc import Callable
from typing import Any

import pandas as pd

from .component import Component
from .coverage import Coverage
from .covercross import Covercross
from .coverpoint import Coverpoint


class Covergroup(Component):
    def __init__(self, name: str, parent: Component) -> None:
        """
        Covergroup class for managing coverpoints and covercrosses.

        :param name: Name of the covergroup
        :type name: str
        :param parent: Parent component
        :type parent: Component, optional
        """
        super().__init__(name, parent)

        self.comment = None
        self.weight = 1
        self._cps_ = {}

        # Register
        Coverage().add_covergroup(self)

    def set_comment(self, comment: str) -> None:
        """
        Set a comment for the covergroup.

        :param comment: Comment for the covergroup
        :type comment: str
        """
        self.comment = comment

    def set_weight(self, weight: float) -> None:
        """
        Set the weight for the covergroup.

        :param weight: Weight of the covergroup
        :type weight: float
        """
        self.weight = weight

    def add_coverpoint(self, name: str, var: Callable[..., Any]) -> Coverpoint:
        """
        Add a coverpoint to the covergroup.

        :param name: Name of the coverpoint
        :type name: str
        :param var: Function that returns the value to be covered
        :type var: Callable[Any]
        :raises ValueError: If the coverpoint already exists
        :return: The created coverpoint
        :rtype: Coverpoint
        """
        if name not in self._cps_:
            self._cps_[name] = Coverpoint(name, self, var)
        else:
            raise ValueError(f"Coverpoint {name} already exists")
        return self._cps_[name]

    def add_covercross(self, name: str, *args: list[Coverpoint]) -> Covercross:
        """
        Add a covercross to the covergroup.

        :param name: Name of the covercross
        :type name: str
        :param args: Coverpoints to be crossed
        :type args: list[Coverpoint]
        :raises ValueError: If the covercross already exists
        :return: The created covercross
        :rtype: Covercross
        """
        if name not in self._cps_:
            self._cps_[name] = Covercross(name, self)
            self._cps_[name].add_points(*args)
        else:
            raise ValueError(f"Covercross {name} already exists")
        return self._cps_[name]

    def sample(self) -> None:
        """
        Sample all coverpoints in the covergroup
        """
        for cp in self._cps_.values():
            cp.sample()

    def clear(self) -> None:
        """
        Clear all coverpoints in the covergroup
        """
        for cp in self._cps_.values():
            cp.clear()

    def get_bins(self) -> tuple[int, int]:
        """
        Get the total and covered bins for the covergroup

        :return: A tuple (total, covered)
        :rtype: tuple[int, int]
        """
        total = 0
        covered = 0

        for cp in self._cps_.values():
            c, t = cp.get_bins()
            total += t
            covered += c

        return total, covered

    def get_coverage(self) -> float:
        """
        Get the coverage percentage for the covergroup

        :return: Coverage percentage
        :rtype: float
        """
        total, covered = self.get_bins()

        if total == 0:
            return float(0)
        else:
            return float(covered / total) * 100

    def report(self, full: bool = False) -> pd.DataFrame:
        """
        Generate a report for the covergroup

        :param full: If True, generate a detailed report
        :return: A pandas DataFrame with the report
        """
        retval = pd.DataFrame()
        for cp in self._cps_.values():
            if retval is None:
                retval = cp.report(full=full)
            else:
                retval = pd.concat([retval, cp.report(full=full)], ignore_index=True)

        retval.insert(0, "covergroup", self.name)
        retval = retval.fillna("")
        return retval


__all__ = ["Covergroup"]
