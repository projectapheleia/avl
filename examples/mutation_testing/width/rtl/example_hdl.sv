// Copyright 2026 Apheleia
//
// Description:
// Synthetic RTL for the AVL mutation testing "width" example.
//
// An internal sum one bit wider than its inputs. Taking a bit off it
// loses the carry, which is the classic bus declared too narrow.
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

    logic [8:0] total;

    always_comb begin
        total = a + b;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            y         <= '0;
        end
        else begin
            valid_out <= valid_in;
            y         <= total;
        end
    end

endmodule : example_hdl
