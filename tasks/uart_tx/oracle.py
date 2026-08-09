#!/usr/bin/env python3
"""Seeded cycle-by-cycle differential oracle for uart_tx."""

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
CLKS_PER_BIT = 16
Operation = tuple[int, int, int]


def operations(seed: int) -> list[Operation]:
    rng = random.Random(seed)
    ops: list[Operation] = [(0, 0, 0), (0, 1, 0xFF), (1, 0, 0)]
    values = [0x00, 0xFF, 0x5A, 0x96]
    values.extend(rng.randrange(256) for _ in range(10))
    for frame_index, value in enumerate(values):
        ops.extend((1, 0, rng.randrange(256)) for _ in range(rng.randint(0, 4)))
        ops.append((1, 1, value))
        busy_start_at = rng.randint(3, 8 * CLKS_PER_BIT)
        for elapsed in range(1, 10 * CLKS_PER_BIT + 1):
            start = 1 if elapsed == busy_start_at else 0
            ops.append((1, start, rng.randrange(256)))
        if frame_index == 5:
            ops.append((1, 1, 0xA7))
            ops.extend((1, 0, 0) for _ in range(23))
            ops.extend([(0, 0, 0), (0, 1, 0x11), (1, 0, 0)])
    return ops


def discover_module_name(design: Path) -> str:
    source = design.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//[^\r\n]*", "", source)
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)", source)
    if match is None:
        raise RuntimeError(f"no module declaration found in {design}")
    return match.group(1)


def make_tb(ops: list[Operation], module_name: str) -> str:
    body = []
    for index, (reset_value, start, value) in enumerate(ops):
        body.append(
            f"    rst_n=1'b{reset_value}; tx_start=1'b{start}; tx_data=8'h{value:02x}; "
            f"#4; clk=1; #1; $display(\"TRACE {index} %b %b\", tx_serial, tx_busy); "
            "#4; clk=0; #1;"
        )
    return "\n".join([
        "`timescale 1ns/1ps",
        "module oracle_tb;",
        "  reg clk, rst_n, tx_start; reg [7:0] tx_data; wire tx_serial, tx_busy;",
        f"  {module_name} #(.CLKS_PER_BIT(16)) dut(.clk(clk), .rst_n(rst_n),",
        "    .tx_start(tx_start), .tx_data(tx_data), .tx_serial(tx_serial), .tx_busy(tx_busy));",
        "  initial begin",
        "    clk=0; rst_n=0; tx_start=0; tx_data=0;",
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
    root = Path(tempfile.mkdtemp(prefix=f"uart_{args.seed}_", dir=args.workdir))
    result = {"pass": False, "seed": args.seed, "checked": 0, "first_mismatch": None}
    try:
        rtl_trace = simulate(args.rtl.resolve(), make_tb(ops, "uart_tx"), root / "rtl", args.tools)
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
