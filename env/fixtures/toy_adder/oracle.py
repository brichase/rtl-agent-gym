#!/usr/bin/env python3
"""Randomized differential oracle for the toy adder fixture."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rtl", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--tools")
    args = parser.parse_args()

    workdir = Path(args.workdir)
    tools = Path(
        args.tools
        or os.environ.get("RTL_GYM_TOOLS")
        or "/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin"
    )
    rng = random.Random(args.seed)
    vectors = [(0, 0), (15, 15), (15, 1), (8, 8)]
    vectors.extend((rng.randrange(16), rng.randrange(16)) for _ in range(60))
    reference_module = Path(args.ref).stem
    statements = []
    for index, (a_value, b_value) in enumerate(vectors):
        statements.append(
            f"a=4'd{a_value}; b=4'd{b_value}; #1; "
            f"if (agent_sum !== ref_sum) begin "
            f'$display("MISMATCH:{index}:%b:%b", agent_sum, ref_sum); $finish; end'
        )
    testbench = f"""`timescale 1ns/1ps
module oracle_tb;
  reg [3:0] a, b;
  wire [4:0] agent_sum, ref_sum;
  add4 agent (.a(a), .b(b), .sum(agent_sum));
  {reference_module} reference (.a(a), .b(b), .sum(ref_sum));
  initial begin
    {' '.join(statements)}
    $display("ORACLE_ALL_PASS");
    $finish;
  end
endmodule
"""
    tb_path = workdir / "oracle_tb.v"
    output_path = workdir / "oracle.vvp"
    tb_path.write_text(testbench, encoding="utf-8")
    compile_result = subprocess.run(
        [
            str(tools / "iverilog"),
            "-g2005",
            "-s",
            "oracle_tb",
            "-o",
            str(output_path),
            args.rtl,
            args.ref,
            str(tb_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if compile_result.returncode != 0:
        sys.stdout.write(compile_result.stdout)
        print(json.dumps({"pass": False, "seed": args.seed, "checked": 0, "first_mismatch": "compile error"}))
        return 2
    simulation = subprocess.run(
        [str(tools / "vvp"), str(output_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    sys.stdout.write(simulation.stdout)
    passed = simulation.returncode == 0 and "ORACLE_ALL_PASS" in simulation.stdout
    mismatch = next((line for line in simulation.stdout.splitlines() if line.startswith("MISMATCH:")), None)
    checked = int(mismatch.split(":", 2)[1]) + 1 if mismatch else len(vectors)
    print(json.dumps({"pass": passed, "seed": args.seed, "checked": checked, "first_mismatch": mismatch}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
