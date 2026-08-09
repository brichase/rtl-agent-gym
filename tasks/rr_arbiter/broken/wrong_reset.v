`timescale 1ns/1ps

module rr_arbiter (
    input wire clk,
    input wire rst_n,
    input wire [3:0] req,
    output reg [3:0] grant
);
    reg [1:0] last_grant;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin grant <= 0; last_grant <= 3; end
        else begin
            grant <= 0;
            case (last_grant)
                0: if(req[1]) begin grant<=2;last_grant<=1;end else if(req[2]) begin grant<=4;last_grant<=2;end else if(req[3]) begin grant<=8;last_grant<=3;end else if(req[0]) begin grant<=1;last_grant<=0;end
                1: if(req[2]) begin grant<=4;last_grant<=2;end else if(req[3]) begin grant<=8;last_grant<=3;end else if(req[0]) begin grant<=1;last_grant<=0;end else if(req[1]) begin grant<=2;last_grant<=1;end
                2: if(req[3]) begin grant<=8;last_grant<=3;end else if(req[0]) begin grant<=1;last_grant<=0;end else if(req[1]) begin grant<=2;last_grant<=1;end else if(req[2]) begin grant<=4;last_grant<=2;end
                3: if(req[0]) begin grant<=1;last_grant<=0;end else if(req[1]) begin grant<=2;last_grant<=1;end else if(req[2]) begin grant<=4;last_grant<=2;end else if(req[3]) begin grant<=8;last_grant<=3;end
            endcase
        end
    end
endmodule
