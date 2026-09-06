# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class

from __future__ import annotations

from typing import Any

from .logic import Logic


class Uint(Logic):
    _default_fmt_ = str
    """Unsigned values print as decimal rather than the hexadecimal that
    ``Logic`` uses.
    """

    def __copy__(self):
        """
        Copy the Logic - always make a copy to ensure randomness is preserved.

        :return: Copied Var.
        :rtype: Var
        """
        new_obj = Uint(self.value, auto_random=self._auto_random_, fmt=self._fmt_, width=self.width)
        new_obj._constraints_ = {
            k: v.copy() for k, v in self._constraints_.items()
        }
        new_obj.__class__ = self.__class__
        return  new_obj

class Uint8(Uint):
    width = 8
    """Width in bits. Declared here so that constructing one costs no
    per-instance width attribute.
    """

    _mask_ = (1 << 8) - 1
    """Mask of 8 set bits, applied when a value is assigned."""

    _fixed_width_ = True
    """The width is part of the type, so a caller may not override it."""

    def _wrap_(self, result : Any) -> Uint8:
        """
        Wrap the result in an Logic instance.

        :param result: The result to be wrapped.
        :type result: Any
        :return: An instance of Logic with the result.
        :rtype: Logic
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_)

class Uint16(Uint):
    width = 16
    """Width in bits. Declared here so that constructing one costs no
    per-instance width attribute.
    """

    _mask_ = (1 << 16) - 1
    """Mask of 16 set bits, applied when a value is assigned."""

    _fixed_width_ = True
    """The width is part of the type, so a caller may not override it."""

    def _wrap_(self, result : Any) -> Uint16:
        """
        Wrap the result in an Logic instance.

        :param result: The result to be wrapped.
        :type result: Any
        :return: An instance of Logic with the result.
        :rtype: Logic
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_)

class Uint32(Uint):
    width = 32
    """Width in bits. Declared here so that constructing one costs no
    per-instance width attribute.
    """

    _mask_ = (1 << 32) - 1
    """Mask of 32 set bits, applied when a value is assigned."""

    _fixed_width_ = True
    """The width is part of the type, so a caller may not override it."""

    def _wrap_(self, result : Any) -> Uint32:
        """
        Wrap the result in an Logic instance.

        :param result: The result to be wrapped.
        :type result: Any
        :return: An instance of Logic with the result.
        :rtype: Logic
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_)

class Uint64(Uint):
    width = 64
    """Width in bits. Declared here so that constructing one costs no
    per-instance width attribute.
    """

    _mask_ = (1 << 64) - 1
    """Mask of 64 set bits, applied when a value is assigned."""

    _fixed_width_ = True
    """The width is part of the type, so a caller may not override it."""

    def _wrap_(self, result : Any) -> Uint64:
        """
        Wrap the result in an Logic instance.

        :param result: The result to be wrapped.
        :type result: Any
        :return: An instance of Logic with the result.
        :rtype: Logic
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_)

__all__ = ["Uint", "Uint8", "Uint16", "Uint32", "Uint64"]
