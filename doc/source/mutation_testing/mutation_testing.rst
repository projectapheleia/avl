.. _mutation_testing:

AVL Mutation Testing
====================

Overview
--------

AVL provides a tool to measure how well a testbench detects defects in the RTL.
The tool creates modified copies of the design, called mutants, and runs the
existing testbench against each one. Each mutant contains one artificial defect,
such as replacing an addition with a subtraction or delaying a signal by one cycle.

A mutant that passes the tests is reported as a survivor. This can indicate
missing stimulus or a result that the testbench does not check. For example,
changing ``a < b`` to ``a <= b`` only changes the result when the operands are
equal. A testbench needs both stimulus that reaches this boundary and a check
that observes the difference.

The tool is exported as the ``avl-mutation-testing`` project script and is added
to your path when AVL is installed. It uses pyslang, included in the AVL
dependencies, to locate mutation sites in SystemVerilog source. Running the
tests also requires a simulator and the normal testbench build environment.
If yosys is available on your path, the tool performs a bounded equivalence
check to identify mutants that do not change the observed design behaviour.

Running an Example
------------------

The examples under ``examples/mutation_testing`` provide a complete flow for
generating mutants, running simulations and reporting the score. From the
repository root, run the ALU example with the following commands:

.. code-block:: shell

    $ cd examples/mutation_testing/alu
    $ make sim
    $ make mutants
    $ make mutation_regression

``make sim`` runs the golden, unmodified design. ``make mutants`` generates the
mutants and writes an HTML report to ``mutants/mutations.html``. Generation is
also a prerequisite of simulation, so the first command may already create the
mutants. ``make mutation_regression`` runs the golden design and each mutant in
turn, then reports which defects were detected. ``make mutate`` is a shorthand
for the same regression.

To run one mutant for debug, pass its ID to the simulation target:

.. code-block:: shell

    $ make sim AVL_MUTANT=2

Each example selects its mutation classes and count in ``mutation.mk``:

.. code-block:: make

    MUTATION_TYPES := arith,compare
    MUTATION_COUNT := 3

After changing these settings, run ``make clean`` before regenerating the
mutants. The generation target tracks changes to the RTL, but does not track
changes to these settings.

The examples use ``COCOTB_RANDOM_SEED=1`` for every simulation so that the golden
design and all mutants receive the same stimulus. To use another seed, apply it
to the whole campaign:

.. code-block:: shell

    $ make mutation_regression COCOTB_RANDOM_SEED=42

To run all the example campaigns, use ``make regression`` from
``examples/mutation_testing``. ``make list`` lists the examples and plain
``make`` displays help. The regression keeps a log for each example under
``.results/<example>.log`` and skips examples whose declared required tools are
unavailable.

Generating Mutants
------------------

The command line tool can also be used directly. To inspect the available
classes and list sites without writing any files:

.. code-block:: shell

    $ avl-mutation-testing --list-types
    $ avl-mutation-testing --source rtl/*.sv --types arith,compare --count 4 --list

To generate the selected mutants and a catalogue for the regression:

.. code-block:: shell

    $ avl-mutation-testing --source rtl/*.sv --top example_hdl \
        --types arith,compare --count 4 --output mutants --json mutants/faults.json

Each numbered directory contains a complete copy of the supplied source files,
with one defect applied to one file. The golden files are left unchanged.
Changed lines carry an ``AVL MUTATION`` comment identifying the modification.
The HTML report shows the changes in their source context, and the JSON
catalogue records the IDs, locations, modifications and equivalence verdicts.

.. code-block:: text

    mutants/
        1/                 Source files for mutant 1
        2/                 Source files for mutant 2
        faults.json        Catalogue requested with --json
        mutations.html     Source comparison and equivalence report

Use a dedicated output directory: generation removes an existing output
directory before writing the new mutants. Source files are copied using their
base names, so the supplied files must have distinct base names.

For a design containing submodules, supply all the required source files and
set ``--top`` to the design's top module. Otherwise the equivalence check uses
the module containing the mutation, which may expose a difference that is not
observable at the top of the design.

Selecting Mutation Sites
------------------------

By default, all supported classes and all candidate sites are selected.
``--types`` restricts the classes and ``--count`` limits the number of mutants.
When a limit is applied, the tool selects across classes and operators before
repeating them. The order of classes in ``--types`` determines their priority.
Within an operator, sites are selected in source order.

Adding ``--seed`` uses reproducible random sampling when the count is smaller
than the number of candidates. This seed controls site selection; the cocotb
seed controls simulation stimulus. Selected sites are sorted by file and source
position and numbered from 1, so IDs can change when the sources or selection
settings change.

Mutation Classes
----------------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Class
     - Modification
   * - ``arith``
     - Replaces arithmetic operators: ``+`` with ``-``, ``-`` with ``+``,
       ``*`` with ``+``, ``/`` with ``*`` and ``%`` with ``/``.
   * - ``bitwise``
     - Replaces ``&`` with ``|``, ``|`` with ``&`` and ``^`` with ``&``.
   * - ``compare``
     - Swaps ``==`` and ``!=``, ``<`` and ``<=``, or ``>`` and ``>=``.
   * - ``logical``
     - Swaps ``&&`` and ``||``.
   * - ``shift``
     - Swaps ``<<`` and ``>>``.
   * - ``unary``
     - Removes a logical ``!`` or bitwise ``~`` operator.
   * - ``pipeline``
     - Adds one cycle of delay to a nonblocking assignment to a whole signal.
       Constant assignments and indexed targets are excluded.
   * - ``sign``
     - Negates the value assigned to a signed variable. Explicit signed
       declarations and types that are signed by default are recognised.
   * - ``array_packed``
     - Reverses a packed declaration range, changing the bit numbering.
   * - ``array_unpacked``
     - Reverses an unpacked declaration range, changing the element order.
   * - ``width``
     - Narrows an internal packed signal by one bit and inserts casts at its
       assignments and references to preserve surrounding expression widths.
   * - ``condition``
     - Forces a branch condition true or false, and changes comparison
       boundaries within the condition. Reset branches are excluded.
   * - ``statement``
     - Replaces a nonblocking assignment in a clocked block with a null
       statement, so the register holds its value. Reset assignments are excluded.
   * - ``operand``
     - Swaps the operands of a non-commutative operator, for example
       ``a - b`` becomes ``b - a``.
   * - ``blocking``
     - Changes a nonblocking assignment to a blocking assignment.
   * - ``nonblocking``
     - Changes a blocking assignment to a nonblocking assignment.

Sites are found from syntax rather than an elaborated design. Elaboration-time
expressions are excluded from operator mutations. Signedness supplied through
a typedef or parameterised type is not resolved. Width mutations are limited to
single internal declarations with literal bounds, at least two bits, no bit or
part selects, and no assignment that reads its own target.

The ``blocking`` and ``nonblocking`` classes require an edge-triggered block
and a later read of the target within the same enclosing block. Their effects
depend on simulation scheduling. When ``condition`` and ``compare`` are both
requested, comparisons used in branch decisions belong to ``condition`` to
avoid duplicate mutations. Using ``compare`` alone still includes them.

Equivalence Checking
--------------------

During generation, yosys compares each mutant with the golden design using a
SAT check over a fixed number of cycles. The default bound is 8 cycles and the
default timeout is 60 seconds per mutant.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Verdict
     - Meaning
   * - ``different``
     - A sequence that distinguishes the designs was found in the formal model.
   * - ``equivalent``
     - No difference was found within the cycle bound and the check's
       zero-initialised state model. This is not an unbounded proof of equivalence.
   * - ``unknown``
     - yosys could not read the design or produce a verdict.
   * - ``timeout``
     - The check exceeded the time limit.
   * - ``skipped``
     - yosys was unavailable or ``--no-equiv`` was specified.

Increase ``--equiv-cycles`` if a defect may take more cycles to become visible.
``--equiv-timeout`` controls the time available for each check. The simulation
regression still runs every mutant, including those marked equivalent. A passing
mutant marked equivalent is excluded from the score; a failing one is counted
as detected. The other verdicts do not exclude a mutant from scoring.

Running a Regression
--------------------

Generation and grading are separate operations. After generating a JSON
catalogue, run the regression with:

.. code-block:: shell

    $ avl-mutation-testing --grade --json mutants/faults.json \
        --make "make sim" --archive mutants

The build must accept ``AVL_MUTANT=0`` to select the golden RTL and a positive
ID to select ``mutants/<id>``. The grader appends this variable to the command
specified by ``--make``. It does not switch sources itself. Use a separate build
directory for each ID, or ensure the build recompiles when the selected RTL
changes. The example makefiles provide this integration.

The golden run must pass before any mutants are scored. For each run, the
grader removes the previous results XML, captures the simulation output and
checks for AVL error, critical or fatal log records, cocotb test failures, or missing
or malformed results XML. These conditions count as detection for a mutant and
as failure for the golden design.

.. note::

   A build failure that produces no results XML also counts as detection.
   Inspect the archived log before treating an unexpected detection as evidence
   that the testbench checked the defect. The process exit status alone is not
   used to determine detection.

The report uses three statuses: ``DETECTED``, ``SURVIVED`` and ``EQUIVALENT``.
The score is calculated as follows:

.. code-block:: text

    score = 100 * detected / (detected + survived)

When there are no scored mutants, the reported score is 100%. Always review the
counts alongside the percentage. A completed regression writes ``summary.json``
beside the catalogue with the mutation, detection, survivor, equivalent and
scored counts, and the score.

With ``--archive mutants``, the golden log is saved as
``mutants/golden/sim.log`` and each mutant log as ``mutants/<id>/sim.log``.
Results XML is copied to the same directory when available. Runs are serial;
the examples share output files such as ``coverage.json`` in the working
directory.

Grading returns exit status 0 when no mutants survive, 1 when there are
survivors, and 2 when the golden run fails. This allows the regression to be
used in CI. For a survivor, inspect the mutation report and simulation log,
check whether the stimulus reaches the changed behaviour, and check whether
the testbench observes the affected result. An unresolved equivalence verdict
may also require investigation before changing the testbench.

Command Line Reference
----------------------

Generation options
~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Option
     - Description
   * - ``--source FILE [FILE ...]``
     - SystemVerilog source files. Required for generation and site listing.
   * - ``--output DIRECTORY``
     - Mutant output directory. Default: ``mutants``. Replaced on generation.
   * - ``--types CLASSES``
     - Comma-separated mutation classes. Default: all classes.
   * - ``--count N``
     - Maximum number of mutants. Default: all candidates. Fewer available
       candidates produces a warning rather than a generation failure.
   * - ``--seed N``
     - Seed for random sampling when limiting the candidate count.
   * - ``--json FILE``
     - Write the catalogue to this file. Required later for grading.
   * - ``--html FILE``
     - HTML report location. Default: ``<output>/mutations.html``.
   * - ``--top MODULE``
     - Top module for equivalence checking. Default: the mutated module.
   * - ``--no-equiv``
     - Skip equivalence checking.
   * - ``--equiv-cycles N``
     - Equivalence unrolling bound. Default: ``8``.
   * - ``--equiv-timeout SECONDS``
     - Time limit per equivalence check. Default: ``60``.
   * - ``--list``
     - List selected sites without generating files or checking equivalence.
   * - ``--list-types``
     - List supported classes and exit. No source files are required.

Grading options
~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Option
     - Description
   * - ``--grade``
     - Run the golden design and mutants from an existing catalogue.
   * - ``--json FILE``
     - Catalogue to read. Required with ``--grade``.
   * - ``--make COMMAND``
     - Simulation command. Default: ``make sim``.
   * - ``--directory DIRECTORY``
     - Working directory for simulations. Default: the current directory.
   * - ``--results FILE``
     - cocotb results file, relative to the simulation directory.
       Default: ``results.xml``.
   * - ``--var NAME``
     - Make variable used to select the mutant. Default: ``AVL_MUTANT``.
   * - ``--archive DIRECTORY``
     - Save each run's log and results. No archive is written by default.

Relative catalogue and archive paths are resolved from the tool's working
directory, not from ``--directory``. ``--help`` displays all command line options.

API Reference
-------------

The Python functions are documented in
:doc:`avl.tools.mutation_testing </modules/avl.tools.mutation_testing>`.
