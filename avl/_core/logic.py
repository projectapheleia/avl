# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class


from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from ._lazy import lazy_import
from .var import Var

z3 = lazy_import("z3")


class Logic(Var):

    width = 32
    """Width of the variable in bits. Fixed per class for every sized subclass
    (``Uint8``, ``Int32``, ``Bool``, ...), and only copied onto an instance
    when a caller asks for a different width.
    """

    _mask_ = (1 << 32) - 1
    """Mask of :attr:`width` set bits, applied when a value is assigned. Held
    beside the width so that casting never has to recompute it.
    """

    _default_fmt_ = hex
    """Logic values print as hexadecimal unless the caller supplies a format."""

    _fixed_width_ = False
    """True on subclasses whose width is part of the type and may not be
    overridden by the caller.
    """

    _bit_clause_cache_ = None
    """Randomization clauses, keyed by bit and value as ``bit << 1 | value``.

    Only two clauses exist per bit and neither depends on anything that changes
    between randomizations, so a variable randomized repeatedly builds each of
    them once. None until the variable has been randomized once: a variable
    randomized a single time, as a fresh sequence item is, would otherwise pay to
    fill a cache nothing ever reads. Held per variable rather than globally, so
    that the clauses are released with it.
    """

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
        fmt: Callable[..., str] | None = None,
        width: int | None = None
    ) -> None:
        """
        Initialize an instance of the class.

        :param value: The initial value of the variable.
        :type value: any
        :param auto_random: Indicates if the variable should be automatically randomized, defaults to True.
        :type auto_random: bool, optional
        :param fmt: The format of the variable, defaults to the class format.
        :type fmt: type, optional
        :param width: The width of the variable in bits, defaults to the class width.
        :type width: int, optional
        :raises ValueError: If the width is not a positive integer.
        """
        if width is not None:
            if self._fixed_width_:
                raise TypeError(f"{type(self).__name__} has a fixed width of {self.width}")
            if not isinstance(width, int) or width <= 0:
                raise ValueError("Width must be a positive integer.")
            if width != self.width:
                self.width = width
                self._mask_ = (1 << width) - 1

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
        return int(v) & self._mask_

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
        return (0, self._mask_)

    def _z3_(self) -> z3.BitVecRef:
        """
        Get the Z3 representation of the variable.

        :return: The Z3 BitVec representation of the variable.
        :rtype: z3.BitVecRef
        """
        return z3.BitVec(f"{self._idx_}", self.width)

    def _apply_randomization_(self, solver : z3.Optimize,
                              free_bits : list[int]|None = None) -> None:
        """
        Add the soft constraints that spread this variable over its legal values.

        Each bit is asked, softly, to match a random draw. The solver satisfies as
        many of those as the hard constraints allow, and that is what spreads the
        result rather than returning whichever legal value it finds first.

        :param solver: The optimization solver to apply the constraints to.
        :type solver: Optimize
        :param free_bits: The bits worth asking about. None means every bit. A bit
            the hard constraints pin to a single value is not worth one - see
            Object._free_bits_.
        :type free_bits: list[int], optional
        """
        # One draw for the whole variable. A randint per bit costs an order of
        # magnitude more for exactly the same randomness.
        drawn = random.getrandbits(self.width)
        clauses = self._bit_clause_cache_
        rand = self._rand_
        bits = range(self.width) if free_bits is None else free_bits

        if clauses is None:
            # First randomization of this variable. Build the clauses without
            # keeping them, and arm the cache for a second one.
            self._bit_clause_cache_ = {}
            for b in bits:
                solver.add_soft(z3.Extract(b, b, rand) == ((drawn >> b) & 1), weight=100)
            return

        for b in bits:
            value = (drawn >> b) & 1
            key = b << 1 | value
            clause = clauses.get(key)
            if clause is None:
                clause = clauses[key] = z3.Extract(b, b, rand) == value
            solver.add_soft(clause, weight=100)

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
