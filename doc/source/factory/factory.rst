.. _factory:

AVL Factory
===========

.. inheritance-diagram:: avl._core.factory
    :parts: 1

Overview
--------

The AVL factory provides the same functionality as the UVM factory without the complexity \
of the class::type_id::create() syntax as the factory is native to the :doc:`avl.Object </modules/avl._core.object>` class.

All classes that exend the :doc:`avl.Object </modules/avl._core.object>` class can be overridden by the factory. \

Debugging the factory can be done by printing via either the :doc:`Factory.print_factory </modules/avl._core.factory>` method, or \
simply casting the Factory() to a string.

Override by Type
----------------
.. literalinclude:: ../../../examples/factory/override_component_by_type/cocotb/example.py
    :language: python

Override by Instance
--------------------

There is no override by name in AVL. Instead, the factory can be used to override by instance. As wildcards \
(see below) are supported names can always be found.

.. literalinclude:: ../../../examples/factory/override_component_by_instance/cocotb/example.py
    :language: python

Wildcards are also supported. These are implemented using the Python `fnmatch <https://docs.python.org/3/library/fnmatch.html>`_ module. \
If multiple matches are found, the most specific match is used :any:`Factory.specificity`.

.. literalinclude:: ../../../examples/factory/override_component_by_instance_with_wildcard/cocotb/example.py
    :language: python

Variables
---------

Similar to the UVM config_db / resource_db variables can be set and retrieved from the factory. \
No copying is done automatically, classes are passed by reference and literals by value. \

The :doc:`Factory.set_variable </modules/avl._core.factory>` method adds a variable to the \
factory at a path. Wildcards are allowed in the path. When the :doc:`Factory.get_variable </modules/avl._core.factory>` \
method is called, it will attempt to match the provided path to the existing paths in the factory. \
If a match is found, it will return the associated value. If multiple matches are found, the Factory will use the \
:doc:`Factory.specificity </modules/avl._core.factory>` method on the matching paths to determine which path \
is the most specific, then it will return the value associated with that path. \
Otherwise, it will return a default value. If no default value is provided, it will raise a `KeyError <https://docs.python.org/3/library/exceptions.html>`_.

The Factory can be useful for sharing :doc:`avl.Var </modules/avl._core.var>` objects, cocotb hdl handles,
and configurations for components.

.. literalinclude:: ../../../examples/factory/variables/cocotb/example.py
