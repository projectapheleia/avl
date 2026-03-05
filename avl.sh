#!/bin/bash

# Environment setup
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export AVL_ROOT="$SCRIPT_DIR"

# Graphviz setup
if ! command -v dot &> /dev/null
then
    echo "WARNING : Graphviz could not be found. Please install Graphviz and ensure it is in your PATH (see https://graphviz.org/download/) if you want to generate docs and run all examples."
fi

# Python setup

pushd $AVL_ROOT 1>/dev/null

python_packages=(\
".[dev]"
)

python3 -m venv venv
source ./venv/bin/activate
for p in ${python_packages[@]}; do
    python3 -m pip install --editable $p
done

popd 1>/dev/null

# Default Simulation setup
export CXXFLAGS=${CXXFLAGS:--std=c++17}
export PYTHONPATH=${PYTHONPATH}
export SIM=${SIM:-verilator}
export TOPLEVEL_LANG=${TOPLEVEL_LANG:-verilog}
