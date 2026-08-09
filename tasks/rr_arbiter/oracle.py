#!/usr/bin/env python3
"""Seeded cycle-by-cycle differential oracle for rr_arbiter."""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TOOLS = Path("/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin")


def operations(seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    ops: list[tuple[int, int]] = [(0, 0), (0, 15), (1, 0)]
    ops.extend((1, 15) for _ in range(20))
    ops.extend((1, 1 << requester) for requester in range(4) for _ in range(4))
    ops.extend([(1, 0), (1, 0), (1, 10), (1, 0), (1, 3)])
    for phase in range(6):
        for _ in range(rng.randint(24, 48)):
            if rng.random() < 0.22:
                request = 0
            elif rng.random() < 0.30:
                request = 1 << rng.randrange(4)
            else:
                request = rng.randrange(1, 16)
            burst = rng.randint(1, 6)
            ops.extend((1, request) for _ in range(burst))
        if phase != 5:
            ops.extend([(0, rng.randrange(16)), (0, 0), (1, rng.randrange(16))])
    return ops


def discover_module_name(design: Path) -> str:
    source = design.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//[^\r\n]*", "", source)
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)", source)
    if match is None:
        raise RuntimeError(f"no module declaration found in {design}")
    return match.group(1)


def make_tb(ops: list[tuple[int, int]], module_name: str) -> str:
    body = []
    for index, (reset_value, request) in enumerate(ops):
        body.append(
            f"    rst_n=1'b{reset_value}; req=4'h{request:x}; #4; clk=1; #1; "
            f"$display(\"TRACE {index} %b\", grant); #4; clk=0; #1;"
        )
    return "\n".join([
        "`timescale 1ns/1ps",
        "module oracle_tb;",
        "  reg clk, rst_n; reg [3:0] req; wire [3:0] grant;",
        f"  {module_name} dut(.clk(clk), .rst_n(rst_n), .req(req), .grant(grant));",
        "  initial begin",
        "    clk=0; rst_n=0; req=0;",
        *body,
        "    $finish;",
        "  end",
        "endmodule",
        "",
    ])


def simulate(design: Path, tb_text: str, run_dir: Path, tools: Path) -> list[str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    tb_path = run_dir / "oracle_tb.v"
    image = run_dir / "sim.vvp"
    tb_path.write_text(tb_text, encoding="utf-8")
    compiled = subprocess.run(
        [str(tools / "iverilog"), "-g2005", "-s", "oracle_tb", "-o", str(image),
         str(design), str(tb_path)],
        text=True, capture_output=True, timeout=30, check=False,
    )
    if compiled.returncode != 0:
        raise RuntimeError(f"compile failed for {design}: {compiled.stderr.strip()}")
    simulated = subprocess.run(
        [str(tools / "vvp"), str(image)], text=True, capture_output=True,
        timeout=30, check=False,
    )
    if simulated.returncode != 0:
        raise RuntimeError(f"simulation failed for {design}: {simulated.stderr.strip()}")
    return [line for line in simulated.stdout.splitlines() if line.startswith("TRACE ")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rtl", required=True, type=Path)
    parser.add_argument("--ref", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--tools", type=Path, default=DEFAULT_TOOLS)
    args = parser.parse_args()
    ops = operations(args.seed)
    args.workdir.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=f"arbiter_{args.seed}_", dir=args.workdir))
    result = {"pass": False, "seed": args.seed, "checked": 0, "first_mismatch": None}
    try:
        rtl_trace = simulate(
            args.rtl.resolve(), make_tb(ops, "rr_arbiter"), root / "rtl", args.tools
        )
        ref_path = args.ref.resolve()
        ref_trace = simulate(
            ref_path, make_tb(ops, discover_module_name(ref_path)), root / "ref", args.tools
        )
        result["checked"] = min(len(rtl_trace), len(ref_trace))
        if len(rtl_trace) != len(ref_trace):
            result["first_mismatch"] = f"trace length rtl={len(rtl_trace)} ref={len(ref_trace)}"
        else:
            for index, (got, expected) in enumerate(zip(rtl_trace, ref_trace)):
                if got != expected:
                    result["first_mismatch"] = (
                        f"cycle {index}: rtl={got!r} ref={expected!r} input={ops[index]}"
                    )
                    break
            else:
                result["pass"] = True
        print(json.dumps(result, sort_keys=True))
        return 0 if result["pass"] else 1
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        result["first_mismatch"] = f"infrastructure error: {exc}"
        print(json.dumps(result, sort_keys=True))
        return 2
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
