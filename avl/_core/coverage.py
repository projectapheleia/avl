# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Coverage Container

from __future__ import annotations

import atexit
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from .covergroup import Covergroup

class Coverage:
    _instance = None

    def __new__(cls) -> Coverage:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """
        Initialize the coverage container
        This method initializes the coverage container and registers the exit handler
        to export coverage data when the program exits.
        It checks if the `_cg_` attribute exists; if not, it initializes it as an empty list.
        If the `_cg_` attribute already exists, it does nothing to avoid re-initialization.
        """
        if hasattr(self, "_cg_"):
            return

        # Cover Groups
        self._cg_ = []

        # Register function to export coverage at exit
        atexit.register(self.__at_exit__)

    def __at_exit__(self) -> None:
        """
        Export coverage data at exit
        """
        if len(self._cg_) == 0:
            return

        df = self._cg_[0].report(full=True)
        for cg in self._cg_[1:]:
            df = pd.concat([df, cg.report(full=True)], ignore_index=True)

        df.to_json("coverage.json", mode="w", orient="records")

    def add_covergroup(self, cg: Covergroup) -> None:
        """
        Add a covergroup to the coverage container

        :param cg: The covergroup to add
        """
        self._cg_.append(cg)

    def remove_covergroup(self, cg: Covergroup) -> None:
        """
        Remove a covergroup from the coverage container

        :param cg: The covergroup to remove
        """
        self._cg_.remove(cg)


__all__ = ["Coverage"]
