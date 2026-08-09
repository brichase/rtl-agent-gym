`timescale 1ns/1ps

module tb_visible;
    localparam WIDTH = 8;
    reg  [WIDTH-1:0] data_in;
    reg  [WIDTH-1:0] shift_amt;
    reg  [1:0]       mode;
    wire [WIDTH-1:0] data_out;
    integer failures;

    barrel_shifter #(.WIDTH(WIDTH)) dut (
        .data_in(data_in), .shift_amt(shift_amt), .mode(mode),
        .data_out(data_out)
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

    initial begin
        failures = 0;
        check(8'h13, 8'd2, 2'b00, 8'h4c);
        check(8'hb4, 8'd2, 2'b01, 8'h2d);
        check(8'h81, 8'd1, 2'b10, 8'h03);
        check(8'h81, 8'd1, 2'b11, 8'hc0);
        check(8'h5a, 8'd3, 2'b10, 8'hd2);
        if (failures == 0)
            $display("TB_ALL_PASS");
        $finish;
    end
endmodule
