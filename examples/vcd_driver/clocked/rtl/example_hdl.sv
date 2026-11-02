module example_hdl(
    input  logic       clk,
    input  logic       rst_n,
    input  logic       valid_in,
    input  logic[7:0]  a,
    input  logic[7:0]  b,
    output logic       valid_out,
    output logic[8:0]  c
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            valid_out <= 1'b0;
            c         <= '0;
        end
        else begin
            if (valid_in) begin
                valid_out <= 1'b1;
                c         <= a + b;
            end
            else begin
                valid_out <= 1'b0;
            end
        end
    end

endmodule : example_hdl
