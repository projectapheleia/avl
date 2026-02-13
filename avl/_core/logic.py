# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class


from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from z3 import BitVec, Extract, Optimize

from .var import Var


class Logic(Var):

    def __copy__(self):
        """
        Copy the Logic - always make a copy to ensure randomness is preserved.

        :return: Copied Var.
        :rtype: Var
        """
        new_obj = Logic(self.value, auto_random=self._auto_random_, fmt=self._fmt_, width=self.width)
        new_obj._constraints_ = {
            k: v.copy() for k, v in self._constraints_.items()
        }
        return  new_obj

    def __init__(
        self,
        *args,
        auto_random: bool = True,
        fmt: Callable[..., str] = hex,
        width: int = 32
    ) -> None:
        """
        Initialize an instance of the class.

        :param value: The initial value of the variable.
        :type value: any
        :param auto_random: Indicates if the variable should be automatically randomized, defaults to True.
        :type auto_random: bool, optional
        :param fmt: The format of the variable, defaults to hex.
        :type fmt: type, optional
        :param width: The width of the variable in bits, defaults to 32.
        :type width: int, optional
        :raises ValueError: If the width is not a positive integer.
        """
        if not isinstance(width, int) or width <= 0:
            raise ValueError("Width must be a positive integer.")
        self.width = int(width)

        super().__init__(*args, auto_random=auto_random, fmt=fmt)

    def _cast_(self, other: Any) -> int:
        """
        Cast the value to the appropriate type based on the width of the variable.

        :param other: The value to be cast.
        :type other: Any
        :return: The casted value.
        :rtype: int
        """
        v = other.value if isinstance(other, Logic) else other
        return int(v) & self._range_()[1]

    def _wrap_(self, result : Any) -> Logic:
        """
        Wrap the result in an Logic instance.

        :param result: The result to be wrapped.
        :type result: Any
        :return: An instance of Logic with the result.
        :rtype: Logic
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_, width=self.width)

    def _range_(self) -> tuple[int, int]:
        """
        Get the range of values that can be represented by this variable.

        :return: A tuple containing the minimum and maximum values.
        :rtype: tuple[int, int]
        """
        return (0, (1 << self.width) - 1)

    def _z3_(self) -> BitVecRef:
        """
        Get the Z3 representation of the variable.

        :return: The Z3 BitVec representation of the variable.
        :rtype: z3.BitVecRef
        """
        return BitVec(f"{self._idx_}", self.width)

    def _apply_constraints_(self, solver : Optimize) -> None:
        """
        Apply the constraints to the solver.

        :param solver: The optimization solver to apply the constraints to.
        :type solver: Optimize
        :param add_randomization: Add constraints for randomization
        :type add_randomization: bool
        """

        super()._apply_constraints_(solver)

        # Add soft constraint randomizing each bit
        for b in range(self.width):
            bv = random.randint(0,1)
            solver.add_soft(Extract(b,b,self._rand_) == bv, weight=100)

    def __getitem__(self, key):
        if isinstance(key, slice):
            assert key.start >= 0 and key.stop >= 0, "Slice indexes must be positive integers"
            assert key.stop >= key.start, "Only [lower_bound:upper_bound] format is supported"
            assert key.step is None, "Steps are not supported"
            assert key.stop <= self.width, f"Cannot index [{key.start}:{key.stop}] in var of width {self.width}"

            mask = (1 << (key.stop - key.start))-1
            rshift_width = key.start
        elif isinstance(key, int):
            assert key >= 0 and key <= self.width, f"Cannot index {key} in var of width {self.width}"

            mask = 0x1
            rshift_width = key
        else:
            raise ValueError(f"Unsupported slice type: {type(key)}")

        return (self.value >> rshift_width) & mask

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            assert key.start >= 0 and key.stop >= 0, "Slice indexes must be positive integers"
            assert key.stop >= key.start, "Only [lower_bound:upper_bound] format is supported"
            assert key.step is None, "Steps are not supported"
            assert key.stop <= self.width, f"Cannot index [{key.start}:{key.stop}] in var of width {self.width}"

            mask = (1 << (key.stop - key.start))-1
            lshift_width = key.start
        elif isinstance(key, int):
            assert key >= 0 and key <= self.width, f"Cannot index {key} in var of width {self.width}"

            mask = 0x1
            lshift_width = key
        else:
            raise ValueError(f"Unsupported slice type: {type(key)}")

        self.value = (self.value & ~(mask << lshift_width)) | ((value & mask) << lshift_width)


__all__ = ["Logic"]
