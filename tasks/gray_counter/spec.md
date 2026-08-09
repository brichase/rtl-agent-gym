# N-bit Gray-code counter

Implement the sequential module `gray_counter` from `interface.v`. `N` is the output
width and defaults to 4.

The counter has an internal unsigned `N`-bit binary count. On every rising edge of
`clk` for which `rst_n` is high, increment that binary count by one modulo `2**N`.
The output is the binary-reflected Gray encoding of the current binary count:
`gray = binary_count ^ (binary_count >> 1)`.

`rst_n` is active low and **synchronous**. If `rst_n` is low at a rising edge, set the
binary count, and therefore `gray`, to zero instead of incrementing. Changing `rst_n`
between rising edges must not change the state or output. Reset has priority over the
increment.

The modulo wrap from all-one binary count to zero is a normal count transition. Thus
successive outputs during uninterrupted counting, including the wrap transition, differ
in exactly one bit.
