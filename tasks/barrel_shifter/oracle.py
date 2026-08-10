#!/usr/bin/env python3
"""Seeded randomized differential oracle for barrel_shifter."""

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


Vector = tuple[int, int, int, int]


def vectors(seed: int) -> list[Vector]:
    rng = random.Random(seed)
    result: list[Vector] = []
    for mode in range(4):
        for value in (0x00, 0xFF, 0x01, 0x80, 0xA5, 0x96):
            for distance in (0, 1, 7, 8, 9, 15, 16):
                result.append((8, value, distance, mode))
    # Distances 8 and 9 distinguish modulo-5 rotation from low-three-bit shortcuts;
    # for logical modes they also enforce the distance >= WIDTH zero result.
    for mode in range(4):
        for value in (0x01, 0x11, 0x16, 0x1F):
            for distance in (0, 1, 4, 5, 6, 8, 9, 15):
                result.append((5, value, distance, mode))
    for _ in range(192):
        result.append((8, rng.randrange(256), rng.randrange(32), rng.randrange(4)))
    for _ in range(96):
        result.append((5, rng.randrange(32), rng.randrange(32), rng.randrange(4)))
    rng.shuffle(result)
    return result


def discover_module_name(design: Path) -> str:
    source = design.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//[^\r\n]*", "", source)
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)", source)
    if match is None:
        raise RuntimeError(f"no module declaration found in {design}")
    return match.group(1)


def make_tb(items: list[Vector], module_name: str) -> str:
    body = []
    for index, (width, value, distance, mode) in enumerate(items):
        if width == 8:
            body.append(
                f"    data_in_8=8'h{value:02x}; shift_amt_8=8'd{distance}; "
                f"mode_8=2'd{mode}; #1; $display(\"TRACE {index} %h\", data_out_8);"
            )
        else:
            body.append(
                f"    data_in_5=5'h{value:02x}; shift_amt_5=5'd{distance}; "
                f"mode_5=2'd{mode}; #1; $display(\"TRACE {index} %h\", data_out_5);"
            )
    return "\n".join(
        [
            "`timescale 1ns/1ps",
            "module oracle_tb;",
            "  reg [7:0] data_in_8; reg [7:0] shift_amt_8; reg [1:0] mode_8;",
            "  wire [7:0] data_out_8;",
            "  reg [4:0] data_in_5; reg [4:0] shift_amt_5; reg [1:0] mode_5;",
            "  wire [4:0] data_out_5;",
            f"  {module_name} #(.WIDTH(8)) dut_8(.data_in(data_in_8),",
            "    .shift_amt(shift_amt_8), .mode(mode_8), .data_out(data_out_8));",
            f"  {module_name} #(.WIDTH(5)) dut_5(.data_in(data_in_5),",
            "    .shift_amt(shift_amt_5), .mode(mode_5), .data_out(data_out_5));",
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
        rtl_trace = simulate(
            args.rtl.resolve(), make_tb(items, "barrel_shifter"), root / "rtl", args.tools
        )
        ref_path = args.ref.resolve()
        ref_trace = simulate(
            ref_path, make_tb(items, discover_module_name(ref_path)), root / "ref", args.tools
        )
        result["checked"] = min(len(rtl_trace), len(ref_trace))
        if len(rtl_trace) != len(ref_trace):
            result["first_mismatch"] = f"trace length rtl={len(rtl_trace)} ref={len(ref_trace)}"
        else:
            for index, (got, expected) in enumerate(zip(rtl_trace, ref_trace)):
                if got != expected:
                    result["first_mismatch"] = (
                        f"vector {index}: rtl={got!r} ref={expected!r} "
                        f"inputs=(width,value,distance,mode)={items[index]}"
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
