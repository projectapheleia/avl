// Copyright 2026 Apheleia
//
// Description:
// Synthetic RTL for the AVL mutation testing "array_unpacked" example.
//
// A lookup table filled by an assignment pattern. The pattern fills
// the array in declaration order, so turning the unpacked dimension
// around reverses which element gets which value.
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

    logic [7:0] lut [0:3];

    always_comb begin
        lut = '{8'd10, 8'd20, 8'd30, 8'd40};
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            y         <= '0;
        end
        else begin
            valid_out <= valid_in;
            y         <= {1'b0, lut[a[1:0]]};
        end
    end

endmodule : example_hdl
