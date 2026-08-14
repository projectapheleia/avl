# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class


from __future__ import annotations

import random
from typing import Any

from z3 import BitVec, BitVecRef, Extract, Optimize

from .var import Var


class Logic(Var):

    # Width, and the mask derived from it, for a Logic given no width of its own.
    # The two must always agree - see Var.__init__, which is where an explicit
    # width sets both. Logic defines no __init__ of its own, so that building one
    # costs a single constructor frame; the class attributes are what a level of
    # the hierarchy contributes instead.
    width = 32
    _mask_ = (1 << 32) - 1

    # Logic prints as hex where Var prints as str.
    _fmt_default_ = hex

    # (pooled z3 variable's AST id, bit, value) -> the clause asking that bit to
    # take that value. Building these was around a third of the cost of
    # randomizing a wide object; pooling them alongside the z3 variables makes
    # them reusable by the next object of the same shape. The pooled variables
    # are held for the life of the process by Var._z3_pool_, so an AST id cannot
    # be recycled underneath a key.
    _bit_clause_pool_: dict = {}

    def __copy__(self):
        """
        Copy the Logic - always make a copy to ensure randomness is preserved.

        :return: Copied Var.
        :rtype: Var
        """
        new_obj = Logic(self.value, auto_random=self._auto_random_, fmt=self._fmt_, width=self.width)
        new_obj._constraints_ = self._copied_constraints_()
        return  new_obj

    def _cast_(self, other: Any) -> int:
        """
        Cast the value to the appropriate type based on the width of the variable.

        :param other: The value to be cast.
        :type other: Any
        :return: The casted value.
        :rtype: int
        """
        v = other.value if isinstance(other, Logic) else other
        # Against the kept mask rather than _range_(), which would rebuild it on
        # every assignment.
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

    def _z3_name_(self, ordinal : int) -> str:
        """
        The pooled name for a variable at this position in a solve.

        The width is what makes a bit vector's sort, and one Logic class covers
        every width, so the name carries the width rather than the class name.

        :param ordinal: Position of the variable within the randomization.
        :type ordinal: int
        :return: The name.
        :rtype: str
        """
        return f"v{ordinal}_l{self.width}"

    def _z3_(self, name : str) -> BitVecRef:
        """
        Get the Z3 representation of the variable.

        :param name: Pooled name to give it - see Var._z3_name_.
        :type name: str
        :return: The Z3 BitVec representation of the variable.
        :rtype: z3.BitVecRef
        """
        return Var._pooled_z3_(name, lambda: BitVec(name, self.width))

    def _apply_randomization_(self, solver : Optimize, free_bits : list[int]|None = None,
                              record : list|None = None) -> None:
        """
        Add the soft constraints that spread this variable over its legal values.

        Each bit is asked, softly, to match a random draw. The solver satisfies as
        many of those as the hard constraints allow, and that is what spreads the
        result, rather than returning whichever legal value the solver finds first.

        :param solver: The optimization solver to apply the constraints to.
        :type solver: Optimize
        :param free_bits: The bits to constrain. None means every bit. A bit the
            hard constraints pin to a single value is not worth one - see
            Object._free_bits_ - and nor is one they will not grant alongside the
            rest - see Object._clause_plan_.
        :type free_bits: list[int], optional
        :param record: When given, the (bit, value) pairs asked for are appended to
            it, so the clause plan can be settled against what the solver grants.
        :type record: list, optional
        """
        # All the bits come from a single getrandbits call - one randint per bit
        # is an order of magnitude more expensive for no extra randomness.
        bits = random.getrandbits(self.width)
        pool = Logic._bit_clause_pool_
        rand_id = self._rand_.get_id()
        for b in (range(self.width) if free_bits is None else free_bits):
            value = (bits >> b) & 1
            clause = pool.get((rand_id, b, value))
            if clause is None:
                clause = Extract(b, b, self._rand_) == value
                pool[(rand_id, b, value)] = clause
            solver.add_soft(clause, weight=100)
            if record is not None:
                record.append((b, value))

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
