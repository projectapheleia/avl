# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Phase Manager

from __future__ import annotations

from typing import TYPE_CHECKING

from anytree import AnyNode, RenderTree
from graphviz import Digraph

if TYPE_CHECKING:
    from .component import Any, Component

class Visualization:
    _nodes: dict[Any|Component, AnyNode] = {None: AnyNode(id="root")}

    @staticmethod
    def add_component(component: Component) -> None:
        """
        Adds a component to the visualization tree.

        This method inserts the given component into the internal node structure,
        ensuring that each component is unique within the visualization tree. If the
        component already exists, a ValueError is raised.

        :param component: The component to be added to the visualization tree.
        :type component: object
        :raises ValueError: If the component already exists in the visualization tree.
        """
        if component in Visualization._nodes:
            raise ValueError(
                f"Component {component.get_name()} already exists in the visualisation tree."
            )

        Visualization._nodes[component] = AnyNode(
            id=component.get_name(), parent=Visualization.get_node(component.get_parent())
        )

    @staticmethod
    def get_node(component: Component|None) -> AnyNode:
        """
        Retrieve the node associated with the given component from the AVL visualization.

        :param component: The component whose node is to be retrieved.
        :type component: Any
        :returns: The node corresponding to the specified component.
        :rtype: Any
        :raises KeyError: If the component is not found in the nodes dictionary.
        """
        return Visualization._nodes[component]

    @staticmethod
    def tree(component: Component|None = None) -> str:
        """
        Returns a string representation of the AVL visualization tree.
        This method traverses the AVL visualization tree and constructs a string
        representation of the tree structure, including the IDs of each node.

        :param component: The component whose subtree is to be represented.
        :type component: Any
        :returns: A string representation of the AVL visualization tree.
        :rtype: str
        """
        retval = ""
        for pre, _, node in RenderTree(Visualization.get_node(component)):
            retval += f"{pre}{node.id}\n"
        return retval

    @staticmethod
    def diagram(component: Component|None = None) -> None:
        """
        Generates a diagram of the AVL visualization tree using Graphviz.
        This method creates a directed graph representation of the AVL visualization tree,
        allowing for visual inspection of the component hierarchy. The diagram is saved
        as a PNG file.

        :param component: The component whose subtree is to be represented.
        :type component: Any
        """

        def add_subgraph(dot, node):
            if node.children:
                with dot.subgraph(name=f"cluster_{id(node)}") as sub:
                    sub.attr(label=f"{node.id}")
                    for child in node.children:
                        add_subgraph(sub, child)
            else:
                label = f"{node.id}"
                dot.node(str(id(node)), label, shape="box")

                dot = Digraph(format="png")
                dot.attr("node", shape="box")

        # Creat the diagram
        dot = Digraph(format="png")
        dot.attr("graph", rankdir="TB")

        # Add the components
        add_subgraph(dot, Visualization.get_node(component))

        if component is None:
            dot.render("root", cleanup=True)
        else:
            dot.render(f"{component.get_name()}", cleanup=True)


__all__ = ["Visualization"]
