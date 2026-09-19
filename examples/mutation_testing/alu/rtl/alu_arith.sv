// Copyright 2026 Apheleia
//
// Description:
// Adder / subtractor for the mutation testing ALU example.
//
// Holds the example's two arith mutation sites.

module alu_arith(
    input  logic[7:0]  a,
    input  logic[7:0]  b,
    input  logic       sub,
    output logic[8:0]  y
);

    always_comb begin
        if (sub) begin
            y = a - b;
        end
        else begin
            y = a + b;
        end
    end

endmodule : alu_arith
