// Copyright 2026 Apheleia
//
// Description:
// Apheleia Verification Library (AVL) comparison benchmark.
//
// The harness every flavour of the benchmark runs: a clock, a reset and a
// cycle counter, driven from the cocotb testbench in ../cocotb/benchmark.py.
// One item is created, constrained and randomized per rising edge.
//
// Who does that work is the only thing that differs, and it is the only thing
// inside the `ifdef below:
//
//   sv                   the classes in classes.svh, randomized by the
//                        simulator's own constraint solver
//   everything else      the identical classes in Python, randomized in the
//                        cocotb testbench
//
// classes.svh is `include`d here, inside the module, so that the run_item task
// it declares can reach checksum and count.

`timescale 1ns/1ps

module comparison_bench (
    input logic clk,
    input logic rst_n
);

    // Common to every flavour - lets the testbench confirm that all of them ran
    // for the same number of clock cycles.
    int unsigned cycles = 0;

    always @(posedge clk) begin
        if (!rst_n) begin
            cycles <= 0;
        end
        else begin
            cycles <= cycles + 1;
        end
    end

`ifdef BENCH_SV
    // -----------------------------------------------------------------------
    // The work under test - SystemVerilog classes and constraints.
    // -----------------------------------------------------------------------

    // Declared before the classes, whose run_item task accumulates into them.
    longint unsigned checksum = 0;
    int unsigned     count    = 0;

    bit              enable   = 1'b1;
    int unsigned     burst    = 1;

`include "classes.svh"

    // How many of the classes take part. Every class is compiled in, so one
    // model serves any count, and the default is all of them.
    int unsigned     classes  = BENCH_CLASSES;

    initial begin
        // Cleared for the baseline run, which measures the harness on its own.
        void'($value$plusargs("work=%d", enable));
        void'($value$plusargs("burst=%d", burst));
        void'($value$plusargs("classes=%d", classes));

        if (classes < 1 || classes > BENCH_CLASSES) begin
            $fatal(1, "classes must be between 1 and %0d, not %0d", BENCH_CLASSES, classes);
        end
    end

    always @(posedge clk) begin
        if (rst_n && enable) begin
            repeat (burst) begin
                // The classes are taken in turn, so a run of N iterations over
                // N classes builds one item of each.
                run_item(count % classes);
            end
        end
    end

    final begin
        $display("BENCH_RESULT flavour=sv iterations=%0d checksum=%0d", count, checksum);
    end
`endif

endmodule : comparison_bench
