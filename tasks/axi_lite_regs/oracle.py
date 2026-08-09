#!/usr/bin/env python3
"""Seeded transaction-level differential oracle for axi_lite_regs."""

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


def operations(seed: int) -> list[tuple]:
    rng = random.Random(seed)
    ops: list[tuple] = [
        ("split_probe", 0, 0x13579BDF, 15, 2, 1),
        ("write", 4, 0x2468ACE0, 15, 2, 0, 3),
        ("read", 4, 1, 3),
        ("write", 8, 0xDEADBEEF, 5, 0, 3, 2),
        ("read", 8, 3, 0),
        ("write", 0x10, 0xFFFFFFFF, 15, 1, 2, 1),
        ("read", 0x10, 2, 2),
    ]
    addresses = [0, 4, 8, 12, 0x10, 2, 0x100]
    for phase in range(5):
        for _ in range(12):
            address = rng.choice(addresses)
            ops.append((
                "write", address, rng.randrange(1 << 32), rng.randrange(16),
                rng.randrange(4), rng.randrange(4), rng.randrange(4),
            ))
            if rng.random() < 0.85:
                ops.append(("read", rng.choice(addresses), rng.randrange(4), rng.randrange(4)))
        if phase != 4:
            ops.append(("reset", rng.randrange(1, 3)))
            for address in (0, 4, 8, 12):
                ops.append(("read", address, rng.randrange(4), rng.randrange(4)))
    return ops


def discover_module_name(design: Path) -> str:
    source = design.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//[^\r\n]*", "", source)
    match = re.search(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)", source)
    if match is None:
        raise RuntimeError(f"no module declaration found in {design}")
    return match.group(1)


def make_tb(ops: list[tuple], module_name: str) -> str:
    body: list[str] = []
    for op in ops:
        if op[0] == "write":
            _, address, data, strobes, aw_delay, w_delay, b_delay = op
            body.append(
                f"    do_write(32'h{address:08x},32'h{data:08x},4'h{strobes:x},"
                f"{aw_delay},{w_delay},{b_delay});"
            )
        elif op[0] == "read":
            _, address, ar_delay, r_delay = op
            body.append(f"    do_read(32'h{address:08x},{ar_delay},{r_delay});")
        elif op[0] == "split_probe":
            _, address, data, strobes, aw_to_read, b_delay = op
            body.append(
                f"    split_probe(32'h{address:08x},32'h{data:08x},4'h{strobes:x},"
                f"{aw_to_read},{b_delay});"
            )
        else:
            body.append(f"    do_reset({op[1]});")

    return "\n".join([
        "`timescale 1ns/1ps",
        "module oracle_tb;",
        "  reg clk,rst_n;",
        "  reg [31:0] s_axi_awaddr; reg s_axi_awvalid; wire s_axi_awready;",
        "  reg [31:0] s_axi_wdata; reg [3:0] s_axi_wstrb; reg s_axi_wvalid; wire s_axi_wready;",
        "  wire [1:0] s_axi_bresp; wire s_axi_bvalid; reg s_axi_bready;",
        "  reg [31:0] s_axi_araddr; reg s_axi_arvalid; wire s_axi_arready;",
        "  wire [31:0] s_axi_rdata; wire [1:0] s_axi_rresp; wire s_axi_rvalid; reg s_axi_rready;",
        f"  {module_name} dut(",
        "    .clk(clk),.rst_n(rst_n),.s_axi_awaddr(s_axi_awaddr),.s_axi_awvalid(s_axi_awvalid),.s_axi_awready(s_axi_awready),",
        "    .s_axi_wdata(s_axi_wdata),.s_axi_wstrb(s_axi_wstrb),.s_axi_wvalid(s_axi_wvalid),.s_axi_wready(s_axi_wready),",
        "    .s_axi_bresp(s_axi_bresp),.s_axi_bvalid(s_axi_bvalid),.s_axi_bready(s_axi_bready),",
        "    .s_axi_araddr(s_axi_araddr),.s_axi_arvalid(s_axi_arvalid),.s_axi_arready(s_axi_arready),",
        "    .s_axi_rdata(s_axi_rdata),.s_axi_rresp(s_axi_rresp),.s_axi_rvalid(s_axi_rvalid),.s_axi_rready(s_axi_rready));",
        "  always #5 clk=~clk;",
        "  always @(posedge clk) begin",
        "    if(rst_n) begin",
        "      if(s_axi_awvalid&&s_axi_awready) $display(\"TRACE AW %h\",s_axi_awaddr);",
        "      if(s_axi_wvalid&&s_axi_wready) $display(\"TRACE W %h %h\",s_axi_wdata,s_axi_wstrb);",
        "      if(s_axi_bvalid&&s_axi_bready) $display(\"TRACE B %h\",s_axi_bresp);",
        "      if(s_axi_arvalid&&s_axi_arready) $display(\"TRACE AR %h\",s_axi_araddr);",
        "      if(s_axi_rvalid&&s_axi_rready) $display(\"TRACE R %h %h\",s_axi_rdata,s_axi_rresp);",
        "    end",
        "  end",
        "  task send_aw; input [31:0] a; input integer d; begin",
        "    repeat(d) @(posedge clk); @(negedge clk); s_axi_awaddr=a; s_axi_awvalid=1;",
        "    while(s_axi_awready!==1) @(posedge clk); @(negedge clk); s_axi_awvalid=0;",
        "  end endtask",
        "  task send_w; input [31:0] dta; input [3:0] st; input integer d; begin",
        "    repeat(d) @(posedge clk); @(negedge clk); s_axi_wdata=dta; s_axi_wstrb=st; s_axi_wvalid=1;",
        "    while(s_axi_wready!==1) @(posedge clk); @(negedge clk); s_axi_wvalid=0;",
        "  end endtask",
        "  task take_b; input integer d; begin",
        "    repeat(d) @(posedge clk); @(negedge clk); s_axi_bready=1;",
        "    while(s_axi_bvalid!==1) @(posedge clk); @(posedge clk); @(negedge clk); s_axi_bready=0;",
        "  end endtask",
        "  task do_write; input [31:0] a; input [31:0] dta; input [3:0] st;",
        "    input integer ad; input integer wd; input integer bd; begin",
        "    fork send_aw(a,ad); send_w(dta,st,wd); take_b(bd); join",
        "  end endtask",
        "  task do_read; input [31:0] a; input integer ad; input integer rd; begin",
        "    fork",
        "      begin repeat(ad) @(posedge clk); @(negedge clk); s_axi_araddr=a; s_axi_arvalid=1;",
        "        while(s_axi_arready!==1) @(posedge clk); @(negedge clk); s_axi_arvalid=0; end",
        "      begin repeat(rd) @(posedge clk); @(negedge clk); s_axi_rready=1;",
        "        while(s_axi_rvalid!==1) @(posedge clk); @(posedge clk); @(negedge clk); s_axi_rready=0; end",
        "    join",
        "  end endtask",
        "  task split_probe; input [31:0] a; input [31:0] dta; input [3:0] st;",
        "    input integer gap; input integer bd; begin",
        "    send_aw(a,0); repeat(gap) @(posedge clk); do_read(a,0,1);",
        "    fork send_w(dta,st,0); take_b(bd); join",
        "  end endtask",
        "  task do_reset; input integer n; begin",
        "    @(negedge clk); rst_n=0; repeat(n) @(posedge clk); @(negedge clk); rst_n=1;",
        "  end endtask",
        "  initial begin",
        "    clk=0;rst_n=0;s_axi_awaddr=0;s_axi_awvalid=0;s_axi_wdata=0;s_axi_wstrb=0;s_axi_wvalid=0;",
        "    s_axi_bready=0;s_axi_araddr=0;s_axi_arvalid=0;s_axi_rready=0;",
        "    repeat(2) @(posedge clk); @(negedge clk); rst_n=1;",
        *body,
        "    repeat(3) @(posedge clk); $finish;",
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
        [str(tools / "iverilog"), "-g2005", "-s", "oracle_tb", "-o", str(image), str(design), str(tb_path)],
        text=True, capture_output=True, timeout=30, check=False,
    )
    if compiled.returncode != 0:
        raise RuntimeError(f"compile failed for {design}: {compiled.stderr.strip()}")
    simulated = subprocess.run([str(tools / "vvp"), str(image)], text=True, capture_output=True, timeout=30, check=False)
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
    root = Path(tempfile.mkdtemp(prefix=f"axi_{args.seed}_", dir=args.workdir))
    result = {"pass": False, "seed": args.seed, "checked": 0, "first_mismatch": None}
    try:
        rtl_trace = simulate(args.rtl.resolve(), make_tb(ops, "axi_lite_regs"), root / "rtl", args.tools)
        ref_path = args.ref.resolve()
        ref_trace = simulate(ref_path, make_tb(ops, discover_module_name(ref_path)), root / "ref", args.tools)
        result["checked"] = min(len(rtl_trace), len(ref_trace))
        if len(rtl_trace) != len(ref_trace):
            result["first_mismatch"] = f"transaction count rtl={len(rtl_trace)} ref={len(ref_trace)}"
        else:
            for index, (got, expected) in enumerate(zip(rtl_trace, ref_trace)):
                if got != expected:
                    result["first_mismatch"] = f"transaction {index}: rtl={got!r} ref={expected!r}"
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
