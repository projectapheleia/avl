# Apheleia Verification Library Hierachical component
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Coverpoint

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from .component import Component
from .coverbin import Coverbin

if TYPE_CHECKING:
    from .covergroup import Covergroup

class Coverpoint(Component):
    def __init__(self, name: str, parent: Covergroup, var: Any = None) -> None:
        """
        Initialize an instance of the class.

        :param name: The name of the instance, defaults to an empty string.
        :type name: str, optional
        :param parent: The parent instance, defaults to None.
        :type parent: object, optional
        :param var: An optional variable, defaults to None.
        :type var: object, optional
        """
        super().__init__(name, parent)

        self.var = var
        self.comment = None
        self.weight = parent.weight if parent is not None else 1
        self.at_least = 1
        self._bins_ = {}

    def set_comment(self, comment: str) -> None:
        """
        Set the comment for the AVL coverpoint.

        :param comment: The comment to be set.
        :type comment: str
        """
        self.comment = comment

    def set_weight(self, weight: float) -> None:
        """
        Set the weight of the AVL cover point.

        :param weight: The weight to be set.
        :type weight: float
        """
        self.weight = weight

    def set_at_least(self, at_least: int) -> None:
        """
        Set the minimum threshold value.

        :param at_least: The minimum value to be set.
        :type at_least: int
        """
        self.at_least = at_least


    def add_bin(self, name: str, *args: list[Any], **kwargs: list[Any]) -> None:
        """
        Add a bin to the AVL coverpoint.

        :param name: The name of the bin to add.
        :type name: str
        :param args: Additional arguments to pass to the Coverbin constructor.
        :param illegal: Flag indicating if the bin is illegal. Defaults to False.
        :type illegal: bool, optional
        :param stats: Flag indicating if statistics should be collected for the bin. Defaults to False.
        :type stats: bool, optional
        :raises ValueError: If a bin with the given name already exists.
        """

        if name not in self._bins_:
            self._bins_[name] = Coverbin(name, self, *args, **kwargs)
        else:
            raise ValueError(f"Bin {name} already exists")

    def remove_bin(self, name: str) -> None:
        """
        Remove a bin from the AVL coverpoint.

        :param name: The name of the bin to remove.
        :type name: str
        :raises KeyError: If the bin with the given name does not exist.
        """
        if name in self._bins_:
            del self._bins_[name]
        else:
            raise ValueError(f"Bin {name} does not exist")

    def get_hit(self) -> Coverbin|None:
        """
        Check if the variable matches any bin condition.

        This method iterates over all bins stored in the `_bins_` attribute and
        checks if the variable `self.var` matches any bin condition by calling
        the `check` method on each bin.

        :return: The bin that matches the variable condition, or None if no bin matches.
        :rtype: Coverbin or None
        """
        for bin in self._bins_.values():
            if bin.check(self.var()):
                return bin

        return None

    def sample(self) -> None:
        """
        Sample values from each bin in the `_bins_` attribute.

        This method iterates over all bins stored in the `_bins_` attribute and
        calls the `sample` method on each bin, passing the result of `self.var()`
        as an argument.
        """
        for b in self._bins_.values():
            b.sample(self.var())

    def clear(self) -> None:
        """
        Clear the counts of all bins in the `_bins_` attribute.

        This method iterates over all bins stored in the `_bins_` attribute and
        calls the `clear` method on each bin to reset their counts.
        """
        for b in self._bins_.values():
            b._count_ = 0

    def get_bins(self) -> tuple[int, int]:
        """
        Calculate the total number of bins and the number of covered bins.

        This method iterates over all bins in the `_bins_` dictionary and counts
        the total number of bins and the number of bins that have a count greater
        than or equal to `at_least`.

        :returns: A tuple containing the total number of bins and the number of covered bins.
        :rtype: tuple(int, int)
        """
        total = 0
        covered = 0

        for bin in self._bins_.values():
            if bin._count_ >= self.at_least:
                covered += 1
            total += 1

        return total, covered

    def get_coverage(self) -> float:
        """
        Calculate and return the coverage percentage.

        This method retrieves the total number of bins and the number of covered bins,
        then calculates the coverage percentage as (covered / total) * 100.

        :return: The coverage percentage. If the total number of bins is zero,
                 returns 0.0 to avoid division by zero.
        :rtype: float
        """
        total, covered = self.get_bins()

        if total == 0:
            return float(0)
        else:
            return float(covered / total) * 100

    def report(self, full: bool = False) -> pd.DataFrame:
        """
        Generate a report of the coverage data.

        :param full: If True, generate a detailed report including all bins. If False, generate a summary report. Default is False.
        :type full: bool, optional

        :return: A DataFrame containing the coverage data. The structure of the DataFrame depends on the value of the `full` parameter:
             - If `full` is True, the DataFrame contains columns: 'covergroup', 'coverpoint', 'at_least', 'count'.
             - If `full` is False, the DataFrame contains columns: 'covergroup', 'coverpoint', 'coverage'.
        :rtype: pandas.DataFrame
        """

        if full:
            retval = pd.DataFrame()
            for b in self._bins_.values():
                if retval is None:
                    retval = b.report()
                else:
                    retval = pd.concat([retval, b.report()], ignore_index=True)

            retval.insert(0, "name", self.name)
            retval.insert(2, "at_least", self.at_least)

            retval = retval.fillna("")
            retval = retval.dropna(axis=1, how="all")
            return retval
        else:
            return pd.DataFrame({"name": [self.name], "coverage": [self.get_coverage()]})


__all__ = ["Coverpoint"]
