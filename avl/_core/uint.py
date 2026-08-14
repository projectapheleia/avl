# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .logic import Logic


class Uint(Logic):

    # Prints as str, where Logic prints as hex. See Var.__init__ for why a level
    # of this hierarchy contributes class attributes rather than a constructor.
    _fmt_default_ = str

    def __copy__(self):
        """
        Copy the Logic - always make a copy to ensure randomness is preserved.

        :return: Copied Var.
        :rtype: Var
        """
        new_obj = Uint(self.value, auto_random=self._auto_random_, fmt=self._fmt_, width=self.width)
        new_obj._constraints_ = self._copied_constraints_()
        new_obj.__class__ = self.__class__
        return  new_obj

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
