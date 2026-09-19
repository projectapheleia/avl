// Copyright 2026 Apheleia
//
// Description:
// Synthetic RTL for the AVL mutation testing "bitwise" example.
//
// An and, an or and an xor, so the bitwise class has a site of each.
//
// Deliberately tiny. It exists so that one class of defect can be seen on its
// own, against a testbench small enough to read in one sitting.

module example_hdl(
    input  logic       clk,
    input  logic       rst_n,
    input  logic       valid_in,
    input  logic [7:0]  a,
    input  logic [7:0]  b,
    output logic       valid_out,
    output logic [8:0]  y
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            y         <= '0;
        end
        else begin
            valid_out <= valid_in;
            y         <= {1'b0, (a & b) ^ (a | b)};
        end
    end

endmodule : example_hdl
