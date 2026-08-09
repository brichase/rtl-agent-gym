# Parameterized barrel shifter

Implement the combinational module `barrel_shifter` from `interface.v`.

`WIDTH` is the data width and defaults to 8. `data_in` and `data_out` are unsigned
`WIDTH`-bit vectors. `shift_amt` is also `WIDTH` bits wide; its unsigned numeric value
is the requested distance. `mode` selects exactly one operation:

- `2'b00`: logical left shift. Vacated low bits are zero. A distance greater than or
  equal to `WIDTH` produces all zeroes.
- `2'b01`: logical right shift. Vacated high bits are zero. A distance greater than or
  equal to `WIDTH` produces all zeroes.
- `2'b10`: rotate left. The distance is reduced modulo `WIDTH`; bits shifted out of the
  high end re-enter at the low end.
- `2'b11`: rotate right. The distance is reduced modulo `WIDTH`; bits shifted out of the
  low end re-enter at the high end.

The output must respond combinationally to every input change. In particular, a zero
distance returns `data_in` in every mode. No clock, reset, latch, or stored state is used.
