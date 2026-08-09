`timescale 1ns/1ps
module axi_lite_regs (
    input wire clk,input wire rst_n,input wire [31:0] s_axi_awaddr,input wire s_axi_awvalid,output wire s_axi_awready,
    input wire [31:0] s_axi_wdata,input wire [3:0] s_axi_wstrb,input wire s_axi_wvalid,output wire s_axi_wready,
    output reg [1:0] s_axi_bresp,output reg s_axi_bvalid,input wire s_axi_bready,
    input wire [31:0] s_axi_araddr,input wire s_axi_arvalid,output wire s_axi_arready,
    output reg [31:0] s_axi_rdata,output reg [1:0] s_axi_rresp,output reg s_axi_rvalid,input wire s_axi_rready
);
    reg [31:0] regs[0:3]; reg ap,wp; reg [31:0] ah,wd; reg [3:0] ws; integer i;
    wire [31:0] aa=ap?ah:s_axi_awaddr; wire [31:0] dd=wp?wd:s_axi_wdata; wire [3:0] ss=wp?ws:s_axi_wstrb;
    assign s_axi_awready=rst_n&&!ap&&!s_axi_bvalid; assign s_axi_wready=rst_n&&!wp&&!s_axi_bvalid; assign s_axi_arready=rst_n&&!s_axi_rvalid;
    always @(posedge clk) begin
      if(!rst_n) begin ap<=0;wp<=0;s_axi_bvalid<=0;s_axi_rvalid<=0;s_axi_bresp<=0;s_axi_rresp<=0;s_axi_rdata<=0;ah<=0;wd<=0;ws<=0;for(i=0;i<4;i=i+1)regs[i]<=0;end
      else begin
        if(s_axi_bvalid&&s_axi_bready)s_axi_bvalid<=0; if(s_axi_rvalid&&s_axi_rready)s_axi_rvalid<=0;
        if(s_axi_awready&&s_axi_awvalid) begin ap<=1;ah<=s_axi_awaddr; if(s_axi_awaddr==0||s_axi_awaddr==4||s_axi_awaddr==8||s_axi_awaddr==12) regs[s_axi_awaddr[3:2]]<=32'hdeadbeef; end
        if(s_axi_wready&&s_axi_wvalid)begin wp<=1;wd<=s_axi_wdata;ws<=s_axi_wstrb;end
        if(!s_axi_bvalid&&(ap||(s_axi_awready&&s_axi_awvalid))&&(wp||(s_axi_wready&&s_axi_wvalid)))begin
          if(aa==0||aa==4||aa==8||aa==12)begin if(ss[0])regs[aa[3:2]][7:0]<=dd[7:0];if(ss[1])regs[aa[3:2]][15:8]<=dd[15:8];if(ss[2])regs[aa[3:2]][23:16]<=dd[23:16];if(ss[3])regs[aa[3:2]][31:24]<=dd[31:24];s_axi_bresp<=0;end else s_axi_bresp<=2; s_axi_bvalid<=1;ap<=0;wp<=0;end
        if(s_axi_arready&&s_axi_arvalid)begin case(s_axi_araddr)0:begin s_axi_rdata<=regs[0];s_axi_rresp<=0;end 4:begin s_axi_rdata<=regs[1];s_axi_rresp<=0;end 8:begin s_axi_rdata<=regs[2];s_axi_rresp<=0;end 12:begin s_axi_rdata<=regs[3];s_axi_rresp<=0;end default:begin s_axi_rdata<=0;s_axi_rresp<=2;end endcase s_axi_rvalid<=1;end
      end
    end
endmodule
