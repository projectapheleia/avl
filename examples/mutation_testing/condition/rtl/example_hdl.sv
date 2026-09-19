// Copyright 2026 Apheleia
//
// Description:
// Synthetic RTL for the AVL mutation testing "condition" example.
//
// Six branch decisions, one per comparison operator, so that every mutation
// the condition class can make is on show. Three are written as if statements
// and three as conditional expressions, because a predicate of either shape is
// a branch decision and both are mutated.
//
// Each decision yields three mutations: the branch held permanently open, held
// permanently shut, and its comparison nudged to the neighbouring one. That is
// eighteen in all.
//
// The arms have to disagree at the boundary for the nudge to be worth
// anything - had gt been "a > b ? a : b" it would be a max(), and a max is the
// same whichever way the boundary falls. Here each arm is a fixed one or zero,
// so > and >= differ whenever a equals b, and the sequence drives that case on
// purpose rather than waiting to stumble across it.
//
// Deliberately tiny. It exists so that one class of defect can be seen on its
// own, against a testbench small enough to read in one sitting.

module example_hdl(
    input  logic       clk,
    input  logic       rst_n,
    input  logic       valid_in,
    input  logic[7:0]  a,
    input  logic[7:0]  b,
    output logic       valid_out,
    output logic[8:0]  y
);

    logic gt;
    logic ge;
    logic lt;
    logic le;
    logic eq;
    logic ne;

    // Predicates of an if statement.
    always_comb begin
        if (a > b) begin
            gt = 1'b1;
        end
        else begin
            gt = 1'b0;
        end

        if (a >= b) begin
            ge = 1'b1;
        end
        else begin
            ge = 1'b0;
        end

        if (a < b) begin
            lt = 1'b1;
        end
        else begin
            lt = 1'b0;
        end
    end

    // Predicates of a conditional expression.
    assign le = (a <= b) ? 1'b1 : 1'b0;
    assign eq = (a == b) ? 1'b1 : 1'b0;
    assign ne = (a != b) ? 1'b1 : 1'b0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            y         <= '0;
        end
        else begin
            valid_out <= valid_in;
            y         <= {3'd0, ne, eq, le, lt, ge, gt};
        end
    end

endmodule : example_hdl
