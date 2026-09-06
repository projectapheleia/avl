# Changelog

## [v1.1.0] - 2026-09-06

### Added
 - benchmarks/: a benchmark suite covering the four things a testbench spends its time on - start-up, object and variable creation, randomization and logging. Each records runs with `--json`/`--label` and compares against them with `--compare`, and `make` targets in `benchmarks/` list, run and clean the lot. `benchmarks/examples` additionally times every example against the released `avl-core` of the same version, to show what a local change is worth on real testbenches rather than on microbenchmarks. Results and write-ups are in each benchmark's `results/` directory, and summarised in the Benchmarks chapter of the documentation.
 - benchmarks/comparison: measures AVL against the alternatives rather than against itself. The same workload - sixteen classes, each declaring four unsigned logic vectors and two signed integers under eleven arithmetic, bitwise and related constraints, and each written with different constants - is written out in SystemVerilog, in AVL and in pyvsc, and run four ways: by the simulator's own constraint solver, from the `run_phase` of a pyuvm test, against the latest released `avl-core` from PyPI, and against the AVL in the working copy. Every flavour compiles the same RTL, runs through the same cocotb flow and does one item per clock edge, and each is measured twice - once with the randomization disabled - so the report carries both the total run time of the simulation and the randomization on its own, in microseconds per item. Timing samples the whole process group, because a SystemVerilog simulator solves constraints in a separate solver process whose CPU time `getrusage()` never sees. pyuvm and pyvsc are installed by the benchmark into a virtual environment of its own, so nothing in AVL depends on them. Each run writes `report.html`, `RESULTS.md`, `summary.csv` and `results.json`, and the results are summarised under Against Other Frameworks in the Benchmarks chapter of the documentation.

### Performance
 - Start-up: `import avl` no longer imports pandas, numpy, z3, bincopy, yaml, graphviz or tabulate. Each is now loaded the first time the feature that needs it is used - reporting, randomization, memory image I/O, diagrams - through a deferred import stand-in. `import avl` fell from 350.0 ms to 15.7 ms with cocotb already loaded, and the cost of starting a testbench over and above a bare cocotb one from 970.3 ms to 77.3 ms. Nothing about the public API changed; a testbench that uses a deferred feature pays that library's import when it first touches it instead of at start-up.
 - Object and variable creation: values that are fixed for a type - width and mask, numpy scalar types, the format callable, the empty constraint dictionaries - moved from every instance to the class, with an instance taking its own copy only where it differs. A variable's index into the global lookup table is now allocated the first time randomization needs it rather than on construction, the factory is no longer consulted when nothing is registered in it, and the floating point cast no longer suppresses a warning that cannot happen. Building a transaction with six variables fell from 43.92 us to 10.47 us.
 - Randomization: the per-bit randomization clauses are now built once per variable and reused, and their random values come from one draw per variable rather than one per bit. A bit that the hard constraints pin to a single value gets no clause at all - its clause is satisfied in every solution or violated in every one, so removing it leaves the result distribution exactly as it was. Randomizing a constrained packet fell 14.4%, a single variable 35.4%, and a packet whose fields are held to narrow ranges - as a real testbench holds them - 56%.
 - Logging: a record was compared against every record handled since the last flush, which with the default flush level meant around five hundred comparisons per message. The repeats that check exists to drop are now marked on the record itself, in constant time. The loggers carrying AVL's handler are held in a set rather than a list, and a component's full name, which names the logger of every message it writes, is built once and remembered rather than rebuilt from its ancestors each time. Writing a message from a component fell from 12.93 us to 6.18 us, and from six levels down from 21.94 us to 7.22 us. Every log format - csv, json, yaml, txt, md and rst - is byte for byte what it was.

### Fixed
 - examples/: `make sim` from the `examples/` directory failed every example. The shared makefile used `$(PWD)`, which is the directory make was invoked from rather than the example's own, so under the recursive make every example resolved its RTL and Python paths against `examples/`; and cocotb 2.0 stopped exporting `PYTHONPATH` from its own makefiles, so the testbench module was not importable. Now uses `$(CURDIR)` and exports `PYTHONPATH`.
 - Enum(): asking for a variable's Z3 representation more than once warned that it was overriding its own range constraint.
 - avl: `__version__` is now re-exported from the package, so `avl.__version__` works.
 - [#93](https://github.com/projectapheleia/avl/issues/93) List(): clear() left the push event set, so a subsequent blocking_pop() did not block and raised `IndexError: pop from empty list`. The push event is now kept aligned with the contents of the list, which also covers the same failure when the list was emptied by pop()/remove(), and when a List was constructed with initial elements (blocking_pop() blocked despite the data being available). blocking_pop() additionally re-checks the list after waking, so a single push no longer releases more than one waiter.

### Changed
 - avl-coverage-analysis: redesigned HTML report as a single self-contained page with AVL/Apheleia branded styling, a searchable hierarchy browser (tests/merged/ranked → covergroups), and a sortable/filterable/searchable covergroup and bin-detail table, replacing the old multi-page DataTables site. The stats scatter-plot popup is now an in-page modal instead of a separate linked file. No more jQuery/DataTables/Plotly CDN dependency, so reports work fully offline.
 - avl-trace-analysis: matched the same branded, sortable/filterable/searchable table styling and dropped the jQuery/DataTables CDN dependency. Added friendlier errors for missing trace files, invalid `--query` expressions, and unknown `--sort` columns (previously raw Python tracebacks). `--sort` now supports descending order via a leading `-` (e.g. `--sort=-data`).

# [v1.0.1] - 2026-08-03

## Fixed
 - SequenceItem(): a SequenceItem parented by a Sequence was silently re-parented to the Sequencer, so its get_full_name() dropped the sequence's name and diverged from the path Object.__new__ uses for set_override_by_instance()/Factory variables. SequenceItem now keeps its real parent, so both paths agree.
 - SequenceItem(): get_root_sequence() looped forever instead of walking up the parent-sequence chain.

# [v1.0.0] - 2026-06-07

## Fixed
 - [#82](https://github.com/projectapheleia/avl/issues/82) Vanilla Template : Issues with sync_reset and ticker
 - [#88](https://github.com/projectapheleia/avl/issues/88) Coverbin(): getstddev asserts if _count_ <=1
 - [#89](https://github.com/projectapheleia/avl/issues/89) IndexedScoreboard(): Ordering of checks can be improved by threading the before and after ports
 - [#90](https://github.com/projectapheleia/avl/issues/90) Object(): manipulation of _auto_random_ can cause false constraint fails
 - [#85](https://github.com/projectapheleia/avl/issues/85) Imports Steps and TimeUnitWithoutSteps from cocotb.simtime will break with cocotb 2.1

## [v0.5.1] - 2026-03-05

### Added
 - [#80](https://github.com/projectapheleia/avl/issues/80) Constraint Debug: Add mechanism to help user debug unsatisfied constraints

## [v0.5.0] - 2026-02-13

### Fixed
 - [#73](https://github.com/projectapheleia/avl/pull/73) Fix pyright lint errors
 - [#71](https://github.com/projectapheleia/avl/issues/71) Object(): kwargs (name, parent) break __new__
 - [#74](https://github.com/projectapheleia/avl/issues/74) Factory overrides carry over from one test to the other.
 - [#72](https://github.com/projectapheleia/avl/issues/72) Non-Uniform Randomization for Gap Constraints
 - [#75](https://github.com/projectapheleia/avl/issues/75) Randomization time increases faster than linear as avl.Var count increases

## [v0.4.3] - 2026-01-23

### Added
 - Added "value" attribute for structs to be more consistent with Vars. No change in behavior. New way of accessing
 - [#69](https://github.com/projectapheleia/avl/issues/69) Struct(): Support slice operations

### Fixed
 - [#64](https://github.com/projectapheleia/avl/pull/64)   fix: Unsupported 'Self' annotation in python 3.10
 - [#67](https://github.com/projectapheleia/avl/pull/67)   fix(example): Adjust constraint to use z3.ULT
 - [#66](https://github.com/projectapheleia/avl/issues/66) Struct(): to_bits and from_bits does not support nested structs
 - [#68](https://github.com/projectapheleia/avl/pull/68) fix(struct): add suport for nested structs in to_bits and from_bits functions

## [v0.4.2] - 2026-01-18

### Added
 - [#62](https://github.com/projectapheleia/avl/pull/62) Add slice support for vars

### Fixed
 - [#60](https://github.com/projectapheleia/avl/issues/60) Object(): deepcopy deepcopies all Objects() (including _parent_). Should just copy (reference)
 - [#61](https://github.com/projectapheleia/avl/issues/61) Object(): deepcopy attempts to deepcopy hdl handles. These don't pickle so fail
 - [#63](https://github.com/projectapheleia/avl/pull/63)   fix(object): Display correct type hint with pyright


## [v0.4.1] - 2026-01-06

### Fixed
 - [#55](https://github.com/projectapheleia/avl/issues/55) Factory(): Compile regexs to improve performance on get_instance and get_variable
 - [#56](https://github.com/projectapheleia/avl/issues/56) Object(): More generic MutableMapping / MutableSequence and Set handling for printing and variable location
 - [#57](https://github.com/projectapheleia/avl/issues/57) Var(): Move z3 creation to randomize stage to improve performance of object creation when randomization is not needed
 - [#58](https://github.com/projectapheleia/avl/issues/58) Object(): Move Logging functions to class variables to improve __init__ performance
 - [#54](https://github.com/projectapheleia/avl/issues/54) Group parameter in bound Log functions
 - [#59](https://github.com/projectapheleia/avl/issues/59) Trace(): Poor formatting of defaultdict / orderedDict i.e. non-native types

## [v0.4.0] - 2025-12-18

### Fixed
 - [#48](https://github.com/projectapheleia/avl/issues/48) Add print_factory() method to Factory class for AVL
 - [#51](https://github.com/projectapheleia/avl/issues/51) Suggested Change: error on same constraint name
 - [#50](https://github.com/projectapheleia/avl/issues/50) Like avl.Logic, avl.Enum assignment values should be typecasted to int
 - [#46](https://github.com/projectapheleia/avl/issues/46) Randomization fails for bitmask constraints
 - [#40](https://github.com/projectapheleia/avl/issues/40) Redundent call to _cast_ in Var
 - [#39](https://github.com/projectapheleia/avl/issues/39) Incovenient Behavior from Logic Assigning from Certain Types
 - [#41](https://github.com/projectapheleia/avl/issues/41) Issue with factory.set_variable
 - [#52](https://github.com/projectapheleia/avl/issues/52) Memory: Support rotated and non-rotated reads and writes for unaligned access

## [v0.3.3] - 2025-10-11

### Fixed
 - [#38](https://github.com/projectapheleia/avl/issues/38) When splitting constraint optimization you can get mixed min / max as constraints not applied atomically

## [v0.3.2] - 2025-10-10

### Fixed
 - [#37](https://github.com/projectapheleia/avl/issues/37) Improve coverage reporting
 - Tidy up of avl.sh to prevent warning on Mac
 - [#35](https://github.com/projectapheleia/avl/issues/35) Randomization of class with many constraints can hang
 - [#36](https://github.com/projectapheleia/avl/issues/36) Default constraint for floats should have been removed

## [v0.3.1] - 2025-10-04

### Fixed
 - [#34](https://github.com/projectapheleia/avl/issues/34) Randomization optimization break ENUM random with != constraint

## [v0.3.0] - 2025-09-20

### Added
 - [#33](https://github.com/projectapheleia/avl/issues/33) Upgrade to cocotb 2.0
 - [#31](https://github.com/projectapheleia/avl/issues/31) Factory(): Make default option for get_variable optional

### Fixed
 - [#32](https://github.com/projectapheleia/avl/issues/32) Object(): use assignment instead of setattr to set logger methods

## [v0.2.2] - 2025-09-09

### Added
- [#21](https://github.com/projectapheleia/avl/issues/21) Export coverage analysis script as part of release

### Fixed
- [#30](https://github.com/projectapheleia/avl/issues/30) Coverbin(): Handle None values
- [#29](https://github.com/projectapheleia/avl/issues/29) Object(): remove_constraints() not working
- [#28](https://github.com/projectapheleia/avl/issues/28) Object(): Randomization performance when randomizing large variable sets with no constraints
- [#27](https://github.com/projectapheleia/avl/issues/27) Trace(): Lists / Dicts containing Vars() not displayed properly
- [#26](https://github.com/projectapheleia/avl/issues/26) Trace(): Empty trace causing error in report_phase()
- [#25](https://github.com/projectapheleia/avl/issues/25) List(): Clear calls push event causing underflow on blocking_pop()

## [v0.2.1] - 2025-08-05

### Added
- [#19](https://github.com/projectapheleia/avl/issues/19) Add helper issue in struct to detect flattened struct and automatically assign / inspect

### Fixed
- [#20](https://github.com/projectapheleia/avl/issues/20) Randomization limited when using hard or soft constraints dynamically
- [#18](https://github.com/projectapheleia/avl/issues/18) Print left in trace.py

## [v0.2.0] - 2025-08-04

### Added
- [#15](https://github.com/projectapheleia/avl/issues/13) Memory Model Required
- [#13](https://github.com/projectapheleia/avl/issues/13) Trace function

### Fixed
- [#14](https://github.com/projectapheleia/avl/issues/14) Factory.get_variable Specificness Algorithm
    - Added specificity function - but public so can be overridden by user if they have a better mechanism
- [#17](https://github.com/projectapheleia/avl/issues/17) avl.sh doesn't work on macos
- [#16](https://github.com/projectapheleia/avl/issues/16) Uint32 randomized incorrectly - inherits from Logic not Uint
- [#11](https://github.com/projectapheleia/avl/issues/11) Vars have a 'name' attribute whose purpose is unclear
    - Backwards compatible - users will get deprecated warning only
- [#10](https://github.com/projectapheleia/avl/issues/10) Implement setter for the 'value' field of each Var type
- [#9](https://github.com/projectapheleia/avl/issues/9) Cannot access struct fields when using Verilator

## [v0.1.2] - 2025-06-30

### Added
- Examples use symlink to common Makefile for easier maintenance

### Fixed
- [#5](https://github.com/projectapheleia/avl/issues/5) atexit not called by Questa or VCS. Flush log fails at end of sim
- [#6](https://github.com/projectapheleia/avl/issues/6) Copying of sized int and uint fails due to missing width parameter
- [#7](https://github.com/projectapheleia/avl/issues/7) Example makefiles not compatible with Questa and VCS

## [v0.1.1] - 2025-06-26

### Added
- [#4](https://github.com/projectapheleia/avl/issues/4) Improve printing of objects

### Fixed
- [#2](https://github.com/projectapheleia/avl/issues/2) Ticker calling self.log (deprecated function)
- [#3](https://github.com/projectapheleia/avl/issues/3) Copy enum fails due to addition values parameter in __init__

## [v0.1.0] - 2025-06-19

### Added
- First public release.
