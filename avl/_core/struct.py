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
        Calls the to_bits_w_width function and only returns the value.

        :return: An integer representing the combined bit value of the Struct.
        """
        value, width = self.to_bits_w_width()
        return int(value)

    def to_bits_w_width(self) -> tuple[int, int]:
        """
        Convert the Struct instance to a bit representation.
        This method combines the values of all fields into a single integer,
        where each field's value is shifted according to its width.

        :return: An a tupple of integers representing the combined bit
        value of the Struct, plus the size of it.
        """
        value = 0
        offset = 0
        for name, _ in reversed(self._fields_):
            v = getattr(self, name)
            #check if this field (v) is also a struct, if yes, call this function recursively
            if hasattr(v, 'value'):
                value |= (v.value << offset)
                offset += v.width
            else:
                aux_value, aux_width = (v.to_bits_w_width())
                value |= (aux_value << offset)
                offset += aux_width
        return int(value), int(offset)


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

    def from_bits(self, value : int) -> int:
        """
        Populate the Struct instance from a bit representation.
        This method takes an integer value and assigns each field's value
        based on its width, effectively reconstructing the Struct from its bit representation.

        :param value: An integer representing the combined bit value of the Struct.

        :return: Bits that remains after setting all values to the struct fields
        """
        if hasattr(value, "value"):
            _value = int(value.value)
        else:
            _value = int(value)
        for name, _ in reversed(self._fields_):
            v = getattr(self, name)
            #check if this field (v) is also a struct, if yes, call this function recursively
            if hasattr(v, 'value'):
                v.value = _value & ((1 << v.width) - 1)
                _value >>= v.width
            else:
                _value = v.from_bits(_value)
        return int(_value)

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

    @property
    def width(self) -> int:
        """
        Calculate the total width of the Struct instance.
        This property sums the widths of all fields to determine the overall width.

        :return: The total width of the Struct instance.
        """
        total_width = 0
        for name, _ in self._fields_:
            v = getattr(self, name)
            total_width += v.width
        return total_width

    def __getitem__(self, key):
        """
        Get a slice or single bit from the Struct instance.
        This method allows for slicing or indexing the Struct instance to
        retrieve specific bits or ranges of bits.

        :param key: A slice or integer index to specify the bits to retrieve.
        :return: The value of the specified bits.
        """
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
        """
        Set a slice or single bit in the Struct instance.
        This method allows for slicing or indexing the Struct instance to
        set specific bits or ranges of bits.

        :param key: A slice or integer index to specify the bits to set.
        :param value: The value to set for the specified bits.
        """
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

__all__ = ["Struct"]
