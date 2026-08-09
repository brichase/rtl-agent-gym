`timescale 1ns/1ps
module axi_lite_regs (
    input wire clk,input wire rst_n,input wire [31:0] s_axi_awaddr,input wire s_axi_awvalid,output wire s_axi_awready,
    input wire [31:0] s_axi_wdata,input wire [3:0] s_axi_wstrb,input wire s_axi_wvalid,output wire s_axi_wready,
    output wire [1:0] s_axi_bresp,output wire s_axi_bvalid,input wire s_axi_bready,
    input wire [31:0] s_axi_araddr,input wire s_axi_arvalid,output wire s_axi_arready,
    output wire [31:0] s_axi_rdata,output wire [1:0] s_axi_rresp,output wire s_axi_rvalid,input wire s_axi_rready
);
    assign s_axi_awready=0; assign s_axi_wready=0; assign s_axi_bresp=0; assign s_axi_bvalid=0;
    assign s_axi_arready=0; assign s_axi_rdata=0; assign s_axi_rresp=0; assign s_axi_rvalid=0;
endmodule
