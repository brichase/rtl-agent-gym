# 8N1 UART transmitter

Implement the sequential module `uart_tx` from `interface.v`. `CLKS_PER_BIT` is the
number of rising-edge intervals per serial bit and defaults to 16. It is always at
least 2.

When idle, `tx_serial` is high and `tx_busy` is low. If `tx_start` is high at a rising
edge while idle, capture `tx_data`, drive the start bit low, and assert `tx_busy`
immediately after that edge. Transmit one low start bit, eight data bits least-
significant-bit first (`tx_data[0]` through `tx_data[7]`), and one high stop bit.

Every start, data, and stop bit is held for exactly `CLKS_PER_BIT` complete rising-edge
intervals. The acceptance edge begins the first start-bit interval; the serial output
first advances to data bit 0 exactly `CLKS_PER_BIT` rising edges later. After the stop
bit has occupied the same number of intervals, `tx_busy` deasserts and the line remains
high. A new frame may be accepted on the next rising edge. `tx_start` is sampled only
while idle and is ignored while `tx_busy` is high, so it cannot alter the byte or timing
of a frame already in progress.

`rst_n` is active low and **synchronous**. If it is low at a rising edge, abort any
frame, drive `tx_serial` high, and clear `tx_busy`. Changing `rst_n` between rising
edges must not change either output. Reset takes priority over transmission.
