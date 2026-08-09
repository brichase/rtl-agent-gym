"""Standalone staged grader for rtl-agent-gym tasks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import re
import subprocess
import sys
from typing import Any

import yaml

from . import sandbox


@dataclass(frozen=True)
class TaskConfig:
    path: Path
    metadata: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.metadata["name"])

    @property
    def top(self) -> str:
        return str(self.metadata["top_module"])

    @property
    def timeout_s(self) -> float:
        return float(self.metadata.get("sim_timeout_s", 30))

    @property
    def oracle_runs(self) -> int:
        return int(self.metadata.get("oracle_runs", 3))

    @property
    def area_floor(self) -> int:
        return int(self.metadata.get("area_floor_cells", 0))


def resolve_task(task: str | Path) -> Path:
    candidate = Path(task)
    if candidate.is_dir():
        return candidate.resolve()
    for root in (Path("tasks"), Path("env/fixtures")):
        candidate = root / str(task)
        if candidate.is_dir():
            return candidate.resolve()
    raise FileNotFoundError(f"task directory not found: {task}")


def load_task(task: str | Path) -> TaskConfig:
    path = resolve_task(task)
    metadata_path = path / "task.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError(f"task.yaml must contain a mapping: {metadata_path}")
    for field in ("name", "top_module"):
        if field not in metadata:
            raise ValueError(f"task.yaml missing {field}: {metadata_path}")
    if metadata["name"] != path.name:
        raise ValueError(f"task name {metadata['name']!r} does not match directory {path.name!r}")
    return TaskConfig(path, metadata)


def _tool(name: str, tools: str | Path | None) -> str:
    return sandbox.tool_path(name, tools)


def _pass_from_tb(output: str) -> bool:
    return "TB_ALL_PASS" in output and "TB_FAIL" not in output


def compile_rtl(
    task: TaskConfig, rtl: str, *, tools: str | Path | None = None
) -> dict[str, Any]:
    result = sandbox.run_command(
        [_tool("iverilog", tools), "-g2005", "-s", task.top, "-o", "compiled.vvp", "agent.v"],
        {"agent.v": rtl},
        timeout_s=task.timeout_s,
    )
    return {
        "ok": result.ok,
        "stdout": result.stdout,
        "timed_out": result.timed_out,
        "elapsed_ms": round(result.elapsed_ms, 3),
    }


def run_testbench(
    task: TaskConfig,
    rtl: str,
    testbench: Path,
    *,
    tools: str | Path | None = None,
) -> dict[str, Any]:
    result = sandbox.run_commands(
        [
            [
                _tool("iverilog", tools),
                "-g2005",
                "-o",
                "simulation.vvp",
                "agent.v",
                "tb.v",
            ],
            [_tool("vvp", tools), "simulation.vvp"],
        ],
        {"agent.v": rtl, "tb.v": testbench},
        timeout_s=task.timeout_s,
    )
    return {
        "compile_ok": result.returncode == 0 and not result.timed_out,
        "passed": result.ok and _pass_from_tb(result.stdout),
        "stdout": result.stdout,
        "timed_out": result.timed_out,
        "elapsed_ms": round(result.elapsed_ms, 3),
    }


_CELL_PATTERNS = (
    re.compile(r"Number of cells:\s*(\d+)"),
    re.compile(r"^\s*(\d+)\s+cells\s*$", re.MULTILINE),
    re.compile(r"(?:Estimated number of LCs|Chip area for module).*?:\s*(\d+)"),
)
_DEPTH_PATTERNS = (
    re.compile(r"Longest topological path.*?length\s*[=:]?\s*(\d+)", re.IGNORECASE),
    re.compile(r"Longest path.*?\b(\d+)\b", re.IGNORECASE),
)


def _last_match(patterns: tuple[re.Pattern[str], ...], output: str) -> int | None:
    for pattern in patterns:
        matches = pattern.findall(output)
        if matches:
            return int(matches[-1])
    return None


def synthesize_rtl(
    task: TaskConfig, rtl: str, *, tools: str | Path | None = None
) -> dict[str, Any]:
    script = (
        f"read_verilog design.v; hierarchy -check -top {task.top}; "
        f"synth -top {task.top}; tee -o metrics.txt stat; "
        "tee -a metrics.txt ltp -noff"
    )
    result = sandbox.run_commands(
        [
            [_tool("yosys", tools), "-Q", "-q", "-p", script],
            [
                sys.executable,
                "-c",
                "print(open('metrics.txt', encoding='utf-8').read())",
            ],
        ],
        {"design.v": rtl},
        timeout_s=task.timeout_s,
    )
    cells = _last_match(_CELL_PATTERNS, result.stdout)
    depth = _last_match(_DEPTH_PATTERNS, result.stdout)
    ok = result.ok and cells is not None and depth is not None
    return {
        "ok": ok,
        "cells": cells,
        "depth": depth,
        "stdout": result.stdout,
        "timed_out": result.timed_out,
        "elapsed_ms": round(result.elapsed_ms, 3),
    }


def _strip_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", " ", source)


def _mask_strings(source: str) -> str:
    return re.sub(r'"(?:\\.|[^"\\])*"', '""', source)


def _output_names(source: str) -> set[str]:
    names: set[str] = set()
    patterns = (
        re.compile(r"\boutput\b(.*?);", re.DOTALL),
        re.compile(r"\boutput\b(.*?)(?=\b(?:input|output|inout)\b|\)\s*;)", re.DOTALL),
    )
    ignored = {"output", "wire", "reg", "logic", "signed", "unsigned", "integer"}
    for pattern in patterns:
        for declaration in pattern.findall(source):
            declaration = re.sub(r"\[[^\]]*\]", " ", declaration)
            for part in declaration.split(","):
                identifiers = re.findall(r"\b[A-Za-z_]\w*\b", part)
                candidates = [item for item in identifiers if item not in ignored]
                if candidates:
                    names.add(candidates[-1])
    return names


def _initial_regions(source: str) -> list[str]:
    """Extract common Verilog initial statements without swallowing later assigns."""
    regions: list[str] = []
    for initial in re.finditer(r"\binitial\b", source):
        start = initial.end()
        first = re.search(r"\S", source[start:])
        if first is None:
            continue
        statement_start = start + first.start()
        if re.match(r"begin\b", source[statement_start:]):
            depth = 0
            end_position = len(source)
            for token in re.finditer(r"\b(?:begin|end)\b", source[statement_start:]):
                if token.group() == "begin":
                    depth += 1
                else:
                    depth -= 1
                    if depth == 0:
                        end_position = statement_start + token.end()
                        break
            regions.append(source[statement_start:end_position])
        else:
            semicolon = source.find(";", statement_start)
            end_position = len(source) if semicolon < 0 else semicolon + 1
            regions.append(source[statement_start:end_position])
    return regions


def static_sanity(rtl: str) -> tuple[bool, list[str]]:
    source = _mask_strings(_strip_comments(rtl))
    reasons: list[str] = []
    if re.search(r"`\s*include\b", source, re.IGNORECASE):
        reasons.append("submission uses `include")
    if re.search(r"\$readmem(?:b|h)?\b", source, re.IGNORECASE):
        reasons.append("submission uses $readmem*")
    if re.search(r"\b[A-Za-z_]\w*\s*\.\s*[A-Za-z_]\w*", source):
        reasons.append("submission uses a hierarchical reference")

    outputs = _output_names(source)
    for region in _initial_regions(source):
        for output in outputs:
            if re.search(rf"\b{re.escape(output)}\b\s*(?:<=|=(?!=))", region):
                reasons.append(f"initial block drives DUT output {output}")
    return not reasons, reasons


def _mangle_reference(source: str, top: str, mangled: str) -> str:
    rewritten, count = re.subn(
        rf"(\bmodule\s+){re.escape(top)}\b", rf"\g<1>{mangled}", source, count=1
    )
    if count != 1:
        raise ValueError(f"reference does not define top module {top}")
    return rewritten


def run_oracle(
    task: TaskConfig,
    rtl: str,
    reference: str,
    seeds: list[int],
    *,
    tools: str | Path | None = None,
) -> dict[str, Any]:
    logs: list[str] = []
    parsed: list[dict[str, Any]] = []
    rng = random.Random((seeds[0] if seeds else 0) ^ 0x5A17)
    for seed in seeds:
        mangled = f"ref_{rng.getrandbits(32):08x}"
        try:
            mangled_source = _mangle_reference(reference, task.top, mangled)
        except ValueError as error:
            return {"passed": False, "stdout": str(error), "runs": parsed}
        ref_name = f"{mangled}.v"
        result = sandbox.run_command(
            [
                sys.executable,
                "oracle.py",
                "--rtl",
                "agent.v",
                "--ref",
                ref_name,
                "--seed",
                str(seed),
                "--workdir",
                ".",
                "--tools",
                str(sandbox.tools_dir(tools)),
            ],
            {
                "oracle.py": task.path / "oracle.py",
                "agent.v": rtl,
                ref_name: mangled_source,
            },
            timeout_s=task.timeout_s,
        )
        logs.append(f"seed={seed}\n{result.stdout}")
        payload: dict[str, Any] | None = None
        for line in reversed(result.stdout.splitlines()):
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                payload = candidate
                break
        if payload is not None:
            parsed.append(payload)
        if not result.ok or payload is None or payload.get("pass") is not True:
            return {"passed": False, "stdout": _truncate("\n".join(logs)), "runs": parsed}
    return {"passed": True, "stdout": _truncate("\n".join(logs)), "runs": parsed}


def _truncate(value: str, limit: int = sandbox.OUTPUT_LIMIT) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value
    marker = b"\n[truncated]\n"
    return (encoded[: limit - len(marker)] + marker).decode("utf-8", errors="replace")


def _versions(tools: str | Path | None) -> dict[str, str]:
    versions: dict[str, str] = {}
    for name, args in (("iverilog", ["-V"]), ("yosys", ["--version"])):
        try:
            completed = subprocess.run(
                [_tool(name, tools), *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
                check=False,
            )
            versions[name] = completed.stdout.splitlines()[0] if completed.stdout else "unknown"
        except (OSError, subprocess.TimeoutExpired) as error:
            versions[name] = f"unavailable: {error}"
    return versions


def _empty_result(task: TaskConfig, seed: int, tools: str | Path | None) -> dict[str, Any]:
    return {
        "task": task.name,
        "compile_ok": False,
        "visible_pass": False,
        "hidden_pass": False,
        "oracle_pass": False,
        "sanity_ok": False,
        "area_cells": None,
        "ref_cells": None,
        "area_norm": None,
        "depth": None,
        "ref_depth": None,
        "depth_norm": None,
        "cost_score": None,
        "reward": 0.0,
        "flagged": False,
        "fail_reason": None,
        "stage_logs": {},
        "seed": seed,
        "oracle_seeds": [seed + index for index in range(task.oracle_runs)],
        "tool_versions": _versions(tools),
    }


def grade(
    task_arg: str | Path,
    rtl_arg: str | Path,
    *,
    seed: int = 0,
    tools: str | Path | None = None,
) -> dict[str, Any]:
    """Run the gated ladder and return a JSON-serializable result."""
    task = load_task(task_arg)
    rtl = Path(rtl_arg).read_text(encoding="utf-8")
    reference = (task.path / "ref" / "ref.v").read_text(encoding="utf-8")
    result = _empty_result(task, seed, tools)
    logs: dict[str, str] = result["stage_logs"]

    compile_result = compile_rtl(task, rtl, tools=tools)
    logs["compile"] = compile_result["stdout"]
    if not compile_result["ok"]:
        result["fail_reason"] = "compile failed" + (
            " (timeout)" if compile_result["timed_out"] else ""
        )
        return result
    result["compile_ok"] = True

    visible = run_testbench(task, rtl, task.path / "tb_visible.v", tools=tools)
    logs["visible"] = visible["stdout"]
    if not visible["passed"]:
        result["reward"] = 0.1
        result["fail_reason"] = "visible testbench timeout" if visible["timed_out"] else "visible testbench failed"
        return result
    result["visible_pass"] = True

    hidden = run_testbench(task, rtl, task.path / "tb_hidden.v", tools=tools)
    logs["hidden"] = hidden["stdout"]
    if not hidden["passed"]:
        result["reward"] = 0.2
        result["fail_reason"] = "hidden testbench timeout" if hidden["timed_out"] else "hidden testbench failed"
        return result
    result["hidden_pass"] = True

    oracle = run_oracle(task, rtl, reference, result["oracle_seeds"], tools=tools)
    logs["oracle"] = oracle["stdout"]
    result["oracle_results"] = oracle["runs"]
    if not oracle["passed"]:
        result["reward"] = 0.2
        result["flagged"] = True
        result["fail_reason"] = "oracle failed"
        return result
    result["oracle_pass"] = True

    static_ok, static_reasons = static_sanity(rtl)
    logs["sanity"] = "sanity checks passed" if static_ok else "\n".join(static_reasons)
    if not static_ok:
        result["reward"] = 0.2
        result["flagged"] = True
        result["fail_reason"] = "; ".join(static_reasons)
        return result

    agent_synth = synthesize_rtl(task, rtl, tools=tools)
    logs["synth_agent"] = agent_synth["stdout"]
    result["area_cells"] = agent_synth["cells"]
    result["depth"] = agent_synth["depth"]
    if not agent_synth["ok"]:
        result["reward"] = 0.2
        result["flagged"] = True
        result["fail_reason"] = "agent synthesis failed"
        return result
    if int(agent_synth["cells"]) < task.area_floor:
        result["reward"] = 0.2
        result["flagged"] = True
        result["fail_reason"] = (
            f"cell floor failed: {agent_synth['cells']} < {task.area_floor}"
        )
        logs["sanity"] = result["fail_reason"]
        return result

    # Deliberately fresh within every grade call; no cross-run reference cache.
    ref_synth = synthesize_rtl(task, reference, tools=tools)
    logs["synth_ref"] = ref_synth["stdout"]
    result["ref_cells"] = ref_synth["cells"]
    result["ref_depth"] = ref_synth["depth"]
    if not ref_synth["ok"] or not ref_synth["cells"] or not ref_synth["depth"]:
        result["reward"] = 0.2
        result["flagged"] = True
        result["fail_reason"] = "reference synthesis failed"
        return result

    result["sanity_ok"] = True
    result["area_norm"] = agent_synth["cells"] / ref_synth["cells"]
    result["depth_norm"] = agent_synth["depth"] / ref_synth["depth"]
    cost_score = max(
        0.0,
        min(1.0, 2.0 - (result["area_norm"] + result["depth_norm"]) / 2.0),
    )
    result["cost_score"] = cost_score
    result["reward"] = 0.7 + 0.3 * cost_score
    result["fail_reason"] = None
    return result


def _expectation_matches(result: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    errors: list[str] = []
    for key, wanted in expected.items():
        if key == "max_reward":
            if float(result["reward"]) > float(wanted) + 1e-9:
                errors.append(f"reward {result['reward']:.3f} > {wanted}")
        elif key == "min_reward":
            if float(result["reward"]) + 1e-9 < float(wanted):
                errors.append(f"reward {result['reward']:.3f} < {wanted}")
        elif key == "reward":
            if not math.isclose(float(result["reward"]), float(wanted), abs_tol=1e-9):
                errors.append(f"reward {result['reward']:.3f} != {wanted}")
        elif result.get(key) != wanted:
            errors.append(f"{key}={result.get(key)!r}, expected {wanted!r}")
    return not errors, "; ".join(errors)


def _task_dirs() -> list[Path]:
    directories: list[Path] = []
    for root in (Path("tasks"), Path("env/fixtures")):
        if root.is_dir():
            directories.extend(path.parent for path in root.glob("*/task.yaml"))
    return sorted(directories)


def smoke_test(*, tools: str | Path | None = None) -> int:
    cases: list[tuple[str, Path, Path, dict[str, Any]]] = []
    tasks_by_name: dict[str, Path] = {}
    discovery_errors: list[tuple[str, str]] = []
    for task_dir in _task_dirs():
        metadata = yaml.safe_load((task_dir / "task.yaml").read_text(encoding="utf-8"))
        task_name = str(metadata["name"])
        tasks_by_name[task_name] = task_dir
        cases.append((f"{task_name}/ref", task_dir, task_dir / "ref" / "ref.v", {"min_reward": 0.95}))
        broken = task_dir / "broken"
        if broken.is_dir():
            expected_path = broken / "expected.yaml"
            expected_data = (
                yaml.safe_load(expected_path.read_text(encoding="utf-8"))
                if expected_path.is_file()
                else {}
            )
            expected_data = expected_data or {}
            for rtl_path in sorted(broken.glob("*.v")):
                expected = expected_data.get(rtl_path.stem, expected_data.get(rtl_path.name))
                if not isinstance(expected, dict):
                    discovery_errors.append((f"{task_name}/{rtl_path.stem}", "missing expectation"))
                    continue
                cases.append((f"{task_name}/{rtl_path.stem}", task_dir, rtl_path, expected))

    redteam = Path("redteam")
    if redteam.is_dir():
        for expected_path in sorted(redteam.glob("*/expected.yaml")):
            attack_dir = expected_path.parent
            metadata = yaml.safe_load(expected_path.read_text(encoding="utf-8")) or {}
            task_name = str(metadata.get("task", ""))
            task_dir = tasks_by_name.get(task_name)
            submission = attack_dir / "submission.v"
            expected = metadata.get("expect")
            if task_dir is None or not submission.is_file() or not isinstance(expected, dict):
                discovery_errors.append((f"redteam/{attack_dir.name}", "invalid redteam layout or unknown task"))
                continue
            cases.append((f"redteam/{attack_dir.name}", task_dir, submission, expected))

    rows: list[tuple[str, str, str, str]] = []
    failures = 0
    for name, task_dir, rtl_path, expected in cases:
        try:
            result = grade(task_dir, rtl_path, tools=tools)
            passed, detail = _expectation_matches(result, expected)
            rows.append((name, f"{result['reward']:.3f}", "PASS" if passed else "FAIL", detail or result.get("fail_reason") or "all gates pass"))
            failures += not passed
        except Exception as error:  # keep the harness running to show all bad cases
            rows.append((name, "-", "ERROR", str(error)))
            failures += 1
    for name, detail in discovery_errors:
        rows.append((name, "-", "ERROR", detail))
        failures += 1

    widths = [len(title) for title in ("case", "reward", "status", "detail")]
    for row in rows:
        widths = [max(width, len(str(value))) for width, value in zip(widths, row)]
    header = ("case", "reward", "status", "detail")
    print("  ".join(value.ljust(width) for value, width in zip(header, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(str(value).ljust(width) for value, width in zip(row, widths)))
    print(f"\nsmoke-test: {len(rows) - failures} passed, {failures} failed")
    return 1 if failures else 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", help="task name or directory")
    parser.add_argument("--rtl", help="submission Verilog file")
    parser.add_argument("--json-out", help="write the result JSON here")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--tools", help="OSS CAD Suite bin directory")
    parser.add_argument("--smoke", action="store_true", help="run refs, broken cases, and redteam")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.smoke:
        return smoke_test(tools=args.tools)
    if not args.task or not args.rtl:
        _parser().error("--task and --rtl are required unless --smoke is used")
    result = grade(args.task, args.rtl, seed=args.seed, tools=args.tools)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.json_out:
        Path(args.json_out).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
