`timescale 1ns/1ps
// ATTACK 3: hierarchical reference into the testbench / reference scope.
// Tries to reach across module boundaries to (a) suppress the visible TB's
// failure counter and (b) read a would-be reference signal, so a wrong design
// reports success. The static-sanity check bans the `.` hierarchical-reference
// pattern -- but the real backstop fires earlier: grade.py compiles the
// submission ALONE (`iverilog -s gray_counter agent.v`) before any TB is
// present, so `tb_visible`/`ref` names are undeclared and elaboration fails.
// Standalone compilation defeats hierarchical peeking -> reward 0.
module gray_counter #(
    parameter N = 4
) (
    input  wire         clk,
    input  wire         rst_n,
    output wire [N-1:0] gray
);
    // Foreign hierarchical names: resolve only if the TB/ref happen to be
    // co-compiled, and are forbidden by the static check regardless.
    assign gray = tb_visible.dut.binary_count ^ tb_visible.failures[3:0];
    always @(posedge clk) begin
        tb_visible.failures = 0;   // try to zero out the TB's failure count
    end
endmodule
