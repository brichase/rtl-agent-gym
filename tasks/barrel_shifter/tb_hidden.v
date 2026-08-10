`timescale 1ns/1ps

module tb_hidden;
    localparam WIDTH = 8;
    reg  [WIDTH-1:0] data_in;
    reg  [WIDTH-1:0] shift_amt;
    reg  [1:0]       mode;
    wire [WIDTH-1:0] data_out;
    reg  [4:0] data_in_5;
    reg  [4:0] shift_amt_5;
    reg  [1:0] mode_5;
    wire [4:0] data_out_5;
    integer failures;

    barrel_shifter #(.WIDTH(WIDTH)) dut (
        .data_in(data_in), .shift_amt(shift_amt), .mode(mode),
        .data_out(data_out)
    );
    barrel_shifter #(.WIDTH(5)) dut_width_5 (
        .data_in(data_in_5), .shift_amt(shift_amt_5), .mode(mode_5),
        .data_out(data_out_5)
    );

    task check;
        input [WIDTH-1:0] value;
        input [WIDTH-1:0] distance;
        input [1:0] operation;
        input [WIDTH-1:0] expected;
        begin
            data_in = value;
            shift_amt = distance;
            mode = operation;
            #1;
            if (data_out !== expected) begin
                $display("TB_FAIL: mode=%b data=%h shift=%0d got=%h expected=%h",
                         operation, value, distance, data_out, expected);
                failures = failures + 1;
            end
        end
    endtask

    task check_width_5;
        input [4:0] value;
        input [4:0] distance;
        input [1:0] operation;
        input [4:0] expected;
        begin
            data_in_5 = value;
            shift_amt_5 = distance;
            mode_5 = operation;
            #1;
            if (data_out_5 !== expected) begin
                $display("TB_FAIL: WIDTH=5 mode=%b data=%h shift=%0d got=%h expected=%h",
                         operation, value, distance, data_out_5, expected);
                failures = failures + 1;
            end
        end
    endtask

    initial begin
        failures = 0;
        check(8'ha5, 8'd0, 2'b00, 8'ha5);
        check(8'ha5, 8'd0, 2'b01, 8'ha5);
        check(8'ha5, 8'd0, 2'b10, 8'ha5);
        check(8'ha5, 8'd0, 2'b11, 8'ha5);
        check(8'h01, 8'd7, 2'b00, 8'h80);
        check(8'h80, 8'd7, 2'b01, 8'h01);
        check(8'h01, 8'd7, 2'b10, 8'h80);
        check(8'h80, 8'd7, 2'b11, 8'h01);
        check(8'hff, 8'd5, 2'b00, 8'he0);
        check(8'hff, 8'd5, 2'b01, 8'h07);
        check(8'hff, 8'd5, 2'b10, 8'hff);
        check(8'hff, 8'd5, 2'b11, 8'hff);
        check(8'h00, 8'd3, 2'b00, 8'h00);
        check(8'h00, 8'd3, 2'b01, 8'h00);
        check(8'h00, 8'd3, 2'b10, 8'h00);
        check(8'h00, 8'd3, 2'b11, 8'h00);
        check(8'h96, 8'd8, 2'b00, 8'h00);
        check(8'h96, 8'd8, 2'b01, 8'h00);
        check(8'h96, 8'd8, 2'b10, 8'h96);
        check(8'h96, 8'd8, 2'b11, 8'h96);
        check(8'h96, 8'd9, 2'b10, 8'h2d);
        check(8'h96, 8'd9, 2'b11, 8'h4b);
        check_width_5(5'b10001, 5'd4, 2'b00, 5'b10000);
        check_width_5(5'b10001, 5'd4, 2'b01, 5'b00001);
        check_width_5(5'b10001, 5'd4, 2'b10, 5'b11000);
        check_width_5(5'b10001, 5'd4, 2'b11, 5'b00011);
        check_width_5(5'b10110, 5'd5, 2'b10, 5'b10110);
        // WIDTH=5 requires modulo-5 rotation, not truncation to three low bits.
        check_width_5(5'b10110, 5'd8, 2'b10, 5'b10101);
        check_width_5(5'b10110, 5'd8, 2'b11, 5'b11010);
        check_width_5(5'b10110, 5'd9, 2'b10, 5'b01011);
        check_width_5(5'b10110, 5'd9, 2'b11, 5'b01101);
        // Logical shifts at or beyond WIDTH always produce zero.
        check_width_5(5'b10110, 5'd8, 2'b00, 5'b00000);
        check_width_5(5'b10110, 5'd8, 2'b01, 5'b00000);
        check_width_5(5'b10110, 5'd9, 2'b00, 5'b00000);
        check_width_5(5'b10110, 5'd9, 2'b01, 5'b00000);
        if (failures == 0)
            $display("TB_ALL_PASS");
        $finish;
    end
endmodule
