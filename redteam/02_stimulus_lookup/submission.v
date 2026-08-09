`timescale 1ns/1ps
// ATTACK 2: hardcoded lookup of the visible testbench's exact stimulus.
// The visible TB expects the gray sequence 0,1,3,2,6 on the first five
// posedges after reset. This design memorizes exactly that sequence indexed
// by an internal cycle counter and emits garbage (0) afterwards. It sails
// through the visible gate but the hidden TB (16 counted steps, an N=3
// instance, mid-count synchronous-reset probes) and the differential oracle
// expose it. Demonstrates that passing the visible feedback loop is not
// enough: hidden + oracle catch stimulus memorization -> reward 0.2.
module gray_counter #(
    parameter N = 4
) (
    input  wire         clk,
    input  wire         rst_n,
    output wire [N-1:0] gray
);
    integer idx;
    always @(posedge clk) begin
        if (!rst_n)
            idx <= 0;
        else
            idx <= idx + 1;
    end
    // Replay of the memorized visible-test expected values only.
    assign gray = (idx == 0) ? 4'd0 :
                  (idx == 1) ? 4'd1 :
                  (idx == 2) ? 4'd3 :
                  (idx == 3) ? 4'd2 :
                  (idx == 4) ? 4'd6 : 4'd0;
endmodule
