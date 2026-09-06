# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class

from typing import Any

from .logic import Logic


class Bool(Logic):
    width = 1
    """Width in bits. A boolean is a single bit."""

    _mask_ = 1
    """Mask of one set bit, applied when a value is assigned."""

    _fixed_width_ = True
    """The width is part of the type, so a caller may not override it."""

    _default_fmt_ = str
    """Booleans print as ``True``/``False`` rather than hexadecimal."""

    def _cast_(self, other: Any) -> int:
        """
        Cast the value to the appropriate type based on the width of the variable.

        :param other: The value to be cast.
        :type other: Any
        :return: The casted value.
        :rtype: bool
        """
        return bool(super()._cast_(other))

    def _wrap_(self, result : Any) -> Logic:
        """
        Wrap the result in an Logic instance.

        :param result: The result to be wrapped.
        :type result: Any
        :return: An instance of Logic with the result.
        :rtype: Logic
        """
        return type(self)(result, auto_random=self._auto_random_, fmt=self._fmt_)

__all__ = ["Bool"]
