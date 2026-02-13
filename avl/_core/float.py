# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class

from __future__ import annotations

import random
import struct
import warnings
from collections.abc import Callable
from typing import Any

import numpy as np
from z3 import FP, BitVec, BitVecNumRef, Extract, FPSort, Not, Optimize, fpBVToFP, fpIsInf, fpIsNaN

from .var import Var

FP16 = FPSort(5, 11)
FP32 = FPSort(8, 24)
FP64 = FPSort(11, 53)

class Fp16(Var):
    def __init__(self, *args, auto_random: bool = True, fmt: Callable[..., str] = str) -> None:
        """
        Initialize an instance of the class.

        :param value: The value to be assigned to the instance.
        :type value: int
        :param auto_random: Flag to enable automatic randomization, defaults to True.
        :type auto_random: bool, optional
        :param fmt: The format to be used, defaults to hex.
        :type fmt: function, optional
        """
        super().__init__(*args, auto_random=auto_random, fmt=fmt)
        self._bits_ = np.uint16(0)
        self.width = 16

    def _cast_(self, other: Any) -> np.float16:
        """
        Cast the other value to the type of this variable's value.

        :param other: The value to cast.
        :type other: Any
        :return: The casted value.
        :rtype: Any
        """
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning, message="overflow encountered in cast")

            v = other.value if isinstance(other, type(self)) else other

            if isinstance(v, BitVecNumRef):
                return np.frombuffer(struct.pack("H", v.as_long()), dtype=np.float16)[0]

            return np.float16(v)

    def _range_(self) -> tuple[float, float]:
        """
        Get the range of values that can be represented by this variable.

        :return: A tuple containing the minimum and maximum values.
        :rtype: tuple[int, int]
        """
        return (-np.finfo(self.value).max, np.finfo(self.value).max)

    def _z3_(self) -> FP:
        """
        Get the Z3 representation of the variable.

        :return: The Z3 FP representation of the variable.
        :rtype: FP
        """
        return FP(f"{self._idx_}", FP16)

    def _apply_constraints_(self, solver : Optimize) -> None:
        """
        Apply the constraints to the solver.

        :param solver: The optimization solver to apply the constraints to.
        :type solver: Optimize
        :param add_randomization: Add constraints for randomization
        :type add_randomization: bool
        """

        Var._apply_constraints_(self, solver)

        bv = BitVec(f"{self._idx_}", self.width)
        fp = FP16

        for b in range(self.width):
            solver.add_soft(Extract(b,b,bv) == random.randint(0,1), weight=100)

        solver.add(Not(fpIsNaN(self._rand_)))
        solver.add(Not(fpIsInf(self._rand_)))
        solver.add(self._rand_ == fpBVToFP(bv, fp))

    def _random_value_(self, bounds: tuple[float, float]|None = None) -> np.float16:
        """
        Randomize the value of the variable.

        :param bounds: Optional bounds for the random value.
        :type bounds: tuple[float, float], optional
        :return: A random float value within the specified bounds or the maximum value.
        :rtype: float
        """
        if bounds is None:
            bounds = self._range_()
        x = np.random.uniform(min(bounds), max(bounds))
        return self._cast_(x)

    def to_bits(self) -> int:
        """
        Get the raw representation of the variable.

        :return: The raw value.
        :rtype: float
        """
        return int(self.value.view(type(self._bits_)))

    def from_bits(self, raw: int) -> None:
        """
        Convert the raw representation back to a float.

        :param raw: The raw value.
        :type raw: int
        """
        self.value = type(self._bits_)(int(raw)).view(type(self.value))

    # Bitwise
    def __and__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __or__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __xor__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __lshift__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __rshift__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __iand__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __ior__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __ixor__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __ilshift__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __irshift__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __rand__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __ror__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __rxor__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __rlshift__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")
    def __rrshift__(self, _): raise NotImplementedError("Bitwise operations are not supported for floating-point variables.")

    # Comparison - need to override to handle NaN and other cases
    def __eq__(self, other):
        other_val = self._cast_(other)
        return not (np.isnan(self.value) or np.isnan(other_val)) and self.value == other_val

    def __ne__(self, other):
        other_val = self._cast_(other)
        return np.isnan(self.value) or np.isnan(other_val) or self.value != other_val

    def __lt__(self, other):
        other_val = self._cast_(other)
        return not (np.isnan(self.value) or np.isnan(other_val)) and self.value < other_val

    def __le__(self, other):
        other_val = self._cast_(other)
        return not (np.isnan(self.value) or np.isnan(other_val)) and self.value <= other_val

    def __gt__(self, other):
        other_val = self._cast_(other)
        return not (np.isnan(self.value) or np.isnan(other_val)) and self.value > other_val

    def __ge__(self, other):
        other_val = self._cast_(other)
        return not (np.isnan(self.value) or np.isnan(other_val)) and self.value >= other_val

class Fp32(Fp16):
    def __init__(self, *args, auto_random: bool = True, fmt: Callable[..., str] = str) -> None:
        """
        Initialize an instance of the class.

        :param value: The value to be assigned to the instance.
        :type value: int
        :param auto_random: Flag to enable automatic randomization, defaults to True.
        :type auto_random: bool, optional
        :param fmt: The format to be used, defaults to hex.
        :type fmt: function, optional
        """
        super().__init__(*args, auto_random=auto_random, fmt=fmt)
        self._bits_ = np.uint32(0)
        self.width = 32

    def _cast_(self, other: Any) -> Any:
        """
        Cast the other value to the type of this variable's value.

        :param other: The value to cast.
        :type other: Any
        :return: The casted value.
        :rtype: Any
        """
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning, message="overflow encountered in cast")

            v = other.value if isinstance(other, type(self)) else other
            if isinstance(v, BitVecNumRef):
                return np.frombuffer(struct.pack("I", v.as_long()), dtype=np.float32)[0]
            return np.float32(v)

    def _z3_(self) -> FP:
        """
        Get the Z3 representation of the variable.

        :return: The Z3 FP representation of the variable.
        :rtype: FP
        """
        return FP(f"{self._idx_}", FP32)

    def _apply_constraints_(self, solver : Optimize) -> None:
        """
        Apply the constraints to the solver.

        :param solver: The optimization solver to apply the constraints to.
        :type solver: Optimize
        :param add_randomization: Add constraints for randomization
        :type add_randomization: bool
        """

        Var._apply_constraints_(self, solver)

        bv = BitVec(f"{self._idx_}", self.width)
        fp = FP32

        for b in range(self.width):
            solver.add_soft(Extract(b,b,bv) == random.randint(0,1), weight=100)

        solver.add(Not(fpIsNaN(self._rand_)))
        solver.add(Not(fpIsInf(self._rand_)))
        solver.add(self._rand_ == fpBVToFP(bv, fp))

class Fp64(Fp16):
    def __init__(self, *args, auto_random: bool = True, fmt: Callable[..., str] = str) -> None:
        """
        Initialize an instance of the class.

        :param value: The value to be assigned to the instance.
        :type value: int
        :param auto_random: Flag to enable automatic randomization, defaults to True.
        :type auto_random: bool, optional
        :param fmt: The format to be used, defaults to hex.
        :type fmt: function, optional
        """
        super().__init__(*args, auto_random=auto_random, fmt=fmt)
        self._bits_ = np.uint64(0)
        self.width = 64

    def _cast_(self, other: Any) -> Any:
        """
        Cast the other value to the type of this variable's value.

        :param other: The value to cast.
        :type other: Any
        :return: The casted value.
        :rtype: Any
        """
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning, message="overflow encountered in cast")

            v = other.value if isinstance(other, type(self)) else other
            if isinstance(v, BitVecNumRef):
                return np.frombuffer(struct.pack("Q", v.as_long()), dtype=np.float64)[0]
            return np.float64(v)

    def _range_(self) -> tuple[float, float]:
        """
        Get the range of values that can be represented by this variable.

        :return: A tuple containing the minimum and maximum values.
        :rtype: tuple[float, float]
        """
        return (-1e100, 1e100) # Reduced to allow randomization

    def _z3_(self) -> FP:
        """
        Get the Z3 representation of the variable.

        :return: The Z3 FP representation of the variable.
        :rtype: FP
        """
        return FP(f"{self._idx_}", FPSort(11,53))

    def _apply_constraints_(self, solver : Optimize) -> None:
        """
        Apply the constraints to the solver.

        :param solver: The optimization solver to apply the constraints to.
        :type solver: Optimize
        :param add_randomization: Add constraints for randomization
        :type add_randomization: bool
        """

        Var._apply_constraints_(self, solver)

        bv = BitVec(f"{self._idx_}", self.width)
        fp = FP64

        for b in range(self.width):
            solver.add_soft(Extract(b,b,bv) == random.randint(0,1), weight=100)

        solver.add(Not(fpIsNaN(self._rand_)))
        solver.add(Not(fpIsInf(self._rand_)))
        solver.add(self._rand_ == fpBVToFP(bv, fp))

Half = Fp16
Float = Fp32
Double = Fp64

__all__ = ["Fp16", "Fp32", "Fp64", "Half", "Float", "Double"]
