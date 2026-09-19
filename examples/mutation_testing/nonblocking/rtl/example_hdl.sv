// Copyright 2026 Apheleia
//
// Description:
// Synthetic RTL for the AVL mutation testing "nonblocking" example.
//
// Two blocking temporaries in a clocked block, both read by the
// registered output below them. Turning either into a nonblocking
// assignment hands the output last cycle's value instead of this
// one - the classic reason a blocking temp must stay blocking.
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

    logic [7:0] sum;
    logic [7:0] dif;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            y         <= '0;
        end
        else begin
            valid_out <= valid_in;
            sum       = a + b;
            dif       = a - b;
            y         <= {1'b0, sum ^ dif};
        end
    end

endmodule : example_hdl
