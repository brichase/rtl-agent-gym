# Synchronous FIFO with full and empty flags

Implement `sync_fifo` from `interface.v`. `WIDTH` is the stored word width and defaults
to 8. `DEPTH` is the number of words and defaults to 8. All reads and writes are governed
by a single rising-edge clock.

`rst_n` is active low and **synchronous**. When it is low at a rising edge, the FIFO
becomes empty: read and write positions and occupancy are cleared, `empty` is asserted,
`full` is deasserted, and `data_out` becomes all zeroes. Changing `rst_n` between rising
edges must not change any visible state. Reset has priority over reads and writes.

At each non-reset rising edge, determine acceptance from the FIFO state immediately
before that edge:

- A read is accepted when `rd_en` is high and the FIFO is not empty. It removes the
  oldest word and updates `data_out` to that word.
- A write is accepted when `wr_en` is high and either the FIFO is not full or a read is
  accepted on the same edge. It appends `data_in` as the newest word.
- A write attempted while full with no accepted read is ignored.
- A read attempted while empty is ignored. `data_out` retains its previous value on any
  edge without an accepted read.

Therefore, simultaneous `rd_en` and `wr_en` while full accepts both operations: the
oldest word appears on `data_out`, the new word is appended, and the FIFO remains full.
Simultaneous `rd_en` and `wr_en` while empty accepts only the write: no read occurs,
`data_out` holds its value, and occupancy becomes one. Away from the boundaries,
simultaneous read and write accepts both and leaves occupancy unchanged.

`empty` is high exactly when occupancy is zero. `full` is high exactly when occupancy is
`DEPTH`. Successful operations preserve FIFO ordering across pointer wraparound; no word
may be lost, duplicated, or reordered.
