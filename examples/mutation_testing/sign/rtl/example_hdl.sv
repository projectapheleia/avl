// Copyright 2026 Apheleia
//
// Description:
// Synthetic RTL for the AVL mutation testing "sign" example.
//
// Signed ports and a signed intermediate. The sign class negates the
// value assigned to a signed variable, and only to a signed one.
//
// Deliberately tiny. It exists so that one class of defect can be seen on its
// own, against a testbench small enough to read in one sitting.

module example_hdl(
    input  logic       clk,
    input  logic       rst_n,
    input  logic       valid_in,
    input  logic signed [7:0]  a,
    input  logic signed [7:0]  b,
    output logic       valid_out,
    output logic signed [8:0]  y
);

    logic signed [8:0] sum;

    always_comb begin
        sum = a + b;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            y         <= '0;
        end
        else begin
            valid_out <= valid_in;
            y         <= sum;
        end
    end

endmodule : example_hdl
