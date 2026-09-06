# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class

from __future__ import annotations

import random
import struct
import warnings
from functools import cache
from typing import Any

from ._lazy import lazy_import
from .var import Var

np = lazy_import("numpy")
z3 = lazy_import("z3")


@cache
def _fp_sort_(ebits: int, sbits: int) -> Any:
    """
    Return the Z3 floating point sort with the given exponent and significand widths.

    Built on first use, so that importing avl does not import z3.

    :param ebits: Number of exponent bits.
    :type ebits: int
    :param sbits: Number of significand bits.
    :type sbits: int
    :return: The Z3 FP sort.
    :rtype: z3.FPSortRef
    """
    return z3.FPSort(ebits, sbits)


@cache
def _np_type_(name: str) -> Any:
    """
    Return a numpy scalar type by name.

    Resolved on first use and cached, so that defining these classes costs
    nothing and does not import numpy.

    :param name: The numpy scalar type name, for example "float32".
    :type name: str
    :return: The numpy scalar type.
    :rtype: type
    """
    return getattr(np, name)

class Fp16(Var):
    """Half precision floating point variable."""

    # Everything that is fixed for the type lives on the class, so constructing
    # a variable stores only its value.

    width = 16
    """Width of the variable in bits."""

    _value_dtype_ = "float16"
    """Name of the numpy scalar type values are held as. Held as a name so that
    defining the class does not import numpy; ``_np_type_`` resolves it.
    """

    _bits_dtype_ = "uint16"
    """Name of the numpy integer type of the same width, used by ``to_bits``
    and ``from_bits``.
    """

    _bits_format_ = "H"
    """``struct`` format code of the same width, used to unpack a Z3 bit vector
    back into a float during randomization.
    """

    _max_ = 65504.0
    """Largest representable magnitude. A cast only has to suppress numpy's
    overflow warning when the value falls outside it.
    """

    _fp_ebits_ = 5
    """Exponent bits of the Z3 floating point sort."""

    _fp_sbits_ = 11
    """Significand bits of the Z3 floating point sort."""

    _bit_clause_cache_ = None
    """Randomization clauses over the IEEE bit pattern, keyed and armed as in
    ``Logic._bit_clause_cache_``.
    """

    def _cast_(self, other: Any) -> Any:
        """
        Cast the other value to the type of this variable's value.

        :param other: The value to cast.
        :type other: Any
        :return: The casted value.
        :rtype: Any
        """
        v = other.value if isinstance(other, type(self)) else other
        cast = _np_type_(self._value_dtype_)

        if isinstance(v, int | float | np.number):
            # numpy only warns when the value does not fit the target type, so
            # only pay for suppressing that warning when it can actually happen.
            if -self._max_ <= v <= self._max_:
                return cast(v)
        elif isinstance(v, z3.BitVecNumRef):
            # Z3 hands back a bit vector during randomization.
            return np.frombuffer(struct.pack(self._bits_format_, v.as_long()), dtype=cast)[0]

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning, message="overflow encountered in cast")
            return cast(v)

    def _range_(self) -> tuple[float, float]:
        """
        Get the range of values that can be represented by this variable.

        :return: A tuple containing the minimum and maximum values.
        :rtype: tuple[int, int]
        """
        return (-self._max_, self._max_)

    def _z3_(self) -> z3.FP:
        """
        Get the Z3 representation of the variable.

        :return: The Z3 FP representation of the variable.
        :rtype: FP
        """
        return z3.FP(f"{self._idx_}", _fp_sort_(self._fp_ebits_, self._fp_sbits_))

    def _z3_bits_(self) -> z3.BitVecRef:
        """
        The Z3 bit vector holding this variable's IEEE bit pattern.

        Randomization draws over the bit pattern rather than over the float.

        :return: The bit vector.
        :rtype: z3.BitVecRef
        """
        return z3.BitVec(f"{self._idx_}", self.width)

    def _apply_constraints_(self, solver : z3.Optimize) -> None:
        """
        Apply the constraints to the solver.

        Ties the float to the bit vector holding its IEEE pattern and rules out
        NaN and the infinities. Randomization is applied separately, by
        _apply_randomization_, which draws over that same bit vector.

        :param solver: The optimization solver to apply the constraints to.
        :type solver: Optimize
        :param add_randomization: Add constraints for randomization
        :type add_randomization: bool
        """

        Var._apply_constraints_(self, solver)

        bits = self._z3_bits_()
        solver.add(z3.Not(z3.fpIsNaN(self._rand_)))
        solver.add(z3.Not(z3.fpIsInf(self._rand_)))
        solver.add(self._rand_ == z3.fpBVToFP(bits, _fp_sort_(self._fp_ebits_, self._fp_sbits_)))

    def _apply_randomization_(self, solver : z3.Optimize,
                              free_bits : list[int]|None = None) -> None:
        """
        Add the soft constraints that spread this variable over its legal values.

        The draw is made over the IEEE bit pattern rather than over the float.
        Object._free_bits_ examines only variables whose Z3 representation is a bit
        vector, and this one's is a float, so nothing is worked out for it and every
        bit gets asked about.

        :param solver: The optimization solver to apply the constraints to.
        :type solver: Optimize
        :param free_bits: Always None here, see above.
        :type free_bits: list[int], optional
        """
        bits = self._z3_bits_()

        # One draw for the whole variable. A randint per bit costs an order of
        # magnitude more for exactly the same randomness.
        drawn = random.getrandbits(self.width)
        clauses = self._bit_clause_cache_
        positions = range(self.width) if free_bits is None else free_bits

        if clauses is None:
            # First randomization of this variable. Build the clauses without
            # keeping them, and arm the cache for a second one.
            self._bit_clause_cache_ = {}
            for b in positions:
                solver.add_soft(z3.Extract(b, b, bits) == ((drawn >> b) & 1), weight=100)
            return

        for b in positions:
            value = (drawn >> b) & 1
            key = b << 1 | value
            clause = clauses.get(key)
            if clause is None:
                clause = clauses[key] = z3.Extract(b, b, bits) == value
            solver.add_soft(clause, weight=100)

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
        return int(self.value.view(_np_type_(self._bits_dtype_)))

    def from_bits(self, raw: int) -> None:
        """
        Convert the raw representation back to a float.

        :param raw: The raw value.
        :type raw: int
        """
        self.value = _np_type_(self._bits_dtype_)(int(raw)).view(type(self.value))

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
    """Single precision floating point variable."""

    width = 32
    """Width of the variable in bits."""

    _value_dtype_ = "float32"
    """Name of the numpy scalar type values are held as."""

    _bits_dtype_ = "uint32"
    """Name of the numpy integer type of the same width."""

    _bits_format_ = "I"
    """``struct`` format code of the same width."""

    _max_ = 3.4028234663852886e+38
    """Largest representable magnitude."""

    _fp_ebits_ = 8
    """Exponent bits of the Z3 floating point sort."""

    _fp_sbits_ = 24
    """Significand bits of the Z3 floating point sort."""


class Fp64(Fp16):
    """Double precision floating point variable."""

    width = 64
    """Width of the variable in bits."""

    _value_dtype_ = "float64"
    """Name of the numpy scalar type values are held as."""

    _bits_dtype_ = "uint64"
    """Name of the numpy integer type of the same width."""

    _bits_format_ = "Q"
    """``struct`` format code of the same width."""

    _max_ = 1.7976931348623157e+308
    """Largest representable magnitude."""

    _fp_ebits_ = 11
    """Exponent bits of the Z3 floating point sort."""

    _fp_sbits_ = 53
    """Significand bits of the Z3 floating point sort."""

    def _range_(self) -> tuple[float, float]:
        """
        Get the range of values that can be represented by this variable.

        :return: A tuple containing the minimum and maximum values.
        :rtype: tuple[float, float]
        """
        return (-1e100, 1e100) # Reduced to allow randomization


Half = Fp16
Float = Fp32
Double = Fp64

__all__ = ["Fp16", "Fp32", "Fp64", "Half", "Float", "Double"]
