#!/usr/bin/env python3
"""Seeded transaction-sequence differential oracle for gray_counter."""

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


def operations(seed: int) -> list[tuple[str, int]]:
    rng = random.Random(seed)
    result: list[tuple[str, int]] = [("cycle", 0), ("cycle", 0)]
    result.extend(("cycle", 1) for _ in range(20))
    result.extend([("probe_reset", 0), ("cycle", 0), ("cycle", 1)])
    for _ in range(4):
        result.extend(("cycle", 1) for _ in range(rng.randint(3, 18)))
        result.extend(("cycle", 1) for _ in range(rng.randint(0, 4)))
        result.append(("probe_reset", 0))
        result.extend(("cycle", 0) for _ in range(rng.randint(1, 3)))
        result.extend(("cycle", 1) for _ in range(rng.randint(2, 10)))
    result.extend(("cycle", 1) for _ in range(20))
    return result


def discover_module_name(design: Path) -> str:
    source = design.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//[^\r\n]*", "", source)
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)", source)
    if match is None:
        raise RuntimeError(f"no module declaration found in {design}")
    return match.group(1)


def make_tb(ops: list[tuple[str, int]], module_name: str) -> str:
    body: list[str] = []
    trace_index = 0
    for kind, reset_value in ops:
        if kind == "cycle":
            body.append(
                f"    rst_n=1'b{reset_value}; #4; clk=1'b1; #1; "
                f"$display(\"TRACE {trace_index} %h\", gray); #4; clk=1'b0; #1;"
            )
        else:
            body.append(
                f"    rst_n=1'b1; #2; rst_n=1'b0; #1; "
                f"$display(\"TRACE {trace_index} %h\", gray); #1;"
            )
        trace_index += 1
    return "\n".join(
        [
            "`timescale 1ns/1ps",
            "module oracle_tb;",
            "  reg clk; reg rst_n; wire [3:0] gray;",
            f"  {module_name} #(.N(4)) dut(.clk(clk), .rst_n(rst_n), .gray(gray));",
            "  initial begin",
            "    clk=1'b0; rst_n=1'b0;",
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
    ops = operations(args.seed)
    args.workdir.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=f"gray_{args.seed}_", dir=args.workdir))
    result = {"pass": False, "seed": args.seed, "checked": 0, "first_mismatch": None}
    try:
        rtl_trace = simulate(
            args.rtl.resolve(), make_tb(ops, "gray_counter"), root / "rtl", args.tools
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
                        f"event {index}: rtl={got!r} ref={expected!r} operation={ops[index]}"
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
