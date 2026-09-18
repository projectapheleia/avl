// Copyright 2026 Apheleia
//
// Description:
// Simple synchronous FIFO, used to demonstrate AVL mutation testing.
//
// This is plain, unmodified RTL. avl-mutation-testing generates the mutants
// from it with --types arith, which yields exactly three sites: the occupancy
// subtract and the two pointer increments.

module example_hdl #(
    parameter int WIDTH = 8,
    parameter int DEPTH = 8
)(
    input  logic             clk,
    input  logic             rst_n,
    input  logic             push,
    input  logic[WIDTH-1:0]  wdata,
    input  logic             pop,
    output logic[WIDTH-1:0]  rdata,
    output logic             full,
    output logic             empty
);

    localparam int AW = $clog2(DEPTH);

    logic[WIDTH-1:0] mem [DEPTH];
    logic[AW:0]      wptr;
    logic[AW:0]      rptr;
    logic[AW:0]      level;

    assign level = wptr - rptr;
    assign empty = (level == '0);
    assign full  = (level == (AW+1)'(DEPTH));
    assign rdata = mem[rptr[AW-1:0]];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wptr <= '0;
            rptr <= '0;
        end
        else begin
            if (push && !full) begin
                mem[wptr[AW-1:0]] <= wdata;
                wptr              <= wptr + 1'b1;
            end

            if (pop && !empty) begin
                rptr <= rptr + 1'b1;
            end
        end
    end

endmodule : example_hdl
