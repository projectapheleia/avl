# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Hierachical component

from __future__ import annotations

from typing import Any

import cocotb
import cocotb.triggers
from cocotb.triggers import NullTrigger

from .object import Object
from .phase import Phase
from .phase_manager import PhaseManager
from .visualization import Visualization


class Component(Object):

    def __deepcopy__(self, _):
        """
        Deep copy the Component - to avoid recursion just return the instance.

        :param memo: Dictionary to keep track of already copied objects.
        :type memo: dict
        :return: Deep copied Component.
        :rtype: Component
        """
        return self

    def __init__(self, name: str, parent: Component) -> None:
        """
        Initialize Component.

        :param name: Name of the component.
        :type name: str
        :param parent: Parent component.
        :type parent: Component
        """
        super().__init__(name, parent)

        # Parent / Child
        self._children_ = []
        if parent is not None:
            parent.add_child(self)

        Visualization.add_component(self)

        # Phase management
        # Sync to ensure all children complete their hierarchical function calls
        # before the parent does.
        self._hierarchical_sync_ = cocotb.triggers.Event()

    async def _hierarchical_func_(self, fn_name: str, *args: Any, **kwargs: Any) -> Any:
        """
        Execute a hierarchical function on all child components.

        :param fn_name: Name of the function to execute.
        :type fn_name: str
        :param args: Variable length argument list.
        :param kwargs: Arbitrary keyword arguments.
        """
        phase = PhaseManager._current
        assert phase is not None
        if phase.top_down:
            fn = getattr(self, fn_name, None)
            if fn is not None:
                await fn(*args, **kwargs)

        for c in self.get_children():
            cocotb.start_soon(c._hierarchical_func_(fn_name, *args, **kwargs))
            await NullTrigger()
            if not phase.top_down:
                await c._hierarchical_sync_.wait()
                c._hierarchical_sync_.clear()

        if not phase.top_down:
            self._hierarchical_sync_.set()
            fn = getattr(self, fn_name, None)
            if fn is not None:
                await fn(*args, **kwargs)

    def add_child(self, child: Component) -> None:
        """
        Add a child component.

        :param child: Child component to add.
        :type child: Component
        """
        if child not in self._children_:
            self._children_.append(child)

    def get_child(self, name: str) -> Component|None:
        """
        Get a child component by name.

        :param name: Name of the child component.
        :type name: str
        :return: Child component.
        :rtype: Component
        """
        for c in self._children_:
            if c.name == name:
                return c
        return None

    def get_num_children(self) -> int:
        """
        Get the number of child components.

        :return: Number of child components.
        :rtype: int
        """
        return len(self._children_)

    def get_children(self) -> list[Component]:
        """
        Get all child components.

        :return: List of child components.
        :rtype: list
        """
        return self._children_

    async def start(self) -> None:
        """
        Start the component and execute its phases.
        """
        while PhaseManager._current is not None:
            fn_name = f"{PhaseManager._current.name.lower()}_phase"
            await self._hierarchical_func_(fn_name)
            await PhaseManager._current.wait_for_objections()
            PhaseManager.next()

    def raise_objection(self, phase: Phase|None = None, obj: Object|None = None) -> None:
        """
        Raise an objection for the current phase.

        :param phase: Phase to raise objection for.
        :type phase: Phase
        :param obj: Object raising the objection.
        :type obj: Component
        """
        if phase is None:
            phase = PhaseManager._current

        if obj is None:
            obj = self

        assert phase is not None
        phase.raise_objection(obj)

    def drop_objection(self, phase: Phase|None = None, obj: Object|None = None) -> None:
        """
        Drop an objection for the current phase.

        :param phase: Phase to drop objection for.
        :type phase: Phase
        :param obj: Object dropping the objection.
        :type obj: Component
        """
        if phase is None:
            phase = PhaseManager._current

        if obj is None:
            obj = self

        assert phase is not None
        phase.drop_objection(obj)


__all__ = ["Component"]
