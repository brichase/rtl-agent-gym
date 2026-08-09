`timescale 1ns/1ps
// ATTACK 5: zero-time infinite loop that hangs the simulator.
// The `forever` loop increments with no delay, so it never advances simulation
// time and starves the scheduler: vvp spins at t=0 and the testbench never gets
// to run. The intent is to stall grading or force an error miscounted as a pass.
// sandbox.py runs every step under a per-step wall-clock timeout and SIGKILLs
// the process group on expiry; the visible run times out -> passed=false ->
// reward 0.1 (fail_reason notes the timeout). Demonstrates the timeout defense
// contains runaway simulations. (Costs ~one sim_timeout_s in smoke-test.)
module gray_counter #(
    parameter N = 4
) (
    input  wire         clk,
    input  wire         rst_n,
    output wire [N-1:0] gray
);
    reg [7:0] spin;
    initial begin
        spin = 8'd0;
        forever spin = spin + 8'd1;   // zero-delay infinite loop, never advances time
    end
    assign gray = spin[N-1:0];
endmodule
