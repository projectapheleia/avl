# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class

from collections.abc import Callable
from typing import Any

from .logic import Logic


class Bool(Logic):
    def __init__(self, *args, auto_random: bool = True, fmt : Callable[..., str] = str) -> None:
        """
        Initialize an instance of the Bool class.

        :param value: The initial value of the instance.
        :type value: bool
        :param auto_random: Flag indicating whether the instance should be automatically randomized, defaults to True.
        :type auto_random: bool, optional
        """
        super().__init__(*args, auto_random=auto_random, fmt=fmt, width=1)

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
