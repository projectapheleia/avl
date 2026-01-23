# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Struct Class

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any

from cocotb.handle import HierarchyObject


class _StructMeta_(type):
    def __new__(mcs, name, bases, namespace):
        """
        Custom metaclass to automatically collect field annotations
        and create a `_fields_` attribute for the Struct class.
        """
        cls = super().__new__(mcs, name, bases, namespace)
        cls._fields_ = list(cls.__annotations__.items())
        return cls

class Struct(metaclass=_StructMeta_):

    def __copy__(self) -> Struct:
        """
        Create a shallow copy of the Struct instance.
        This method creates a new instance of the Struct class and copies
        each field's value from the original instance to the new instance.

        Ensures all Vars are new instances and not references to the original Vars.

        :return: A new Struct instance with copied fields.
        """
        new_struct = type(self)()
        for name, _ in self._fields_:
            obj = getattr(self, name)
            v = copy.copy(obj)
            setattr(new_struct, name, v)
        return new_struct

    def __deepcopy__(self, memo) -> Struct:
        """
        Create a deep copy of the Struct instance.
        This method creates a new instance of the Struct class and recursively
        copies each field's value from the original instance to the new instance.

        :param memo: A dictionary to keep track of already copied objects to avoid infinite recursion.
        :return: A new Struct instance with deep copied fields.
        """
        new_obj = self.__copy__()
        memo[id(self)] = new_obj
        return new_obj

    def __iter__(self) -> Iterator[Any]:
        """
        Iterate over the fields of the Struct instance.
        This method yields each field's value in the order they are defined.
        """
        for name, _ in self._fields_:
            yield getattr(self, name)

    def __repr__(self) -> str:
        """
        Return a string representation of the Struct instance.
        This method constructs a string that includes the class name and
        each field's name and value in the format `name=value`.

        :return: A string representation of the Struct instance.
        """
        field_strs = [f"{name}={getattr(self, name)!r}" for name, _ in self._fields_]
        return f"{self.__class__.__name__}({', '.join(field_strs)})"

    def __str__(self) -> str:
        """
        Return a string representation of the Struct instance.
        This method is an alias for `__repr__`, providing a consistent
        string representation.

        :return: A string representation of the Struct instance.
        """
        return self.__repr__()

    def to_bits(self) -> int:
        """
        Convert the Struct instance to a bit representation.
        This method combines the values of all fields into a single integer,
        where each field's value is shifted according to its width.

        :return: An integer representing the combined bit value of the Struct.
        """
        value = 0
        offset = 0
        for name, _ in reversed(self._fields_):
            v = getattr(self, name)
            value |= (v.value << offset)
            offset += v.width
        return int(value)

    def to_hdl(self, hdl : HierarchyObject) -> None:
        """
        Populate the Struct instance from a HierarchyObject.
        This method assigns each field's value based on the corresponding
        attribute in the HierarchyObject.

        :param hdl: A HierarchyObject from which to populate the Struct fields.
        :return: None
        """

        if hasattr(hdl, "value"):
            hdl.value = self.to_bits()
        else:
            for name, _ in self._fields_:
                s = getattr(self, name)
                h = getattr(hdl, name, None)
                if h is not None:
                    h.value = s.value

    def from_bits(self, value : int) -> None:
        """
        Populate the Struct instance from a bit representation.
        This method takes an integer value and assigns each field's value
        based on its width, effectively reconstructing the Struct from its bit representation.

        :param value: An integer representing the combined bit value of the Struct.

        :return: None
        """
        if hasattr(value, "value"):
            _value = int(value.value)
        else:
            _value = int(value)
        for name, _ in reversed(self._fields_):
            v = getattr(self, name)
            v.value = _value & ((1 << v.width) - 1)
            _value >>= v.width

    def from_hdl(self, hdl : HierarchyObject) -> None:
        """
        Populate the Struct instance from a HierarchyObject.
        This method assigns each field's value based on the corresponding
        attribute in the HierarchyObject.

        :param hdl: A HierarchyObject from which to populate the Struct fields.
        :return: None
        """
        if hasattr(hdl, "value"):
            self.from_bits(hdl.value)
        else:
            for name, _ in self._fields_:
                s = getattr(self, name)
                h = getattr(hdl, name, None)
                if h is not None:
                    s.value = h.value

    @property
    def value(self):
        """
        Property to abstract the value and ensure it's always cast when assigned
        """
        return self.to_bits()

    @value.setter
    def value(self, v):
        """
        Setter property to enforce wraps etc. when assigned directly

        :param v: The Value to assig
        :type v : Andy
        """
        self.from_bits(v)

__all__ = ["Struct"]
