// Copyright 2026 Apheleia
//
// Description:
// Synthetic RTL for the AVL mutation testing "array_packed" example.
//
// A bit reversal. Which bit rev[i] names depends on how rev is
// declared, so turning a packed dimension around renumbers the bits
// and the reversal quietly stops happening.
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

    logic [7:0] rev;

    always_comb begin
        for (int i = 0; i < 8; i++) begin
            rev[i] = a[7-i] ^ b[i];
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            y         <= '0;
        end
        else begin
            valid_out <= valid_in;
            y         <= {1'b0, rev};
        end
    end

endmodule : example_hdl
