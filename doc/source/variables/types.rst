.. _variable_types:

Variable Types
==============

AVL provides a number of variable types more appropriate for HDL design than \
the standard Python types.

- Python lacks 4-state supports. As such all cocotb and AVL variables are 2-state.

- Python lacks width support for integers. AVL adds native width and sign support including half, single and double precision floating point numbers.


+----------------------+--------------+--------------------------+
| System Verilog Type  | Python Type  | AVL Variable             |
+======================+==============+==========================+
| shortint             | int          | avl.Int16                |
+----------------------+--------------+--------------------------+
| int                  | int          | avl.Int32                |
+----------------------+--------------+--------------------------+
| longint              | int          | avl.Int64                |
+----------------------+--------------+--------------------------+
| byte                 | int          | avl.Byte / avl.Int8      |
+----------------------+--------------+--------------------------+
| bit                  | bool         | avl.Logic / avl.Bool     |
+----------------------+--------------+--------------------------+
| logic                | int          | avl.Logic / avl.Unit8 /  |
+----------------------+--------------+ avl.Uint16 / avl.Uint32 /|
| reg                  | int          | avl.Uint64               |
+----------------------+--------------+--------------------------+
| integer              | int          | avl.Int / avl.Int32      |
+----------------------+--------------+--------------------------+
| time                 | int          | avl.Int64                |
+----------------------+--------------+--------------------------+
| real                 | float        | avl.Double / avl.Fp64    |
+----------------------+--------------+--------------------------+
| shortreal            | float        | avl.Half / avl.Fp32      |
+----------------------+--------------+--------------------------+
|                      | float        | avl.Float / avl.Fp16     |
+----------------------+--------------+--------------------------+
| string               | str          | str                      |
+----------------------+--------------+--------------------------+
| enum                 | Enum         | avl.Enum                 |
+----------------------+--------------+--------------------------+

Variable Usage
--------------

AVL attempts to make variable usage as close to Python and SystemVerilog as possible.

All AVL variable types inherit from the :doc:`avl.Var </modules/avl._core.var>` base class which provides the magic methods \
to make the variables behave like their Python and SystemVerilog counterparts.

The only exception to this is when attempting to directly update the value of a variable, when the user \
must update the underlying value explicitly.

Unlike python ints avl_vars are mutable, so the user can update the value \
of the variable directly without creating a new handle.
AVL variables can be used in the same way as Python variables, and can be \
used in expressions, assignments, and function calls. This is to allow variables saved for \
lambda functions to be preserved.

:doc:`avl.Logic </modules/avl._core.logic>` objects are unsigned and support constraints usings \
bitwise operations. However, due to this they can be slower to randomize than \
:doc:`avl.Int </modules/avl._core.int>` and :doc:`avl.Uint </modules/avl._core.uint>` objects which \
only support arithmetic constraints.

:doc:`avl.Logic </modules/avl._core.logic>` and its children (i.e. :doc:`avl.Uint </modules/avl._core.uint>`, \
:doc:`avl.Int </modules/avl._core.int>` and :doc:`avl.Bool </modules/avl._core.bool>`) all support bit slice access with the following constraints:

- Single-index slices are supported, e.g. ``myvar[31]`` will return bit 31 of ``myvar``.
- Slice indexes follow the same rule as for strings and lists: ``myvar[0:8]`` will access **bits 0 to 7** of ``myvar``.
- Slice indexes must always be positive.
- SystemVerilog-like accesses where the greater index is first (e.g. ``myvar[8:0]``), are not supported.
- Steps (e.g. ``myvar[0:8:1]``) are not supported.

Integer / Logic Example
-----------------------
.. literalinclude:: ../../../examples/variables/logic/cocotb/example.py
    :language: python

Float / Real Example
--------------------
.. literalinclude:: ../../../examples/variables/float/cocotb/example.py
    :language: python

Enum Example
------------
.. literalinclude:: ../../../examples/variables/enum/cocotb/example.py
    :language: python
