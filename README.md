# AVL - Apheleia Verification Library

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.7%2B-blue)](https://www.python.org/)


AVL has been developed by experienced, industry professional verification engineers to provide a methodology \
and library of base classes for developing functional verification environments in [Python](https://www.python.org/).

AVL is built on the [CocoTB](https://docs.cocotb.org/en/stable/) framework, but aims to combine the best elements of \
[UVM](https://accellera.org/community/uvm) in a more engineer friendly and efficient way.


## CocoTB 2.0

AVL now supports CocoTB2.0 https://docs.cocotb.org/en/development/upgrade-2.0.html. This was introduced in v0.3.0.

All older versions support v1.9.1 and will fail if run with CocoTB 2.0.

To upgrade follow the instructions given on the link above.

---

## 🧬 Mutation Testing

Coverage tells you the testbench *ran* a line. It does not tell you the testbench would have *noticed* had that line been wrong.

[Mutation testing](https://en.wikipedia.org/wiki/Mutation_testing) — known in hardware as functional qualification — answers the second question. `avl-mutation-testing` takes your golden RTL, writes out a set of copies each carrying exactly one deliberate defect, and re-runs your existing tests against every one. A mutant the tests still pass is a hole in the verification environment: a class of bug that could ship unnoticed. The testbench needs no knowledge of any of this — a mutant is ordinary RTL that happens to be wrong.

```sh
avl-mutation-testing --source rtl/*.sv --top my_module --types arith,compare --count 10
```

### Supported mutations

Classes are selected with `--types`, and `avl-mutation-testing --list-types` prints them with the syntax each one matches.

| Class | Mutation | Example |
| --- | --- | --- |
| `arith` | Swaps an arithmetic operator | `a + b` → `a - b` |
| `bitwise` | Swaps a bitwise operator | `a & b` → `a \| b` |
| `compare` | Swaps a comparison | `a < b` → `a <= b` |
| `logical` | Swaps a logical operator | `a && b` → `a \|\| b` |
| `shift` | Swaps a shift direction | `a << 1` → `a >> 1` |
| `unary` | Removes a unary operator | `~a` → `a` |
| `operand` | Reverses a non-commutative operator's operands | `a - b` → `b - a` |
| `condition` | Holds a branch open, holds it shut, and nudges the comparisons it is built from | `if (en)` → `if (1'b1)`, `if (1'b0)` |
| `statement` | Drops a registered assignment, so the register holds | `y <= d;` → `;` |
| `pipeline` | Gives a registered signal an extra stage, so it arrives a cycle late | `y <= d;` → `y` one cycle late |
| `sign` | Negates the value assigned to a signed variable | `y = a + 1;` → `y = -(a + 1);` |
| `width` | Takes the top bit off a packed declaration | `logic [8:0] t` → `logic [7:0] t` |
| `array_packed` | Reverses a packed dimension, renumbering the bits | `logic [7:0] a` → `logic [0:7] a` |
| `array_unpacked` | Reverses an unpacked dimension, reordering the elements | `logic a [0:3]` → `logic a [3:0]` |
| `blocking` | Makes a nonblocking assignment blocking | `x <= a;` → `x = a;` |
| `nonblocking` | Makes a blocking assignment nonblocking | `x = a;` → `x <= a;` |

Every line a mutation changes carries an `/* AVL MUTATION - ... */` comment, so a mutant that turns up in an editor, a debugger or a waveform cannot be mistaken for the golden source. Generation also writes `mutations.html`, a report explaining each mutation in its source context.

### Equivalent mutants

Some defects cannot change behaviour — flipping the `+` in `a + 0` to a `-` is still `a`. No testbench can ever catch those, so scoring them as survivors reports verification holes that are not there. Where [Yosys](https://yosyshq.net/yosys/) is installed each mutation is proved to change the design before any simulation time is spent on it, and the ones that do not are reported as equivalent and left out of the score. Yosys is optional; without it the stage is skipped.

### Background and tools

| Link | |
| --- | --- |
| [Mutation testing](https://en.wikipedia.org/wiki/Mutation_testing) | Overview of the technique |
| [Hints on Test Data Selection](https://doi.org/10.1109/C-M.1978.218136) | DeMillo, Lipton & Sayward, *IEEE Computer* 11(4), 1978 — where the idea starts |
| [An Analysis and Survey of the Development of Mutation Testing](https://doi.org/10.1109/TSE.2010.62) | Jia & Harman, *IEEE Transactions on Software Engineering* 37(5) — the standard survey |
| [pyslang](https://pypi.org/project/pyslang/) / [slang](https://github.com/MikePopoloski/slang) | SystemVerilog frontend used to locate mutation sites |
| [Yosys](https://yosyshq.net/yosys/) | Proves each mutation changes the design |
| [CocoTB](https://docs.cocotb.org/en/stable/) | Runs the testbench against each mutant |
| [Verilator](https://www.veripool.org/verilator/) | Default simulator for the examples |

Nineteen worked examples live under [examples/mutation_testing](examples/mutation_testing), one per mutation class plus a hierarchical ALU, a synchronous FIFO, and a design with a provably equivalent mutant. See [its README](examples/mutation_testing/README.md) for the full walkthrough, and [the documentation](doc/source/mutation_testing/mutation_testing.rst) for the complete option reference.

---

## 📦 Installation

### Using `pip`
```sh
# Standard build
pip install avl-core

# Development build
pip install avl-core[dev]
```

### Install from Source
```sh
git clone https://github.com/projectapheleia/avl.git
cd avl

# Standard build
pip install .

# Development build
pip install .[dev]
```

Alternatively if you want to create a [virtual environment](https://docs.python.org/3/library/venv.html) rather than install globally a script is provided. This will install, with edit privileges to local virtual environment.

This script assumes you have  [Verilator](https://www.veripool.org/verilator/), [GTKWave](https://gtkwave.sourceforge.net/) and [Graphviz](https://graphviz.org/download/) installed, so all examples and documentation will build out of the box. [Yosys](https://yosyshq.net/yosys/) is optional; the mutation testing examples use it to prove each mutation changes the design, and skip that stage without it. The script warns about anything it cannot find.


```sh
git clone https://github.com/projectapheleia/avl.git
cd avl
source avl.sh
```

## 📖 Documentation

In order to build the documentation you must have installed the development build.

### Build from Source
```sh
cd docs
make html
<browser> build/html/index.html
```
## 🏃 Examples

In order to run all the examples you must have installed the development build.

To run all examples:

```sh
cd examples

# To run
make -j 8 sim

# To clean
make -j 8 clean
```

To run an individual example:

```sh
cd examples/THE EXAMPLE YOU WANT

# To run
make sim

# To clean
make clean
```

The examples use the [CocoTB Makefile](https://docs.cocotb.org/en/stable/building.html) and default to [Verilator](https://www.veripool.org/verilator/) with all waveforms generated. This can be modified using the standard CocoTB build system.

>**WARNING**:
>Due to [GNU Make not exporting variables not already in env](https://www.gnu.org/software/make/manual/make.html#Environment) the user must ensure PYTHONPATH is set in the environment.
>If you have sourced the avl.sh this is done for you.

---


## 🧹 Code Style & Linting

This project uses [**Ruff**](https://docs.astral.sh/ruff/) for linting and formatting.

Check code for issues:

```sh
ruff check .
```

Automatically fix common issues:

```sh
ruff check . --fix
```

## Additional Libraries / UVCs

| Library | Description |
|---------|-------------|
|[avl-ral](https://github.com/projectapheleia/avl-ral)| Register Abstraction Layer |
|[avl-qemu](https://github.com/projectapheleia/avl-qemu)| QEMU Integration |
|[avl-apb](https://github.com/projectapheleia/avl-apb)| AMBA APB UVC |
|[avl-axi-stream](https://github.com/projectapheleia/avl-axi-stream)| AMBA AXI-STREAM UVC |
|[avl-axi](https://github.com/projectapheleia/avl-axi)| AMBA AXI5 UVC |
|[avl-jtag](https://github.com/projectapheleia/avl-jtag)| JTAG UVC |
|[avl-spi](https://github.com/projectapheleia/avl-spi)| SPI UVC |
|[avl-riscv-coverage](https://github.com/projectapheleia/avl-riscv-coverage) | RISCV Coverage collection from trace framework |
|[avl-tutorials](https://github.com/projectapheleia/avl-tutorials) | AVL Tutorials and introduction presentations |

## 📧 Contact

- Email: avl@projectapheleia.net
- GitHub: [projectapheleia](https://github.com/projectapheleia)
