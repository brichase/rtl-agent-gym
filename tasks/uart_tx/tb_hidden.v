`timescale 1ns/1ps

module tb_hidden;
    localparam CPB = 16;
    reg clk;
    reg rst_n;
    reg tx_start;
    reg [7:0] tx_data;
    wire tx_serial;
    wire tx_busy;
    reg tx_start_4;
    reg [7:0] tx_data_4;
    wire tx_serial_4;
    wire tx_busy_4;
    integer failures;
    integer i;
    integer j;

    uart_tx #(.CLKS_PER_BIT(CPB)) dut (
        .clk(clk), .rst_n(rst_n), .tx_start(tx_start), .tx_data(tx_data),
        .tx_serial(tx_serial), .tx_busy(tx_busy)
    );
    uart_tx #(.CLKS_PER_BIT(4)) dut_cpb4 (
        .clk(clk), .rst_n(rst_n), .tx_start(tx_start_4), .tx_data(tx_data_4),
        .tx_serial(tx_serial_4), .tx_busy(tx_busy_4)
    );
    always #5 clk = ~clk;

    task check_main;
        input expected_serial;
        input expected_busy;
        begin
            #1;
            if (tx_serial !== expected_serial || tx_busy !== expected_busy) begin
                $display("TB_FAIL: main serial=%b/%b busy=%b/%b",
                         tx_serial, expected_serial, tx_busy, expected_busy);
                failures = failures + 1;
            end
        end
    endtask

    task send_main;
        input [7:0] value;
        begin
            @(negedge clk); tx_data = value; tx_start = 1;
            @(posedge clk); check_main(0, 1);
            @(negedge clk); tx_start = 0;
            for (j = 1; j < CPB; j = j + 1) begin
                @(posedge clk); check_main(0, 1);
            end
            for (i = 0; i < 8; i = i + 1) begin
                @(posedge clk); check_main(value[i], 1);
                for (j = 1; j < CPB; j = j + 1) begin
                    @(posedge clk); check_main(value[i], 1);
                end
            end
            @(posedge clk); check_main(1, 1);
            for (j = 1; j < CPB; j = j + 1) begin
                @(posedge clk); check_main(1, 1);
            end
            @(posedge clk); check_main(1, 0);
        end
    endtask

    task send_cpb4;
        input [7:0] value;
        begin
            @(negedge clk); tx_data_4 = value; tx_start_4 = 1;
            @(posedge clk); #1;
            if (tx_serial_4 !== 0 || tx_busy_4 !== 1) begin
                $display("TB_FAIL: CPB=4 start"); failures = failures + 1;
            end
            @(negedge clk); tx_start_4 = 0;
            repeat (3) begin @(posedge clk); #1; if (tx_serial_4 !== 0) begin $display("TB_FAIL: CPB=4 start width"); failures=failures+1; end end
            for (i = 0; i < 8; i = i + 1) begin
                @(posedge clk); #1; if (tx_serial_4 !== value[i]) begin $display("TB_FAIL: CPB=4 bit %0d", i); failures=failures+1; end
                repeat (3) begin @(posedge clk); #1; if (tx_serial_4 !== value[i]) begin $display("TB_FAIL: CPB=4 bit width %0d", i); failures=failures+1; end end
            end
            @(posedge clk); #1; if (tx_serial_4 !== 1 || tx_busy_4 !== 1) begin $display("TB_FAIL: CPB=4 stop"); failures=failures+1; end
            repeat (3) @(posedge clk);
            @(posedge clk); #1; if (tx_serial_4 !== 1 || tx_busy_4 !== 0) begin $display("TB_FAIL: CPB=4 completion"); failures=failures+1; end
        end
    endtask

    initial begin
        clk=0; rst_n=0; tx_start=0; tx_data=0; tx_start_4=0; tx_data_4=0; failures=0;
        @(posedge clk); #1;
        if (tx_serial !== 1 || tx_busy !== 0 || tx_serial_4 !== 1 || tx_busy_4 !== 0) begin
            $display("TB_FAIL: reset idle values"); failures = failures + 1;
        end
        @(negedge clk); rst_n=1;

        // Exact boundary checks also establish LSB-first order on asymmetric bytes.
        send_main(8'h5a);
        send_main(8'h96);

        // A start pulse during bit 2 must be ignored; the original byte continues.
        @(negedge clk); tx_data=8'h96; tx_start=1;
        @(posedge clk); check_main(0,1);
        @(negedge clk); tx_start=0;
        repeat (CPB-1) begin @(posedge clk); check_main(0,1); end
        @(posedge clk); check_main(0,1);
        repeat (CPB-1) begin @(posedge clk); check_main(0,1); end
        @(posedge clk); check_main(1,1);
        repeat (CPB-1) begin @(posedge clk); check_main(1,1); end
        @(negedge clk); tx_data=8'h00; tx_start=1;
        @(posedge clk); check_main(1,1);
        @(negedge clk); tx_start=0;
        repeat (CPB-1) begin @(posedge clk); check_main(1,1); end
        // Remaining bits of 0x96 are 0,1,0,0,1.
        for (i=3; i<8; i=i+1) begin
            @(posedge clk); check_main((8'h96 >> i) & 1'b1,1);
            repeat (CPB-1) begin @(posedge clk); check_main((8'h96 >> i) & 1'b1,1); end
        end
        @(posedge clk); check_main(1,1);
        repeat (CPB-1) begin @(posedge clk); check_main(1,1); end
        @(posedge clk); check_main(1,0);

        // Reset in a frame is synchronous and aborts it at the rising edge.
        @(negedge clk); tx_data=8'h33; tx_start=1;
        @(posedge clk); check_main(0,1);
        @(negedge clk); tx_start=0; #2 rst_n=0; #1;
        if (tx_serial !== 0 || tx_busy !== 1) begin
            $display("TB_FAIL: synchronous reset changed outputs between edges"); failures=failures+1;
        end
        @(posedge clk); #1;
        if (tx_serial !== 1 || tx_busy !== 0) begin
            $display("TB_FAIL: reset did not abort frame to idle"); failures=failures+1;
        end
        @(negedge clk); rst_n=1;

        send_cpb4(8'ha6);
        if (failures == 0) $display("TB_ALL_PASS");
        $finish;
    end
endmodule
