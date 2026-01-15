# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Variable Class

from __future__ import annotations

from collections.abc import Callable
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

    def _cast_(self, other: Any) -> int:
        """
        Cast the value to the appropriate type based on the width of the variable.

        :param other: The value to be cast.
        :type other: Any
        :return: The casted value.
        :rtype: int
        """
        v = other.value if isinstance(other, Var) else other
        (_min_, _) = self._range_()

        return int((v - _min_) % (1 << self.width)) + _min_

    def _range_(self) -> tuple[int, int]:
        """
        Get the range of values that can be represented by this variable.

        :return: A tuple containing the minimum and maximum values.
        :rtype: tuple[int, int]
        """
        return (-(1 << (self.width - 1)), (1 << (self.width - 1)) - 1)

class Int8(Int):
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
