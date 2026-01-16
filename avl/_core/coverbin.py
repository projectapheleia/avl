# Apheleia Verification Library Hierachical component
# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Coverpoint

from math import sqrt
from typing import Any

import pandas as pd

from .component import Component
from .var import Var


class Coverbin(Component):
    def __init__(self, name: str, parent: Any, *args: Any, **kwargs: Any) -> None:
        """
        Initialize an instance of the Coverbin class.

        :param name: The name of the AVL cover bin.
        :type name: str
        :param parent: The parent component of the AVL cover bin.
        :type parent: object
        :param args: Additional arguments that can be values (int, float, Var), ranges, or lambda functions.
        :type args: int, float, Var, range, callable
        :param kwargs: Additional keyword arguments for configuration.
        :type kwargs: dict

        :raises ValueError: If an unknown bin condition is provided in args.
        """
        super().__init__(name, parent)

        if "illegal" in kwargs:
            self.illegal = kwargs["illegal"]
        else:
            self.illegal = False
        if "stats" in kwargs:
            self.stats = kwargs["stats"]
        else:
            self.stats = False

        self._values_ = []
        self._ranges_ = []
        self._funcs_ = []
        self._count_ = 0

        # Stats
        if self.stats:
            self.min = None
            self.max = None
            self.mean = 0.0
            self._m2_ = 0.0

        for arg in args:
            if isinstance(arg, (int | float | list | tuple | set | Var)):
                self._values_.append(arg)
            elif isinstance(arg, range):
                self._ranges_.append(arg)
            elif callable(arg) and (arg.__name__ == "<lambda>"):
                self._funcs_.append(arg)
            else:
                raise ValueError(f"Unknown bin condition {arg}")

    def check(self, var: Any) -> bool:
        """
        Check if the given variable matches any of the bin's conditions.

        :param var: The variable to be checked.
        :type var: Any

        :return: True if the variable matches any condition, False otherwise.
        :rtype: bool
        """
        if var is None:
            return False

        hit = False
        for v in self._values_:
            if v == var:
                hit = True

        for r in self._ranges_:
            if var in r:
                hit = True

        for f in self._funcs_:
            if f(var):
                hit = True

        return hit

    def sample(self, var: Any) -> None:
        """
        Check if the given variable matches any of the bin's conditions and increment the count.

        :param var: The variable to be checked.
        :type var: Any
        """

        if self.check(var):
            if self.illegal:
                raise ValueError(f"Illegal value {var} found in coverbin {self.name}")
            self._count_ += 1

            if self.stats:
                var_float = float(var)
                if self.min is None or var_float < self.min:
                    self.min = var_float
                if self.max is None or var_float > self.max:
                    self.max = var_float

                delta = float(var) - self.mean
                self.mean += delta / self._count_
                delta2 = float(var) - self.mean
                self._m2_ += delta * delta2

    def get_mean(self) -> float|None:
        """
        Return the mean value.

        :return: The mean value.
        :rtype: float
        """
        if self.stats:
            return self.mean if self._count_ > 0 else None
        else:
            return None

    def get_variance(self) -> float|None:
        """
        Return the variance value.

        :return: The variance value.
        :rtype: float
        """
        if self.stats:
            return self._m2_ / (self._count_ - 1) if self._count_ > 1 else None
        else:
            return None

    def get_stddev(self) -> float|None:
        """
        Return the standard deviation value.

        :return: The standard deviation value.
        :rtype: float
        """
        if self.stats:
            variance = self.get_variance()
            assert variance is not None
            return sqrt(variance) if self._count_ > 1 else None
        else:
            return None

    def report(self) -> pd.DataFrame:
        """
        Generate a report of the coverage data.

        :return: A DataFrame containing the coverage data. The structure of the DataFrame depends on the value of the `full` parameter:
             - If `full` is True, the DataFrame contains columns: 'covergroup', 'coverpoint', 'at_least', 'count'.
             - If `full` is False, the DataFrame contains columns: 'covergroup', 'coverpoint', 'coverage'.
        :rtype: pandas.DataFrame
        """

        if self.stats:
            return pd.DataFrame(
                {
                    "bin": [self.name],
                    "count": [int(self._count_)],
                    "min": [self.min],
                    "max": [self.max],
                    "mean": [self.get_mean()],
                    "variance": [self.get_variance()],
                    "stddev": [self.get_stddev()],
                }
            )
        else:
            return pd.DataFrame({"bin": [self.name], "count": [int(self._count_)]})


__all__ = ["Coverbin"]
