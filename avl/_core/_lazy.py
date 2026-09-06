# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library deferred imports

"""Deferred imports for AVL's heavyweight third party dependencies.

``import avl`` happens on every simulation start-up, but most of AVL's
dependencies are only needed by a subset of its features - pandas and tabulate
for reporting, z3 and numpy for randomization, bincopy for memory image I/O,
graphviz for diagrams.  Importing them eagerly costs several hundred
milliseconds on every run, whether or not the testbench uses them.

:func:`lazy_import` returns a stand-in module that imports the real module the
first time an attribute is read from it, so the cost is only paid by testbenches
that actually use the feature.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any


class LazyModule(ModuleType):
    """A module stand-in that imports the real module on first attribute access."""

    def __init__(self, name: str) -> None:
        """
        :param name: The fully qualified name of the module to import on demand.
        :type name: str
        """
        super().__init__(name)
        self.__dict__["_module_"] = None

    def _resolve_(self) -> ModuleType:
        """
        Import the real module, caching it for subsequent accesses.

        :return: The imported module.
        :rtype: ModuleType
        """
        module = self.__dict__["_module_"]
        if module is None:
            module = importlib.import_module(self.__name__)
            self.__dict__["_module_"] = module
        return module

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._resolve_(), name)
        # Cache on the stand-in itself. __getattr__ is only consulted when the
        # normal lookup fails, so every subsequent use of this attribute costs
        # an ordinary dictionary lookup rather than a call into here.
        self.__dict__[name] = value
        return value

    def __dir__(self) -> list[str]:
        return dir(self._resolve_())

    def __repr__(self) -> str:
        state = "loaded" if self.__dict__["_module_"] is not None else "deferred"
        return f"<lazy module {self.__name__!r} ({state})>"


def lazy_import(name: str) -> Any:
    """
    Defer importing ``name`` until one of its attributes is used.

    Only attribute access is supported, so ``from z3 import BitVec`` style
    imports must be rewritten as ``z3.BitVec``.

    :param name: The fully qualified name of the module to import on demand.
    :type name: str
    :return: A stand-in for the module.
    :rtype: ModuleType
    """
    return LazyModule(name)


__all__ = ["LazyModule", "lazy_import"]
