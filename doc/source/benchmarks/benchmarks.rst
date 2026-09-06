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

Object Creation
---------------

A testbench builds transactions constantly - one per bus item, one per sequence
item, thousands per test - so the cost of constructing an AVL object and its
variables is paid over and over. Building a transaction with six variables used to
take 44 microseconds; it now takes 10.

Results
^^^^^^^

Measured on a transaction carrying one of each variable type, and on four
different transaction classes built round-robin so that nothing depends on the
same class being constructed repeatedly. The base here is the tree as it stood
after the start-up work above, not the 1.0.1 release.

.. list-table::
   :header-rows: 1
   :widths: 40 20 20 20

   * - Measurement
     - Base
     - Optimised
     - Change
   * - Transaction with 6 variables
     - 43.92 us
     - **10.47 us**
     - -76.2 %
   * - Four classes, round-robin
     - 36.13 us
     - **8.47 us**
     - -76.5 %

.. image:: /images/avl_objects_transaction.png
   :align: center
   :alt: Base versus optimised construction time for a transaction with six variables and for four transaction classes built in turn.

Building 1000 transactions went from 44 ms to 10 ms.

Per Type
^^^^^^^^

.. image:: /images/avl_objects_breakdown.png
   :align: center
   :alt: Base versus optimised construction time for each AVL object and variable type, from avl.Object at around one microsecond to avl.Fp32 at fifteen.

.. list-table::
   :header-rows: 1
   :widths: 34 22 22 22

   * - Type
     - Base
     - Optimised
     - Change
   * - :doc:`avl.Object </modules/avl._core.object>`
     - 1.08 us
     - 0.64 us
     - -41.2 %
   * - :doc:`avl.Transaction </modules/avl._core.transaction>`
     - 1.23 us
     - 0.72 us
     - -41.5 %
   * - :doc:`avl.Logic </modules/avl._core.logic>` (64 bit)
     - 3.75 us
     - 1.35 us
     - -64.0 %
   * - :doc:`avl.Uint32 </modules/avl._core.uint>`
     - 4.61 us
     - 1.01 us
     - -78.2 %
   * - :doc:`avl.Int16 </modules/avl._core.int>`
     - 5.34 us
     - 1.11 us
     - -79.2 %
   * - :doc:`avl.Bool </modules/avl._core.bool>`
     - 3.84 us
     - 1.02 us
     - -73.4 %
   * - :doc:`avl.Enum </modules/avl._core.enum>`
     - 5.59 us
     - 2.27 us
     - -59.4 %
   * - :doc:`avl.Fp32 </modules/avl._core.float>`
     - 14.96 us
     - 1.26 us
     - -91.6 %

Where the Time Went
^^^^^^^^^^^^^^^^^^^

**Per-instance state that was really per-class.** Every variable stored its own
copy of values fixed for its type - the width and its mask, the numpy scalar type
of a float, the format callable, an empty constraint dictionary. A
:doc:`avl.Uint8 </modules/avl._core.uint>` wrote its width on every instance even
though a ``Uint8`` is 8 bits by definition. These are now class attributes, and an
instance is only given its own copy when it actually differs - a ``Logic``
constructed with a non-default width, or a variable that has a constraint added to
it. The same applies to ``Object`` and ``Transaction``, whose table formatting
settings, transaction id and empty dictionaries all moved to the class.

**A global registry every variable joined.** Construction allocated an index and
inserted the variable into a module-level weak dictionary. That index exists only
to name the variable in Z3 and to map a solution back to it, so a variable that is
never randomized never needed one. The index is now allocated the first time it is
read.

**The factory was consulted whether or not it was used.** Creating an object built
an instance path - walking the whole parent chain and formatting a string - and
then asked the factory for an override, even when nothing had ever been
registered. The factory now tracks whether it is empty, and object creation
returns immediately when it is. Testbenches that use the factory are unaffected.

**A warning suppressed on every float cast.** The floating point types wrapped
every cast in ``warnings.catch_warnings()`` to hide a numpy overflow warning,
which recompiles a regular expression each time. That was 11 of the 15
microseconds it took to build an ``Fp32``. The cast now checks the value against
the type's maximum and only takes that path when the value really can overflow.

**Constructors that did nothing but forward.** ``Uint32`` called ``Uint`` called
``Logic`` called ``Var`` - five frames for an ``Int16``, each repacking its
arguments. The intermediate layers existed only to change a default format or pin
a width, both of which are now class attributes, so they are gone. A fixed-width
type still rejects an explicit width, so ``avl.Uint8(0, width=16)`` raises rather
than silently producing a 16 bit value.

None of this changes how objects or variables are used, and no public API changed.

Randomization
-------------

Constraint solving is the most expensive thing a testbench asks AVL to do, and a
sequence does it once per item. The work below reduced what a randomization costs
without changing a single value it produces.

Results
^^^^^^^

Measured on a packet carrying one of each variable type - logic, unsigned,
signed, enumerated and floating point - under arithmetic, bitwise and select
constraints, and on the other shapes a testbench randomizes.

.. list-table::
   :header-rows: 1
   :widths: 34 22 22 22

   * - Measurement
     - Base
     - Optimised
     - Change
   * - Constrained packet
     - 22 897 us
     - **19 607 us**
     - -14.4 %
   * - Integer fields only
     - 3 796 us
     - **2 555 us**
     - -32.7 %
   * - Single variable
     - 1 975 us
     - **1 275 us**
     - -35.4 %
   * - No constraints
     - 1 438 us
     - 1 326 us
     - -7.8 %
   * - New object each time
     - 24 214 us
     - 23 709 us
     - -2.1 %

.. image:: /images/avl_random_overall.png
   :align: center
   :alt: Base versus optimised randomization time for a constrained packet, integer fields only, an unconstrained object, a new object each time, and a single variable.

Where the Time Went
^^^^^^^^^^^^^^^^^^^

**One draw per variable rather than one per bit.** Randomization asks each bit,
softly, to match a random draw. Those draws came from a ``random.randint(0, 1)``
call per bit, where a single ``getrandbits`` call over the whole width gives the
same bits for a fraction of the cost. The direct draws a variable falls back to
when the solver does not decide it now go through a helper built on the same call
rather than through ``random.randint``, which revalidates its arguments every time.

**Clauses kept rather than rebuilt.** Only two clauses can exist for a bit - one
asking it for zero, one asking it for one - and neither depends on anything that
changes between randomizations. They are now built once and reused. A variable
randomized a single time, as a fresh sequence item is, does not pay to fill a
cache nothing will read: the cache is armed on the second randomization, so the
first behaves exactly as it did before.

**No clause on a bit that has no choice.** See below.

Free Bit Analysis
^^^^^^^^^^^^^^^^^

A bit the hard constraints pin to one value cannot be traded against anything.
Its clause is satisfied in every solution or violated in every one, so it shifts
every candidate's cost by the same amount and decides nothing. Dropping it leaves
the result distribution exactly as it was, and takes work off the search.

Before randomizing, AVL now names every bit with a boolean and asks Z3, in one
question for all of them, which are forced. The answer depends only on the
object's own hard constraints, so it is worked out once per constraint shape and
kept. A constraint passed to :doc:`randomize() </modules/avl._core.object>` can pin further bits but never
unpin one, so the answer stays correct when one is passed.

How much this is worth depends entirely on how tightly the constraints bind:

.. list-table::
   :header-rows: 1
   :widths: 28 18 18 18 18

   * - Shape
     - Bits kept
     - Every bit
     - Free bits
     - Change
   * - Loosely constrained
     - 113 of 124
     - 17 794 us
     - 17 379 us
     - -2.3 %
   * - Tightly constrained
     - 25 of 112
     - 5 160 us
     - **2 260 us**
     - **-56.2 %**

.. image:: /images/avl_random_freebits.png
   :align: center
   :alt: Randomization time with a clause on every bit against a clause on free bits only, for a loosely constrained and a tightly constrained packet.

A packet whose address may fall anywhere in 32 bits has almost no pinned bits and
gains almost nothing. Hold the same fields to the ranges a real testbench holds
them to - an address within one page, a burst of one to sixteen, a handful of
identifiers - and three quarters of their bits are pinned. Constrain tightly and
this is the largest single win available.

The values are unaffected. Randomizing the same object 400 times from the same
seed, with the analysis off and then on, gives identical distributions: the same
288 distinct addresses, the same per bit frequencies, the same set of lengths and
identifiers.

Running Your Own Measurements
-----------------------------

All the figures above were collected on a single machine at the time the changes
were made, using Verilator 5.040, cocotb 2.1.0 and Python 3.12.3. Absolute numbers
depend heavily on the machine, the simulator and the Python installation, so treat
them as an indication of scale rather than as values to expect.

The benchmarks used to produce them ship with AVL, and you are encouraged to run
them on your own setup - either to confirm the improvements or to check that a
change of your own has not regressed start-up or object creation time. See
`benchmarks/README.md <https://github.com/projectapheleia/avl/blob/main/benchmarks/README.md>`_
for what the benchmark measures and how to record and compare runs.

Comparing Against a Release
---------------------------

The benchmarks above measure one thing each in isolation. The examples benchmark
does the opposite: it runs every example in ``examples/`` twice - once against the
AVL in your checkout, once against the released ``avl-core`` of the same version
number from PyPI - and reports the difference for each one.

It is a utility rather than a result. Use it to see whether a change you have made
locally helps or hurts real testbenches, before deciding it was worth making.

Running it
^^^^^^^^^^

.. code-block:: shell

    $ source ./avl.sh                    # from the repository root
    $ cd benchmarks/examples
    $ ./examples_benchmark.py --dry-run  # show the plan, run nothing
    $ ./examples_benchmark.py            # 3 timed runs per example, per variant

The first real run builds a virtual environment holding the released ``avl-core``
and takes a while; later runs reuse it. ``--dry-run`` reports the versions, the
environments and the examples it would run without running any of them, which is
the quickest way to check the comparison is set up the way you expect.

Useful options
^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Option
     - Effect
   * - ``-n N``
     - Timed runs of each example in each variant. Default 3.
   * - ``--only PATTERN``
     - Only examples matching PATTERN, for example ``'constraints/*'``. Repeatable.
   * - ``--skip PATTERN``
     - Exclude examples matching PATTERN. Repeatable.
   * - ``--released-version V``
     - Compare against a release other than the current version number.
   * - ``--json FILE`` / ``--markdown FILE``
     - Record the run, so a later one can be compared against it.
   * - ``--rebuild-env``
     - Recreate the released environment, after changing what is pinned into it.

What it controls for
^^^^^^^^^^^^^^^^^^^^

AVL is the only difference between the two variants. ``cocotb``, ``z3-solver``
and the other shared dependencies are installed into the released environment at
the versions your local environment uses, so the simulator, the cocotb release
and the constraint solver are identical on both sides.

Each variant gets a private copy of ``examples/``, so neither writes into your
working tree or invalidates the other's build. Every example is run untimed first,
which compiles the DUT, so no timed sample includes Verilator compilation. Timed
runs then alternate between the variants, so drift in machine load does not
systematically favour either, and every run in both variants is given the same
random seed so the two solve the same problems.

An example that fails in either variant is reported as not compared rather than
aborting the run - a new example the released version cannot run, for instance.

See
`benchmarks/examples/README.md <https://github.com/projectapheleia/avl/blob/main/benchmarks/examples/README.md>`_
for the rest, including what is pinned into the released environment and why.
