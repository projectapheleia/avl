// Copyright 2026 Apheleia
//
// Description:
// Synthetic RTL for the AVL mutation testing "equivalent" example.
//
// A negative test for the equivalence check. Adding zero is a no-op,
// so the mutation that turns it into a subtract changes the source
// without changing the design. No testbench can ever catch that, and
// reporting it as a survivor would invent a verification hole. The
// xor beside it is an ordinary mutation that should be caught, so the
// example shows the two outcomes side by side.
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

    logic [7:0] pass_through;

    always_comb begin
        pass_through = a + 8'd0;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            y         <= '0;
        end
        else begin
            valid_out <= valid_in;
            y         <= {1'b0, pass_through ^ b};
        end
    end

endmodule : example_hdl
