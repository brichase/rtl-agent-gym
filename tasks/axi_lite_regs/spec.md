# Four-register AXI4-Lite subordinate

Implement the sequential module `axi_lite_regs` from `interface.v`. It is an AXI4-Lite
subordinate with 32-bit addresses, 32-bit data, and four resettable read/write registers
at byte addresses `32'h00000000`, `32'h00000004`, `32'h00000008`, and
`32'h0000000c`.

Every channel uses the standard independent VALID/READY handshake: a transfer occurs
on a rising edge only when both signals are high, and a source must hold its payload
and VALID stable until that transfer. The subordinate may apply backpressure and
supports one outstanding write response and one outstanding read response.

The AW and W channels are independent. Accept either address or data first and retain
it until its partner arrives. Execute a write only after both an AW transfer and a W
transfer have occurred; never modify a register from an address transfer alone. Once
both have landed, apply `s_axi_wstrb[3:0]` byte-wise: strobe bit 0 controls bits 7:0,
bit 1 controls 15:8, bit 2 controls 23:16, and bit 3 controls 31:24. Then assert
`s_axi_bvalid` with the write response and hold both until a B handshake. A valid
register address returns the OKAY response `2'b00`. Any other address, including an
unaligned address or one with nonzero upper bits, changes no register and returns
SLVERR `2'b10`.

On an AR transfer, return the current value of the addressed register, assert
`s_axi_rvalid`, and hold `s_axi_rdata` and `s_axi_rresp` until an R handshake. The four
valid addresses return OKAY. Every other address returns data zero and SLVERR. Reads
are independent of the B channel, so a read may be accepted and answered while a write
response is stalled. A read accepted on the same edge that changes a register observes
the register's value from before that edge; a read accepted on a later edge, including
while the resulting B response is pending, observes the new value.

`rst_n` is active low and **synchronous**. If low at a rising edge, clear all four
registers, discard any saved AW or W half-transaction, and deassert `s_axi_bvalid` and
`s_axi_rvalid`. READY outputs are low while reset is asserted. Changing `rst_n` between
rising edges must not change state or outputs. Reset takes priority over all handshakes.
