# Evaluation report

Source: `/data/projects/rtl-agent-gym/results/full/results.jsonl` (120 episodes). Solved means reward >= 0.7.
Pass@1 is the empirical solved-episode fraction; pass@5 records whether any trial in the group solved.

## Single-shot to agentic headline

| Model | Single-shot episode passes | Agentic episode passes | Delta pass rate | Single-shot task pass@5 | Agentic task pass@5 | Delta task pass@5 | Delta mean reward |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-5.6-luna@max | 30/30 (100.0%) | 30/30 (100.0%) | +0.0 pp | 6/6 (100.0%) | 6/6 (100.0%) | +0.0 pp | +0.023 |
| gpt-5.6-sol@high | 29/30 (96.7%) | 30/30 (100.0%) | +3.3 pp | 6/6 (100.0%) | 6/6 (100.0%) | +0.0 pp | +0.035 |

## Results by task, model, and condition

| Task | Model | Condition | Passes | Pass rate | Pass@1 | Pass@5 | Mean reward | Mean turns | Mean tool calls | Mean tokens in | Mean tokens out | Mean area norm (solved) | Mean depth norm (solved) | Flagged |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| axi_lite_regs | gpt-5.6-luna@max | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 0.00 | 12990.0 | 7687.2 | 0.933 | 0.625 | 0 |
| axi_lite_regs | gpt-5.6-luna@max | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 4.60 | 208248.8 | 12921.2 | 0.936 | 0.662 | 0 |
| axi_lite_regs | gpt-5.6-sol@high | single_shot | 4/5 | 80.0% | 4/5 (80.0%) | 1/1 (100.0%) | 0.820 | 1.00 | 0.00 | 14674.8 | 4356.2 | 0.936 | 0.562 | 0 |
| axi_lite_regs | gpt-5.6-sol@high | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 3.60 | 134233.8 | 9110.4 | 0.936 | 0.562 | 0 |
| barrel_shifter | gpt-5.6-luna@max | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 0.00 | 12548.0 | 1072.4 | 0.978 | 0.978 | 0 |
| barrel_shifter | gpt-5.6-luna@max | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.998 | 1.00 | 4.40 | 187279.8 | 4334.0 | 0.980 | 0.956 | 0 |
| barrel_shifter | gpt-5.6-sol@high | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.997 | 1.00 | 0.00 | 14232.8 | 1018.0 | 0.986 | 0.978 | 0 |
| barrel_shifter | gpt-5.6-sol@high | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.998 | 1.00 | 3.20 | 85603.8 | 2855.4 | 0.993 | 0.978 | 0 |
| gray_counter | gpt-5.6-luna@max | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 0.00 | 12468.0 | 341.2 | 1.000 | 1.000 | 0 |
| gray_counter | gpt-5.6-luna@max | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 3.80 | 148474.8 | 1801.2 | 1.000 | 1.000 | 0 |
| gray_counter | gpt-5.6-sol@high | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 0.00 | 14152.8 | 256.0 | 1.000 | 1.000 | 0 |
| gray_counter | gpt-5.6-sol@high | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 3.00 | 70521.8 | 1027.2 | 1.000 | 1.000 | 0 |
| rr_arbiter | gpt-5.6-luna@max | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.999 | 1.00 | 0.00 | 12593.0 | 1205.8 | 0.993 | 0.971 | 0 |
| rr_arbiter | gpt-5.6-luna@max | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.999 | 1.00 | 3.40 | 130987.4 | 4130.6 | 1.007 | 1.000 | 0 |
| rr_arbiter | gpt-5.6-sol@high | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 0.00 | 14283.4 | 955.2 | 1.007 | 0.971 | 0 |
| rr_arbiter | gpt-5.6-sol@high | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 3.80 | 82918.2 | 2998.2 | 1.007 | 0.971 | 0 |
| sync_fifo | gpt-5.6-luna@max | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.939 | 1.00 | 0.00 | 12867.8 | 1837.6 | 1.173 | 1.860 | 0 |
| sync_fifo | gpt-5.6-luna@max | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.990 | 1.00 | 3.20 | 187505.2 | 4660.8 | 1.008 | 1.060 | 0 |
| sync_fifo | gpt-5.6-sol@high | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.999 | 1.00 | 0.00 | 14295.0 | 1187.8 | 1.008 | 1.000 | 0 |
| sync_fifo | gpt-5.6-sol@high | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.999 | 1.00 | 3.00 | 94108.8 | 3628.0 | 1.008 | 1.000 | 0 |
| uart_tx | gpt-5.6-luna@max | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.908 | 1.00 | 0.00 | 12753.8 | 2783.2 | 1.475 | 0.871 | 0 |
| uart_tx | gpt-5.6-luna@max | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 3.40 | 145968.0 | 4898.4 | 0.636 | 0.548 | 0 |
| uart_tx | gpt-5.6-sol@high | single_shot | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 0.974 | 1.00 | 0.00 | 14309.8 | 1079.6 | 1.175 | 1.000 | 0 |
| uart_tx | gpt-5.6-sol@high | agentic | 5/5 | 100.0% | 5/5 (100.0%) | 1/1 (100.0%) | 1.000 | 1.00 | 3.00 | 85847.0 | 3626.2 | 0.412 | 0.239 | 0 |

## First-failure attribution

| First failure stage | Episodes | Share |
| --- | --- | --- |
| none | 118 | 98.3% |
| visible_sim | 1 | 0.8% |
| protocol_violation | 1 | 0.8% |

## Tool latency and cache

| Model | Condition | Timed calls | Latency p50 (ms) | Latency p95 (ms) | Cache hits |
| --- | --- | --- | --- | --- | --- |
| gpt-5.6-luna@max | single_shot | 30 | 32340.3 | 155438.5 | 0/30 (0.0%) |
| gpt-5.6-luna@max | agentic | 144 | 89.2 | 134459.6 | 0/144 (0.0%) |
| gpt-5.6-sol@high | single_shot | 30 | 27491.5 | 113290.7 | 0/30 (0.0%) |
| gpt-5.6-sol@high | agentic | 128 | 130.0 | 119513.7 | 0/128 (0.0%) |
