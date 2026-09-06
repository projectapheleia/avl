.. _benchmarks:

Benchmarks
==========

Start-up Time
-------------

Every AVL testbench pays a fixed cost before the first simulation tick: Python has
to import the library. In AVL 1.0.1 that cost was close to a second, and almost all
of it was spent importing third party libraries that a testbench may never use.

AVL now defers those imports until the feature that needs them is actually used.
The tables and figures below record what that changed.

Results
^^^^^^^

Two testbenches were compared. Both instantiate the same empty DUT and finish at
time zero. One builds a standard :doc:`avl.Env </modules/avl._core.env>` with no content; the other is a
plain cocotb testbench with an empty test. The difference between them is the AVL
start-up overhead - everything AVL costs to start, with the simulator and cocotb
cancelled out.

.. list-table::
   :header-rows: 1
   :widths: 40 20 20 20

   * - Measurement
     - Base (1.0.1)
     - Deferred imports
     - Change
   * - ``import avl``
     - 350.0 ms
     - **15.7 ms**
     - -95.5 %
   * - AVL start-up overhead
     - 970.3 ms
     - **77.3 ms**
     - -92.0 %
   * - AVL testbench, full run
     - 1910.8 ms
     - 885.6 ms
     - -53.7 %
   * - Bare cocotb testbench (reference)
     - 940.5 ms
     - 808.3 ms
     - *unchanged by this work*

.. image:: /images/avl_startup_comparison.png
   :align: center
   :alt: Base versus deferred-import start-up times for import avl, the AVL start-up overhead and a full testbench run.

Starting a standard environment used to cost as much again as the entire cocotb
testbench it sits in. What remains is close to the run-to-run noise of the
full-simulation samples, so the residual 77 ms should be read as "at the floor"
rather than as a precise figure.

The cost was entirely in the import. A probe testbench timing the two halves
separately inside the simulator measured ``import avl`` at 884.0 ms before and
49.4 ms after, while constructing the :doc:`avl.Env </modules/avl._core.env>` itself measured 0.0 ms in
both cases.

Where the Time Went
^^^^^^^^^^^^^^^^^^^

Each of these libraries was imported eagerly by ``import avl``, and each serves a
feature a minimal testbench never reaches. The grey bar is what is left: AVL's own
modules, which are still imported eagerly.

.. image:: /images/avl_startup_breakdown.png
   :align: center
   :alt: Bar chart of the base import avl cost broken down by third party dependency, from pandas at 179.2 ms down to tabulate at 3.2 ms.

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Dependency
     - Cost
     - Needed for
   * - ``pandas``
     - 179.2 ms
     - coverage, log, trace and memory reports
   * - ``numpy``
     - 81.5 ms
     - :doc:`avl.Fp16, avl.Fp32 and avl.Fp64 </modules/avl._core.float>` arithmetic
   * - ``bincopy``
     - 25.3 ms
     - memory image load and export
   * - ``z3``
     - 15.8 ms
     - constrained randomization
   * - ``yaml``
     - 10.4 ms
     - YAML log files
   * - ``graphviz``
     - 7.2 ms
     - :doc:`avl.Visualization.diagram </modules/avl._core.visualization>`
   * - ``tabulate``
     - 3.2 ms
     - :doc:`avl.Object </modules/avl._core.object>` and :doc:`avl.Factory </modules/avl._core.factory>` tables

``numpy`` is counted separately from ``pandas`` because ``pandas`` imports it.
Deferring ``pandas`` on its own saved only about 220 ms, since the floating point
variable classes still pulled ``numpy`` in directly - the two only pay off together.

How It Works
^^^^^^^^^^^^

``lazy_import(name)`` returns a stand-in module that imports the real module the
first time an attribute is read from it. A module level ``import pandas as pd``
became ``pd = lazy_import("pandas")``; the call sites did not change, because every
use was already inside a function body.

There is nothing to configure and no change to any public API. The first testbench
to touch a deferred feature pays that library's import cost at that point instead
of at start-up; a testbench that never touches it never pays at all.

Running Your Own Measurements
-----------------------------

These figures were collected on a single machine at the time the changes were made,
using Verilator 5.040, cocotb 2.1.0 and Python 3.12.3. Absolute numbers depend
heavily on the machine, the simulator and the Python installation, so treat them as
an indication of scale rather than as values to expect.

The benchmark used to produce them ships with AVL, and you are encouraged to run it
on your own setup - either to confirm the improvement or to check that a change of
your own has not regressed start-up time. See
`benchmarks/README.md <https://github.com/projectapheleia/avl/blob/main/benchmarks/README.md>`_
for what the benchmark measures and how to record and compare runs.
