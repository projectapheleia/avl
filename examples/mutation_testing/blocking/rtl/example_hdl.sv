// Copyright 2026 Apheleia
//
// Description:
// Synthetic RTL for the AVL mutation testing "blocking" example.
//
// A two stage pipeline. Each stage is read by the stage below it in the same
// block, so a nonblocking assignment hands over last cycle's value and a
// blocking one hands over this cycle's - turning either into a blocking
// assignment collapses a stage and the answer arrives a cycle early.
//
// The pipeline is what makes the defect visible at all. A nonblocking
// assignment nobody reads again in the same block is indistinguishable from a
// blocking one, which is why the class only offers an assignment whose target
// is read below it.
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

    logic       valid_d;
    logic[7:0]  data_d;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_d   <= 1'b0;
            valid_out <= 1'b0;
            data_d    <= '0;
            y         <= '0;
        end
        else begin
            valid_d   <= valid_in;
            valid_out <= valid_d;
            data_d    <= a ^ b;
            y         <= {1'b0, data_d};
        end
    end

endmodule : example_hdl
