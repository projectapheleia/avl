# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Trace

import os
from collections.abc import MutableMapping, MutableSequence

import cocotb
import cocotb.utils
import pandas as pd

from .component import Component
from .factory import Factory
from .list import List


class Trace(Component):
    def __init__(self, name: str, parent: Component) -> None:
        """
        Initialize the AVL model component.

        :param name: Name of the model.
        :type name: str
        :param parent: Parent component of the model.
        :type parent: Component
        """
        super().__init__(name, parent)
        self.item_port = List()

        # Interval to flush trace data to file
        self.flush_interval = Factory.get_variable(f"{self.get_full_name()}.flush_interval", 100)

        # Trace name
        self.tracefile = Factory.get_variable(f"{self.get_full_name()}.tracefile", f"{self.get_full_name()}.csv")

        # Delete old trace file if it exists
        if os.path.exists(self.tracefile):
            os.remove(self.tracefile)

        # User defined columns for trace data
        # If None, all public attributes of item will be used
        self.columns: list[str]|None = None

        # Pandas DataFrame to hold trace data
        self.df = self.create_dataframe()

    def create_dataframe(self) -> pd.DataFrame|None:
        """
        Create a new DataFrame with the specified columns.

        :return: A new DataFrame with the specified columns.
        :rtype: pd.DataFrame
        """
        if self.columns is not None:
            if '_path_' not in self.columns:
                self.columns.insert(0, '_path_')

            if '_timestamp_' not in self.columns:
                self.columns.insert(0, '_timestamp_')

            return pd.DataFrame(columns=self.columns)
        else:
            return None

    def flush(self) -> None:
        """
        Flush the trace data to a file or output.

        This method can be overridden to implement custom flush behavior.
        """
        if self.df is None:
            return

        self.debug(f"Flushing trace data to {self.tracefile}")
        if os.path.exists(self.tracefile):
            self.df.to_csv(self.tracefile, mode="a", header=False, index=False)
        else:
            self.df.to_csv(self.tracefile, mode="w", header=True, index=False)

    async def run_phase(self) -> None:
        """
        Run phase for the coverage component.

        """
        while True:
            # Wait for an item to be available on the port
            item = await self.item_port.blocking_get()

            # If no columns are defined, use all public attributes of the item
            if self.df is None:
                self.columns = []
                for k,v in vars(item).items():
                    if not k.startswith('_') and not callable(v):
                        if k not in self.columns:
                            self.columns.append(k)

                self.df = self.create_dataframe()

            # Create a row dictionary for the DataFrame
            # Populate the row with item attributes
            row = {}
            for col in self.df.columns:
                if hasattr(item, col):
                    v = getattr(item, col)
                    if isinstance(v, (MutableSequence | tuple)):
                        row[col] = "[ " + ", ".join(v) + " ]"
                    elif isinstance(v, (MutableMapping)):
                        row[col] = "{ " + ", ".join(f"{_k} : {_v}" for _k, _v in v.items()) + " }"
                    else:
                        row[col] = str(v)
                else:
                    row[col] = None

            if row['_timestamp_'] is None:
                row['_timestamp_'] = cocotb.utils.get_sim_time("ns")

            if row['_path_'] is None:
                row['_path_'] = self.get_full_name()

            # Append the row to the DataFrame
            self.df.loc[len(self.df)] = row

            # Flush and create new dataframe
            if len(self.df) >= self.flush_interval:
                self.flush()
                self.df = pd.DataFrame(columns=self.df.columns)

    async def report_phase(self) -> None:
        """
        Report phase for the bandwidth component.

        Generate plot of bytes on bus over time windows

        """
        self.flush()

__all__ = ["Trace"]
