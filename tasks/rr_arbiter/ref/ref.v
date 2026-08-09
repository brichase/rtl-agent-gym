`timescale 1ns/1ps

module rr_arbiter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [3:0] req,
    output reg  [3:0] grant
);
    reg [1:0] last_grant;

    always @(posedge clk) begin
        if (!rst_n) begin
            grant <= 4'b0000;
            last_grant <= 2'd3;
        end else begin
            grant <= 4'b0000;
            case (last_grant)
                2'd0: begin
                    if (req[1]) begin grant <= 4'b0010; last_grant <= 2'd1; end
                    else if (req[2]) begin grant <= 4'b0100; last_grant <= 2'd2; end
                    else if (req[3]) begin grant <= 4'b1000; last_grant <= 2'd3; end
                    else if (req[0]) begin grant <= 4'b0001; last_grant <= 2'd0; end
                end
                2'd1: begin
                    if (req[2]) begin grant <= 4'b0100; last_grant <= 2'd2; end
                    else if (req[3]) begin grant <= 4'b1000; last_grant <= 2'd3; end
                    else if (req[0]) begin grant <= 4'b0001; last_grant <= 2'd0; end
                    else if (req[1]) begin grant <= 4'b0010; last_grant <= 2'd1; end
                end
                2'd2: begin
                    if (req[3]) begin grant <= 4'b1000; last_grant <= 2'd3; end
                    else if (req[0]) begin grant <= 4'b0001; last_grant <= 2'd0; end
                    else if (req[1]) begin grant <= 4'b0010; last_grant <= 2'd1; end
                    else if (req[2]) begin grant <= 4'b0100; last_grant <= 2'd2; end
                end
                default: begin
                    if (req[0]) begin grant <= 4'b0001; last_grant <= 2'd0; end
                    else if (req[1]) begin grant <= 4'b0010; last_grant <= 2'd1; end
                    else if (req[2]) begin grant <= 4'b0100; last_grant <= 2'd2; end
                    else if (req[3]) begin grant <= 4'b1000; last_grant <= 2'd3; end
                end
            endcase
        end
    end
endmodule
