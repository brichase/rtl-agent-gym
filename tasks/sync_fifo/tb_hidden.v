`timescale 1ns/1ps

module tb_hidden;
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
    reg [WIDTH-1:0] model_mem [0:DEPTH-1];
    reg [WIDTH-1:0] model_data_out;
    reg saved_full;
    reg saved_empty;
    reg [WIDTH-1:0] saved_data;
    integer model_head;
    integer model_tail;
    integer model_count;
    integer failures;
    integer i;
    integer do_read_model;
    integer do_write_model;

    sync_fifo #(.WIDTH(WIDTH), .DEPTH(DEPTH)) dut (
        .clk(clk), .rst_n(rst_n), .wr_en(wr_en), .rd_en(rd_en),
        .data_in(data_in), .data_out(data_out), .full(full), .empty(empty)
    );
    always #5 clk = ~clk;

    task check_model;
        begin
            if (full !== (model_count == DEPTH)) begin
                $display("TB_FAIL: full=%b at model occupancy %0d", full, model_count);
                failures = failures + 1;
            end
            if (empty !== (model_count == 0)) begin
                $display("TB_FAIL: empty=%b at model occupancy %0d", empty, model_count);
                failures = failures + 1;
            end
            if (data_out !== model_data_out) begin
                $display("TB_FAIL: data_out=%h expected=%h", data_out, model_data_out);
                failures = failures + 1;
            end
        end
    endtask

    task transact;
        input do_write;
        input do_read;
        input [WIDTH-1:0] value;
        begin
            do_read_model = do_read && (model_count != 0);
            do_write_model = do_write && ((model_count != DEPTH) || do_read_model);
            @(negedge clk);
            wr_en = do_write;
            rd_en = do_read;
            data_in = value;
            @(posedge clk);
            if (do_read_model) begin
                model_data_out = model_mem[model_head];
                model_head = (model_head + 1) % DEPTH;
                model_count = model_count - 1;
            end
            if (do_write_model) begin
                model_mem[model_tail] = value;
                model_tail = (model_tail + 1) % DEPTH;
                model_count = model_count + 1;
            end
            #1; check_model;
        end
    endtask

    initial begin
        clk = 1'b0;
        rst_n = 1'b0;
        wr_en = 1'b0;
        rd_en = 1'b0;
        data_in = 0;
        failures = 0;
        model_head = 0;
        model_tail = 0;
        model_count = 0;
        model_data_out = 0;
        @(posedge clk); #1; check_model;
        @(negedge clk); rst_n = 1'b1;

        // Fill, reject overflow, then accept simultaneous read/write at full.
        for (i = 0; i < DEPTH; i = i + 1)
            transact(1'b1, 1'b0, 8'h10 + i);
        transact(1'b1, 1'b0, 8'hee);
        transact(1'b1, 1'b1, 8'h80);

        // Drain, reject underflow, then accept only the write at empty.
        for (i = 0; i < DEPTH; i = i + 1)
            transact(1'b0, 1'b1, 8'h00);
        transact(1'b0, 1'b1, 8'h00);
        transact(1'b1, 1'b1, 8'h91);
        transact(1'b0, 1'b1, 8'h00);

        // Mid-fill simultaneous operation leaves occupancy unchanged.
        for (i = 0; i < 4; i = i + 1)
            transact(1'b1, 1'b0, 8'h30 + i);
        transact(1'b1, 1'b1, 8'h44);
        for (i = 0; i < 4; i = i + 1)
            transact(1'b0, 1'b1, 8'h00);

        // More than twice DEPTH successful writes and reads exercise both pointers.
        for (i = 0; i < (2*DEPTH + 5); i = i + 1) begin
            transact(1'b1, 1'b0, i + 8'ha0);
            transact(1'b0, 1'b1, 8'h00);
        end

        // Build nonempty state and verify reset is synchronous before applying it.
        transact(1'b1, 1'b0, 8'hc1);
        transact(1'b1, 1'b0, 8'hc2);
        saved_full = full;
        saved_empty = empty;
        saved_data = data_out;
        @(negedge clk); #2 rst_n = 1'b0; #1;
        if ((full !== saved_full) || (empty !== saved_empty) ||
            (data_out !== saved_data)) begin
            $display("TB_FAIL: synchronous reset changed state between rising edges");
            failures = failures + 1;
        end
        @(posedge clk);
        model_head = 0;
        model_tail = 0;
        model_count = 0;
        model_data_out = 0;
        #1; check_model;
        @(negedge clk);
        rst_n = 1'b1;
        wr_en = 1'b0;
        rd_en = 1'b0;
        transact(1'b1, 1'b0, 8'hd5);
        transact(1'b0, 1'b1, 8'h00);

        if (failures == 0)
            $display("TB_ALL_PASS");
        $finish;
    end
endmodule
