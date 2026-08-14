# Changelog

## [Unreleased]

### Added
 - `avl.urandom_range(lo, hi)`: uniform random integer in the inclusive range [lo, hi], the same draw AVL uses internally for an unconstrained value. Equivalent to `random.randint` but 2-3x faster, and the closest analogue to SystemVerilog's `$urandom_range`.
 - `benchmarks/randomize_and_send/bitwise_128`: a single benchmark covering both of the other groups at once - an item of 128 variables carrying the `bitwise` constraints, randomized and then driven onto 128 signals, once per clock edge - for an overall impression of what a transaction costs when nothing about it is separable. Read against the two groups below it, it shows that the solve is the larger part of a transaction by roughly two orders of magnitude, and that AVL is alone in trading a per constraint shape setup cost (a one-off couple of seconds on an item this wide, from working out which bits the constraints pin) for a materially lower steady state - so which implementation is fastest depends on how many transactions of a shape the test runs.
 - `benchmarks/create_and_send`: a second group of benchmarks, measuring what it costs a testbench to build one transaction object and drive it onto the RTL, once per clock edge, with nothing randomized - swept over 1, 8, 32 and 64 signals so that the fixed cost of a transaction separates from the per-field and per-signal-write cost. Compared against SystemVerilog and pyuvm the same way the randomization benchmarks are, from the same harness, and reported by the same report generator. The framework gained what the group needed: `BENCH_SOURCE_DIR`, so benchmarks that differ only in configuration share one model and testbench; `BENCH_QUALITY`, so a benchmark that randomizes nothing skips the quality runs; and `BENCH_UNIT`, recorded with every timing row, so a report is written in the terms of what it measured rather than always in terms of randomization.

### Changed
 - Item creation performance: a field object costs roughly a third of what it did, and an item of 64 fields half. A testbench builds a fresh sequence item per transaction, so what an item costs is paid per transaction, and `benchmarks/create_and_send` showed it was almost entirely the field objects rather than the item or the signal writes: at 64 signals **151.7 us to 77.6 us** per item, and 1.50x at one signal rising to 1.96x at 64 as the per-field part comes to dominate. A four field item is **6.5 us to 2.2 us**. Four changes, all of them about not doing work when an item is built that only a solve or a constraint ever needs: `Var._register_` no longer hands out an index in `Var._lookup_` to every variable ever built, because only a randomization reads it, so an index is assigned on first use and `Object.randomize` asks for it; `_constraints_` is created by `add_constraint` rather than as a pair of empty dictionaries per field; the mask a width implies is computed once and kept as `_mask_` rather than rebuilt through `_range_()` on every assignment; and `Logic`, `Uint` and `Int` no longer define `__init__`, so a fixed point variable is built in one constructor frame instead of up to five - what a level of that hierarchy contributes now is class attributes (`width`/`_mask_` where the width is fixed, and `_fmt_default_`), which is also how the defaults an instance does not differ from are kept off it. **Distributions are unchanged, and provably so**: every one of the 18 quality dumps across the six randomization benchmarks and three flavours is byte identical before and after, so every value drawn, in order, is the same. `randomize()` itself is unchanged too (1257 us against 1280 us on `arithmetic`, best case identical) - the solver dominates it by three orders of magnitude - though it does one thing less per variable, the two `Var._lookup_` round trips per variable per solve having gone with the eager registration. Visible from the outside only in that `inspect.signature(avl.Logic)` now reports `Var.__init__`, whose `fmt` and `width` default to `None` meaning "whatever this class says", and that an unconstrained variable's `_constraints_` is `None` rather than `{True: {}, False: {}}`. Making `_auto_random_` and `_fmt_` class attributes in the same way was tried and rejected: it measured 4% *slower*, because the conditional needed to skip the store costs more than the store, and it would make every fallback read 75% dearer - including `_auto_random_`, which is read per variable per solve.
 - Randomization performance: z3 variables are now pooled by their sort and their position in the solve rather than created one per `Var` instance, so the expressions built over them - the per-bit randomization clauses, and an analysis of which bits the constraints pin - are built once per shape of object instead of once per `randomize()`. Bits that the hard constraints pin to a single value no longer get a randomization clause, which is what most of the gain comes from. Measured against a fresh object per randomization: `cross` 2.89x, `bitwise` 2.12x, `implication` 1.66x, `list` and `mixed` 1.40x, `arithmetic` 1.37x. **Distributions are unchanged** - a pinned bit's clause is either always satisfied or always violated, so dropping it shifts every candidate solution's score by the same constant and cannot change which are optimal. Sharing a z3 variable between objects is safe because a variable is a name in a formula rather than storage, and each `randomize()` asserts one object's constraints into a solver of its own; see `Randomization Performance` in the documentation for the argument in full, and `benchmarks/` for the measurement of distribution quality that guards it.
 - Randomization performance: randomization clauses are no longer spent on bits the constraints will not grant alongside the rest. The free bit analysis above drops bits pinned to a constant - the bits with no choice at all - but cannot see that the bits it leaves may still not be free to combine, constraints routinely allowing far fewer combinations of them than their count suggests. Twelve free bits span 4096 combinations, so on a field the constraints hold to a few hundred legal values a clause per free bit describes a combination that is usually not legal, and some of those clauses then have to be given up - which core guided MaxSMT does a core at a time, running a round per core, so the search lengthens with the number of clauses that must be given up. Each constraint shape is now measured over its first few randomizations - the solution to compare against is already in hand, so this costs one shift and compare per clause - and a clause plan is then frozen per variable: the bits granted reliably are always asked about, and a random subset of the contested ones is drawn each time. Measured on `cross`, the one benchmark where cross-variable constraints dominate: **1.22x**, with `bitwise`, `arithmetic` and `mixed` unchanged at 1.00x. Unlike the pinned bit analysis this is a heuristic rather than a distribution-preserving identity, so it is measured rather than argued: `cross` per-field entropy moves by at most 0.006 and per-bit proportions by at most 0.044 (the quality gate allows 0.10 and 0.20 respectively), and any variable with nothing worth rationing keeps every free bit and is left exactly as it was - which is every variable of `bitwise` and `arithmetic`, and all of `mixed` bar `attr`. Whether a variable is rationed is decided by that measurement and not by how many variables its constraints mention: a single-variable range forbids combinations of otherwise free bits too, just mildly enough that the plan usually collapses back to every free bit. Because a soft constraint competes with the randomization clauses for the same objective, the object's own soft constraints have been added to the analysis cache key, so that two shapes sharing only their hard constraints no longer share a plan. Constraints passed to `randomize(hard=...)`/`(soft=...)` are added after that key is taken and cannot be covered by it, and unlike the pinned bit analysis a plan cannot be carried across them regardless: pinning a bit only removes a clause whose effect was constant, whereas declining to ask about a contested bit changes which solutions are optimal. Such a solve therefore neither uses a plan nor teaches one, and asks about every free bit as before. A given seed produces a different stimulus sequence to before, for the same reason as the getrandbits change below.
 - Randomization performance: unconstrained values (Var._random_value_) and the per-bit soft constraints on Logic/Fp16/Fp32/Fp64 are now drawn with random.getrandbits instead of random.randint. Var._random_value_() is roughly 2-3x faster; the per-bit draw is 4-6x faster. Distributions are unchanged and still uniform, and random.seed() reproducibility is preserved - but because getrandbits consumes the Mersenne Twister stream differently to randint, a given seed produces a different stimulus sequence to v1.0.1 and earlier. Seeds recorded against older releases will not replay the same values.
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
