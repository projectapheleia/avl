# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .logic import Logic


class Uint(Logic):

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

    def __init__(
        self,
        *args,
        auto_random: bool = True,
        fmt: Callable[..., str] = str,
        width: int = 32
    ) -> None:
        """
        Initialize an instance of the class.

        :param value: The value to be assigned to the instance.
        :type value: int
        :param auto_random: Flag to enable automatic randomization, defaults to True.
        :type auto_random: bool, optional
        :param fmt: The format to be used, defaults to str.
        :type fmt: function, optional
        :param width: The width of the variable in bits, defaults to 32.
        :type width: int, optional
        :raises ValueError: If the width is not a positive integer.
        """
        super().__init__(*args, auto_random=auto_random, fmt=fmt, width=width)

class Uint8(Uint):
    def __init__(
        self, *args, auto_random: bool = True, fmt: Callable[..., str] = str
    ) -> None:
        """
        Initialize an instance of the class.

        :param value: The value to be assigned to the instance.
        :type value: int
        :param auto_random: Flag to enable automatic randomization, defaults to True.
        :type auto_random: bool, optional
        :param fmt: The format to be used, defaults to str.
        :type fmt: function, optional
        """
        super().__init__(*args, auto_random=auto_random, fmt=fmt, width=8)

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
    def __init__(
        self, *args, auto_random: bool = True, fmt: Callable[..., str] = str
    ) -> None:
        """
        Initialize an instance of the class.

        :param value: The value to be assigned to the instance.
        :type value: int
        :param auto_random: Flag to enable automatic randomization, defaults to True.
        :type auto_random: bool, optional
        :param fmt: The format to be used, defaults to str.
        :type fmt: function, optional
        """
        super().__init__(*args, auto_random=auto_random, fmt=fmt, width=16)

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
    def __init__(
        self, *args, auto_random: bool = True, fmt: Callable[..., str] = str
    ) -> None:
        """
        Initialize an instance of the class.

        :param value: The value to be assigned to the instance.
        :type value: int
        :param auto_random: Flag to enable automatic randomization, defaults to True.
        :type auto_random: bool, optional
        :param fmt: The format to be used, defaults to str.
        :type fmt: function, optional
        """
        super().__init__(*args, auto_random=auto_random, fmt=fmt, width=32)

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
    def __init__(
        self, *args, auto_random: bool = True, fmt: Callable[..., str] = str
    ) -> None:
        """
        Initialize an instance of the class.

        :param value: The value to be assigned to the instance.
        :type value: int
        :param auto_random: Flag to enable automatic randomization, defaults to True.
        :type auto_random: bool, optional
        :param fmt: The format to be used, defaults to str.
        :type fmt: function, optional
        """
        super().__init__(*args, auto_random=auto_random, fmt=fmt, width=64)

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
