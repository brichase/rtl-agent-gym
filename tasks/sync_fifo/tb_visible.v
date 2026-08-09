`timescale 1ns/1ps

module tb_visible;
    localparam WIDTH = 8;
    localparam DEPTH = 8;
    reg clk;
    reg rst_n;
    reg wr_en;
    reg rd_en;
    reg [WIDTH-1:0] data_in;
    wire [WIDTH-1:0] data_out;
    wire full;
    wire empty;
    integer failures;

    sync_fifo #(.WIDTH(WIDTH), .DEPTH(DEPTH)) dut (
        .clk(clk), .rst_n(rst_n), .wr_en(wr_en), .rd_en(rd_en),
        .data_in(data_in), .data_out(data_out), .full(full), .empty(empty)
    );
    always #5 clk = ~clk;

    task drive;
        input do_write;
        input do_read;
        input [WIDTH-1:0] value;
        begin
            @(negedge clk);
            wr_en = do_write;
            rd_en = do_read;
            data_in = value;
            @(posedge clk); #1;
        end
    endtask

    task expect_state;
        input expected_full;
        input expected_empty;
        input [WIDTH-1:0] expected_data;
        begin
            if ((full !== expected_full) || (empty !== expected_empty) ||
                (data_out !== expected_data)) begin
                $display("TB_FAIL: full=%b/%b empty=%b/%b data=%h/%h",
                         full, expected_full, empty, expected_empty,
                         data_out, expected_data);
                failures = failures + 1;
            end
        end
    endtask

    initial begin
        clk = 1'b0;
        rst_n = 1'b0;
        wr_en = 1'b0;
        rd_en = 1'b0;
        data_in = 0;
        failures = 0;
        @(posedge clk); #1; expect_state(1'b0, 1'b1, 8'h00);
        @(negedge clk); rst_n = 1'b1;
        drive(1'b1, 1'b0, 8'h31); expect_state(1'b0, 1'b0, 8'h00);
        drive(1'b1, 1'b0, 8'h72); expect_state(1'b0, 1'b0, 8'h00);
        drive(1'b0, 1'b1, 8'h00); expect_state(1'b0, 1'b0, 8'h31);
        drive(1'b0, 1'b1, 8'h00); expect_state(1'b0, 1'b1, 8'h72);
        if (failures == 0)
            $display("TB_ALL_PASS");
        $finish;
    end
endmodule
