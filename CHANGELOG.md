# Changelog

### Fixed
 - [#51](https://github.com/projectapheleia/avl/issues/51) Suggested Change: error on same constraint name
 - [#50](https://github.com/projectapheleia/avl/issues/50) Like avl.Logic, avl.Enum assignment values should be typecasted to int
 - [#46](https://github.com/projectapheleia/avl/issues/46) Randomization fails for bitmask constraints
 - [#40](https://github.com/projectapheleia/avl/issues/40) Redundent call to _cast_ in Var
 - [#39](https://github.com/projectapheleia/avl/issues/39) Incovenient Behavior from Logic Assigning from Certain Types
 - [#41](https://github.com/projectapheleia/avl/issues/41) Issue with factory.set_variable

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
