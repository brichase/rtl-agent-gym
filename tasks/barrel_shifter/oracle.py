#!/usr/bin/env python3
"""Seeded randomized differential oracle for barrel_shifter."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TOOLS = Path("/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin")


def vectors(seed: int) -> list[tuple[int, int, int]]:
    rng = random.Random(seed)
    result: list[tuple[int, int, int]] = []
    for mode in range(4):
        for value in (0x00, 0xFF, 0x01, 0x80, 0xA5, 0x96):
            for distance in (0, 1, 7, 8, 9, 15, 16):
                result.append((value, distance, mode))
    for _ in range(192):
        result.append((rng.randrange(256), rng.randrange(32), rng.randrange(4)))
    rng.shuffle(result)
    return result


def make_tb(items: list[tuple[int, int, int]]) -> str:
    body = []
    for index, (value, distance, mode) in enumerate(items):
        body.append(
            f"    data_in=8'h{value:02x}; shift_amt=8'd{distance}; "
            f"mode=2'd{mode}; #1; $display(\"TRACE {index} %h\", data_out);"
        )
    return "\n".join(
        [
            "`timescale 1ns/1ps",
            "module oracle_tb;",
            "  reg [7:0] data_in; reg [7:0] shift_amt; reg [1:0] mode;",
            "  wire [7:0] data_out;",
            "  barrel_shifter #(.WIDTH(8)) dut(.data_in(data_in),",
            "    .shift_amt(shift_amt), .mode(mode), .data_out(data_out));",
            "  initial begin",
            *body,
            "    $finish;",
            "  end",
            "endmodule",
            "",
        ]
    )


def simulate(design: Path, tb_text: str, run_dir: Path, tools: Path) -> list[str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    tb_path = run_dir / "oracle_tb.v"
    image = run_dir / "sim.vvp"
    tb_path.write_text(tb_text, encoding="utf-8")
    compile_run = subprocess.run(
        [str(tools / "iverilog"), "-g2005", "-s", "oracle_tb", "-o", str(image),
         str(design), str(tb_path)],
        text=True, capture_output=True, timeout=30, check=False,
    )
    if compile_run.returncode != 0:
        raise RuntimeError(f"compile failed for {design}: {compile_run.stderr.strip()}")
    sim_run = subprocess.run(
        [str(tools / "vvp"), str(image)], text=True, capture_output=True,
        timeout=30, check=False,
    )
    if sim_run.returncode != 0:
        raise RuntimeError(f"simulation failed for {design}: {sim_run.stderr.strip()}")
    return [line for line in sim_run.stdout.splitlines() if line.startswith("TRACE ")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rtl", required=True, type=Path)
    parser.add_argument("--ref", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--tools", type=Path, default=DEFAULT_TOOLS)
    args = parser.parse_args()
    items = vectors(args.seed)
    args.workdir.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=f"barrel_{args.seed}_", dir=args.workdir))
    result = {"pass": False, "seed": args.seed, "checked": 0, "first_mismatch": None}
    try:
        rtl_trace = simulate(args.rtl.resolve(), make_tb(items), root / "rtl", args.tools)
        ref_trace = simulate(args.ref.resolve(), make_tb(items), root / "ref", args.tools)
        result["checked"] = min(len(rtl_trace), len(ref_trace))
        if len(rtl_trace) != len(ref_trace):
            result["first_mismatch"] = f"trace length rtl={len(rtl_trace)} ref={len(ref_trace)}"
        else:
            for index, (got, expected) in enumerate(zip(rtl_trace, ref_trace)):
                if got != expected:
                    result["first_mismatch"] = (
                        f"vector {index}: rtl={got!r} ref={expected!r} inputs={items[index]}"
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
