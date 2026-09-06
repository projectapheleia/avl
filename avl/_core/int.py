# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class

from __future__ import annotations

from typing import Any

from .uint import Uint
from .var import Var


class Int(Uint):
    def __copy__(self):
        """
        Copy the Logic - always make a copy to ensure randomness is preserved.

        :return: Copied Var.
        :rtype: Var
        """
        new_obj = Int(self.value, auto_random=self._auto_random_, fmt=self._fmt_, width=self.width)
        new_obj._constraints_ = {
            k: v.copy() for k, v in self._constraints_.items()
        }
        new_obj.__class__ = self.__class__
        return  new_obj

    def _cast_(self, other: Any) -> int:
        """
        Cast the value to the appropriate type based on the width of the variable.

        :param other: The value to be cast.
        :type other: Any
        :return: The casted value.
        :rtype: int
        """
        v = other.value if isinstance(other, Var) else other
        mask = self._mask_
        minimum = -(mask >> 1) - 1

        return int((v - minimum) % (mask + 1)) + minimum

    def _range_(self) -> tuple[int, int]:
        """
        Get the range of values that can be represented by this variable.

        :return: A tuple containing the minimum and maximum values.
        :rtype: tuple[int, int]
        """
        half = self._mask_ >> 1
        return (-half - 1, half)

class Int8(Int):
    width = 8
    """Width in bits. Declared here so that constructing one costs no
    per-instance width attribute.
    """

    _mask_ = (1 << 8) - 1
    """Mask of 8 set bits, applied when a value is assigned."""

    _fixed_width_ = True
    """The width is part of the type, so a caller may not override it."""

    def _wrap_(self, result : Any) -> Int8:
        """
        Wrap the result in an avl_logic instance.

        :param result: The result to be wrapped.
        :type result: Any
        :return: An instance of avl_logic with the result.
        :rtype: avl_logic
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_)

class Int16(Int):
    width = 16
    """Width in bits. Declared here so that constructing one costs no
    per-instance width attribute.
    """

    _mask_ = (1 << 16) - 1
    """Mask of 16 set bits, applied when a value is assigned."""

    _fixed_width_ = True
    """The width is part of the type, so a caller may not override it."""

    def _wrap_(self, result : Any) -> Int16:
        """
        Wrap the result in an avl_logic instance.

        :param result: The result to be wrapped.
        :type result: Any
        :return: An instance of avl_logic with the result.
        :rtype: avl_logic
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_)

class Int32(Int):
    width = 32
    """Width in bits. Declared here so that constructing one costs no
    per-instance width attribute.
    """

    _mask_ = (1 << 32) - 1
    """Mask of 32 set bits, applied when a value is assigned."""

    _fixed_width_ = True
    """The width is part of the type, so a caller may not override it."""

    def _wrap_(self, result : Any) -> Int32:
        """
        Wrap the result in an avl_logic instance.

        :param result: The result to be wrapped.
        :type result: Any
        :return: An instance of avl_logic with the result.
        :rtype: avl_logic
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_)

class Int64(Int):
    width = 64
    """Width in bits. Declared here so that constructing one costs no
    per-instance width attribute.
    """

    _mask_ = (1 << 64) - 1
    """Mask of 64 set bits, applied when a value is assigned."""

    _fixed_width_ = True
    """The width is part of the type, so a caller may not override it."""

    def _wrap_(self, result : Any) -> Int64:
        """
        Wrap the result in an avl_logic instance.

        :param result: The result to be wrapped.
        :type result: Any
        :return: An instance of avl_logic with the result.
        :rtype: avl_logic
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_)

Byte = Int8

__all__ = ["Int", "Int8", "Int16", "Int32", "Int64", "Byte"]
