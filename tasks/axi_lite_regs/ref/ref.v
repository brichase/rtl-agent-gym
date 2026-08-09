`timescale 1ns/1ps

module axi_lite_regs (
    input wire clk, input wire rst_n,
    input wire [31:0] s_axi_awaddr, input wire s_axi_awvalid, output wire s_axi_awready,
    input wire [31:0] s_axi_wdata, input wire [3:0] s_axi_wstrb,
    input wire s_axi_wvalid, output wire s_axi_wready,
    output reg [1:0] s_axi_bresp, output reg s_axi_bvalid, input wire s_axi_bready,
    input wire [31:0] s_axi_araddr, input wire s_axi_arvalid, output wire s_axi_arready,
    output reg [31:0] s_axi_rdata, output reg [1:0] s_axi_rresp,
    output reg s_axi_rvalid, input wire s_axi_rready
);
    reg [31:0] regs [0:3];
    reg aw_pending;
    reg [31:0] awaddr_hold;
    reg w_pending;
    reg [31:0] wdata_hold;
    reg [3:0] wstrb_hold;
    wire [31:0] selected_awaddr;
    wire [31:0] selected_wdata;
    wire [3:0] selected_wstrb;
    integer i;

    assign s_axi_awready = rst_n && !aw_pending && !s_axi_bvalid;
    assign s_axi_wready  = rst_n && !w_pending && !s_axi_bvalid;
    assign s_axi_arready = rst_n && !s_axi_rvalid;
    assign selected_awaddr = aw_pending ? awaddr_hold : s_axi_awaddr;
    assign selected_wdata = w_pending ? wdata_hold : s_axi_wdata;
    assign selected_wstrb = w_pending ? wstrb_hold : s_axi_wstrb;

    always @(posedge clk) begin
        if (!rst_n) begin
            aw_pending <= 0;
            awaddr_hold <= 0;
            w_pending <= 0;
            wdata_hold <= 0;
            wstrb_hold <= 0;
            s_axi_bresp <= 0;
            s_axi_bvalid <= 0;
            s_axi_rdata <= 0;
            s_axi_rresp <= 0;
            s_axi_rvalid <= 0;
            for (i = 0; i < 4; i = i + 1)
                regs[i] <= 0;
        end else begin
            if (s_axi_bvalid && s_axi_bready)
                s_axi_bvalid <= 0;
            if (s_axi_rvalid && s_axi_rready)
                s_axi_rvalid <= 0;

            if (s_axi_awready && s_axi_awvalid) begin
                aw_pending <= 1;
                awaddr_hold <= s_axi_awaddr;
            end
            if (s_axi_wready && s_axi_wvalid) begin
                w_pending <= 1;
                wdata_hold <= s_axi_wdata;
                wstrb_hold <= s_axi_wstrb;
            end

            if (!s_axi_bvalid &&
                (aw_pending || (s_axi_awready && s_axi_awvalid)) &&
                (w_pending || (s_axi_wready && s_axi_wvalid))) begin
                if (selected_awaddr == 32'h00000000 || selected_awaddr == 32'h00000004 ||
                    selected_awaddr == 32'h00000008 || selected_awaddr == 32'h0000000c) begin
                    if (selected_wstrb[0])
                        regs[selected_awaddr[3:2]][7:0] <= selected_wdata[7:0];
                    if (selected_wstrb[1])
                        regs[selected_awaddr[3:2]][15:8] <= selected_wdata[15:8];
                    if (selected_wstrb[2])
                        regs[selected_awaddr[3:2]][23:16] <= selected_wdata[23:16];
                    if (selected_wstrb[3])
                        regs[selected_awaddr[3:2]][31:24] <= selected_wdata[31:24];
                    s_axi_bresp <= 2'b00;
                end else begin
                    s_axi_bresp <= 2'b10;
                end
                s_axi_bvalid <= 1;
                aw_pending <= 0;
                w_pending <= 0;
            end

            if (s_axi_arready && s_axi_arvalid) begin
                case (s_axi_araddr)
                    32'h00000000: begin s_axi_rdata <= regs[0]; s_axi_rresp <= 2'b00; end
                    32'h00000004: begin s_axi_rdata <= regs[1]; s_axi_rresp <= 2'b00; end
                    32'h00000008: begin s_axi_rdata <= regs[2]; s_axi_rresp <= 2'b00; end
                    32'h0000000c: begin s_axi_rdata <= regs[3]; s_axi_rresp <= 2'b00; end
                    default: begin s_axi_rdata <= 0; s_axi_rresp <= 2'b10; end
                endcase
                s_axi_rvalid <= 1;
            end
        end
    end
endmodule
