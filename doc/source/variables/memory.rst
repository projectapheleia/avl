.. _variable_memory:

Memory
======

AVL provides a generic byte memory model.

The memory must be configured by width, and is implemented as a sparse memory.

In addition it supports:

- Configurable initalization : :any:`Memory.set_init_fn`

- Endianness : :any:`Memory.set_endianness`

- Multiple address ranges : :any:`Memory.add_range`

- User callback on access to undefined range : :any:`Memory.miss`

- User controlled access width for reads and writes : :any:`Memory.read` :any:`Memory.write`

    - Write support strobes - obeying endianness

- Comparison of two memories : :any:`Memory.compare`

- Export and import from multiple formats : :any:`Memory.export_to_file`, :any:`Memory.import_from_file`

    - Verilog Hex (readmemh) and Verilog Binary (readmemb)

    - CSV and JSON

    - Intel Hex (ihex), Motorola S-Record (srec), TI Text (ti-txt)

    - Verilog Vmem (verilog vmem)


Example
-------

.. literalinclude:: ../../../examples/memory/simple/cocotb/example.py
    :language: python

Factory override and comparison
-------------------------------

The memory is an :doc:`avl.Object </modules/avl._core.object>`, so :any:`Factory.set_override_by_type` replaces it, \
including a memory a library builds internally. A memory is built by width rather than by name, so it has no \
instance path and an override by instance does not apply to it.

:any:`Memory.compare` compares two memories byte by byte over every address either of them has touched, \
reading an untouched byte through the initialization function of its memory without storing it.

.. literalinclude:: ../../../examples/memory/override/cocotb/example.py
    :language: python
