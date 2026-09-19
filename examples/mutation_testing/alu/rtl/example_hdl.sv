// Copyright 2026 Apheleia
//
// Description:
// Registered ALU, used to demonstrate AVL mutation testing across a design
// built from more than one file.
//
// This is plain, unmodified RTL. avl-mutation-testing is pointed at all three
// files and mutates each of them in turn:
//
//   rtl/alu_arith.sv    the add and the subtract        (arith)
//   rtl/alu_logic.sv    the and and the xor             (bitwise)
//   rtl/example_hdl.sv  the zero flag comparison        (compare)
//                       a cycle of delay on the outputs (pipeline)
//
// Every mutant is a complete copy of all three files with one of them changed,
// so the build never has to know which file a mutation landed in.

module example_hdl(
    input  logic       clk,
    input  logic       rst_n,
    input  logic       valid_in,
    input  logic[7:0]  a,
    input  logic[7:0]  b,
    input  logic[1:0]  op,
    output logic       valid_out,
    output logic[8:0]  result,
    output logic       zero
);

    localparam logic[1:0] OP_ADD = 2'b00;
    localparam logic[1:0] OP_SUB = 2'b01;
    localparam logic[1:0] OP_AND = 2'b10;

    logic[8:0] arith_out;
    logic[8:0] logic_out;
    logic[8:0] alu_out;

    // op[0] selects within each unit: 01 subtracts, 11 exclusive ors.
    alu_arith u_arith (
        .a   (a),
        .b   (b),
        .sub (op[0]),
        .y   (arith_out)
    );

    alu_logic u_logic (
        .a       (a),
        .b       (b),
        .use_xor (op[0]),
        .y       (logic_out)
    );

    always_comb begin
        case (op)
            OP_ADD:  alu_out = arith_out;
            OP_SUB:  alu_out = arith_out;
            OP_AND:  alu_out = logic_out;
            default: alu_out = logic_out;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            result    <= '0;
            zero      <= 1'b0;
        end
        else begin
            valid_out <= valid_in;
            result    <= alu_out;
            zero      <= (alu_out == '0);
        end
    end

endmodule : example_hdl
