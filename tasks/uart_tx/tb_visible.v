`timescale 1ns/1ps

module tb_visible;
    localparam CLKS_PER_BIT = 16;
    reg clk;
    reg rst_n;
    reg tx_start;
    reg [7:0] tx_data;
    wire tx_serial;
    wire tx_busy;
    integer failures;
    integer i;

    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) dut (
        .clk(clk), .rst_n(rst_n), .tx_start(tx_start), .tx_data(tx_data),
        .tx_serial(tx_serial), .tx_busy(tx_busy)
    );
    always #5 clk = ~clk;

    initial begin
        clk = 0; rst_n = 0; tx_start = 0; tx_data = 0; failures = 0;
        @(posedge clk); #1;
        if (tx_serial !== 1'b1 || tx_busy !== 1'b0) begin
            $display("TB_FAIL: reset/idle outputs serial=%b busy=%b", tx_serial, tx_busy);
            failures = failures + 1;
        end
        @(negedge clk); rst_n = 1; tx_data = 8'h00; tx_start = 1;
        @(posedge clk); #1;
        if (tx_serial !== 1'b0 || tx_busy !== 1'b1) begin
            $display("TB_FAIL: frame did not begin with low start bit and busy high");
            failures = failures + 1;
        end
        @(negedge clk); tx_start = 0;
        for (i = 0; i < 9*CLKS_PER_BIT-1; i = i + 1) begin
            @(posedge clk); #1;
            if (tx_busy !== 1'b1) begin
                $display("TB_FAIL: busy deasserted before stop bit");
                failures = failures + 1;
            end
        end
        @(posedge clk); #1;
        if (tx_serial !== 1'b1 || tx_busy !== 1'b1) begin
            $display("TB_FAIL: stop bit is not high while busy");
            failures = failures + 1;
        end
        repeat (CLKS_PER_BIT-1) @(posedge clk);
        #1;
        if (tx_busy !== 1'b1 || tx_serial !== 1'b1) begin
            $display("TB_FAIL: stop bit duration is too short");
            failures = failures + 1;
        end
        @(posedge clk); #1;
        if (tx_busy !== 1'b0 || tx_serial !== 1'b1) begin
            $display("TB_FAIL: transmitter did not return idle");
            failures = failures + 1;
        end
        if (failures == 0) $display("TB_ALL_PASS");
        $finish;
    end
endmodule
