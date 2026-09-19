// Copyright 2026 Apheleia
//
// Description:
// Bitwise unit for the mutation testing ALU example.
//
// Holds the example's two bitwise mutation sites.

module alu_logic(
    input  logic[7:0]  a,
    input  logic[7:0]  b,
    input  logic       use_xor,
    output logic[8:0]  y
);

    always_comb begin
        if (use_xor) begin
            y = {1'b0, a ^ b};
        end
        else begin
            y = {1'b0, a & b};
        end
    end

endmodule : alu_logic
