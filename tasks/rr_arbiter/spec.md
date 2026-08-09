# Four-requester round-robin arbiter

Implement the sequential module `rr_arbiter` from `interface.v`.

`req[3:0]` contains four active-high request signals and `grant[3:0]` contains the
corresponding grants. `grant` is registered: requests are sampled on each rising edge
of `clk`, and the grant selected at that edge appears immediately after the edge and
remains unchanged until the next rising edge. At most one grant may be high. If no
request is high at a rising edge, the next registered grant is `4'b0000`.

Arbitration is round-robin. The remembered position is the index of the requester that
most recently received a grant. At each non-idle rising edge, examine requesters in
cyclic order starting immediately after that position, and grant the first asserted
request. Thus, after granting requester 2, the search order is 3, 0, 1, 2. A grant
updates the remembered position. An idle cycle produces no grant and does not change
the remembered position, so priority resumes where it left off when requests return.
A requester that remains asserted may receive repeated grants when nobody else is
requesting.

`rst_n` is active low and **synchronous**. If it is low at a rising edge, clear `grant`
and initialize the remembered position to requester 3, making requester 0 the first
priority after reset. Changing `rst_n` between rising edges must not change the state
or output. Reset takes priority over arbitration.
