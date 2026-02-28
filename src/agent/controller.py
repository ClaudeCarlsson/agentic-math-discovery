"""Agent Controller: Claude CLI-driven research loop with live observability.

The agent operates in cycles, each consisting of:
1. PLAN   - Claude decides what to explore (via claude CLI)
2. EXECUTE - Tools run locally (explore, check models, score)
3. INTERPRET - Claude analyzes results and proposes discoveries
4. ACT    - Discoveries are added to the library

Requires the Claude Code CLI: npm install -g @anthropic-ai/claude-code
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.agent.tools import ToolExecutor
from src.library.manager import LibraryManager

console = Console()


@dataclass
class CycleReport:
    """Summary of one research cycle."""

    cycle_number: int
    goal: str
    plan: str
    candidates_generated: int
    candidates_with_models: int
    top_candidates: list[dict[str, Any]]
    conjectures: list[dict[str, Any]]
    discoveries: list[dict[str, Any]]
    duration_seconds: float
    agent_reasoning: str = ""


@dataclass
class AgentConfig:
    """Configuration for the agent."""

    model: str = "claude-opus-4-6"
    max_cycles: int = 10
    goal: str = "Explore broadly: find novel algebraic structures"
    explore_depth: int = 2
    max_model_size: int = 6
    score_threshold: float = 0.3
    effort: str = "high"
    base_structures: list[str] = field(default_factory=lambda: [
        "Group", "Ring", "Lattice", "Quasigroup",
    ])


SYSTEM_PROMPT = """\
You are a mathematical research agent specializing in automated theory formation \
in universal algebra. Your goal is to discover structurally novel, non-trivial \
mathematical concepts by exploring the space of algebraic signatures.

## Available Structural Moves

- ABSTRACT: Find common axioms between two structures
- DUALIZE: Swap argument order of operations
- COMPLETE: Add identity, inverse, second operation, or norm
- QUOTIENT: Add commutativity or idempotence
- INTERNALIZE: Create Hom-objects (curry/eval)
- TRANSFER: Create structure-preserving maps between two structures
- DEFORM: Add a deformation parameter to an axiom (q-deformation)

## What Makes a Structure Interesting

- It has non-trivial finite models (not just the 1-element model)
- Its model spectrum shows a pattern (e.g., only at prime sizes, only powers of 2)
- It combines axiom types that don't usually appear together
- It bridges two mathematical domains (e.g., order theory + group theory)
- It has a simple description but rich model theory

## Current Research Goal

{goal}"""


def _format_elapsed(seconds: float) -> str:
    """Format elapsed time as a human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s"


class AgentController:
    """Orchestrates the Claude CLI-driven mathematical discovery loop."""

    def __init__(self, config: AgentConfig, library: LibraryManager):
        self.config = config
        self.library = library
        self.tools = ToolExecutor(library)
        self.history: list[CycleReport] = []
        self._cycle_start: float = 0.0

    def _log(self, msg: str, style: str = "") -> None:
        """Print a timestamped log line relative to cycle start."""
        elapsed = time.time() - self._cycle_start if self._cycle_start else 0
        ts = f"[dim][{_format_elapsed(elapsed):>6s}][/dim]"
        if style:
            console.print(f"{ts} [{style}]{msg}[/{style}]")
        else:
            console.print(f"{ts} {msg}")

    def _call_claude(self, prompt: str, system: str, label: str = "Thinking") -> str:
        """Call the Claude CLI with a live spinner showing elapsed time."""
        cmd = [
            "claude", "--print",
            "--model", self.config.model,
            "--effort", self.config.effort,
            "--output-format", "text",
            "--tools", "",
            "--no-session-persistence",
            "--system-prompt", system,
        ]

        # Allow spawning from inside an existing Claude Code session
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        call_start = time.time()
        stop_event = threading.Event()

        def update_spinner(status):
            while not stop_event.is_set():
                e = time.time() - call_start
                cycle_e = time.time() - self._cycle_start if self._cycle_start else e
                status.update(
                    f"[bold cyan]{label}[/bold cyan] "
                    f"[dim]({_format_elapsed(e)} elapsed, "
                    f"cycle {_format_elapsed(cycle_e)})[/dim]"
                )
                stop_event.wait(1.0)

        with console.status(
            f"[bold cyan]{label}[/bold cyan]", spinner="dots"
        ) as status:
            timer = threading.Thread(target=update_spinner, args=(status,), daemon=True)
            timer.start()

            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
            )

            stop_event.set()
            timer.join()

        elapsed = time.time() - call_start

        if result.returncode != 0:
            stderr = result.stderr.strip()[:500]
            self._log(f"{label} FAILED after {_format_elapsed(elapsed)}", "bold red")
            raise RuntimeError(f"Claude CLI failed (exit {result.returncode}): {stderr}")

        response = result.stdout.strip()
        # Show a brief summary of the response length
        lines = response.count("\n") + 1
        self._log(
            f"{label} [green]done[/green] "
            f"[dim]({_format_elapsed(elapsed)}, {lines} lines)[/dim]"
        )
        return response

    def run(self, num_cycles: int | None = None) -> list[CycleReport]:
        """Run the agent for the specified number of cycles."""
        self._check_claude_available()

        cycles = num_cycles or self.config.max_cycles
        reports = []

        console.print()
        console.rule(
            f"[bold]Starting {cycles} research cycle(s)[/bold]",
            style="blue",
        )
        console.print()

        for i in range(cycles):
            report = self._run_cycle(i + 1, cycles)
            reports.append(report)
            self.history.append(report)
            self._save_report(report)

        console.print()
        console.rule("[bold green]All cycles complete[/bold green]", style="green")
        total_disc = sum(len(r.discoveries) for r in reports)
        total_cand = sum(r.candidates_generated for r in reports)
        console.print(
            f"  Total: {total_cand} candidates explored, "
            f"{total_disc} discoveries added\n"
        )

        return reports

    def _check_claude_available(self) -> None:
        """Verify the claude CLI is installed and accessible."""
        try:
            env = os.environ.copy()
            env.pop("CLAUDECODE", None)
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=10, env=env,
            )
            if result.returncode != 0:
                raise RuntimeError("claude CLI returned non-zero exit code")
            version = result.stdout.strip()
            console.print(f"  [dim]Claude CLI: {version}[/dim]")
        except FileNotFoundError:
            raise RuntimeError(
                "Claude CLI not found. Install: npm install -g @anthropic-ai/claude-code"
            )

    def _run_cycle(self, cycle_num: int, total_cycles: int) -> CycleReport:
        """Execute one complete research cycle with live progress output."""
        self._cycle_start = time.time()

        system = SYSTEM_PROMPT.format(goal=self.config.goal)

        reasoning_parts = []
        candidates_generated = 0
        candidates_with_models = 0
        top_candidates = []
        discoveries = []
        conjectures = []

        # ── Cycle header ─────────────────────────────────────────
        console.rule(
            f"[bold cyan]Cycle {cycle_num}/{total_cycles}[/bold cyan]",
            style="cyan",
        )
        self._log(f"Goal: [italic]{self.config.goal}[/italic]")
        console.print()

        # ── Phase 1: PLAN ────────────────────────────────────────
        self._log("PLAN", "bold yellow")
        self._log("Asking Claude to design exploration strategy...")

        plan_prompt = self._build_plan_prompt(cycle_num)
        plan_response = self._call_claude(
            plan_prompt, system, label="Claude planning"
        )
        reasoning_parts.append(f"## Planning Phase\n\n{plan_response}")

        plan = self._parse_json_block(plan_response, "plan")
        if plan:
            reasoning = plan.get("reasoning", "")
            if reasoning:
                # Show a truncated version of Claude's reasoning
                short = reasoning[:200] + ("..." if len(reasoning) > 200 else "")
                self._log(f"Strategy: [italic]{short}[/italic]")
            explorations = plan.get("explorations", [])
            for exp in explorations:
                bases = exp.get("base_structures", [])
                moves = exp.get("moves", ["ALL"])
                depth = exp.get("depth", 1)
                self._log(
                    f"  Explore {bases} "
                    f"with [{', '.join(moves)}] "
                    f"at depth {depth}"
                )
        else:
            self._log("No structured plan parsed, using defaults", "yellow")
            plan = {
                "reasoning": "Fallback: using default exploration parameters.",
                "explorations": [{
                    "base_structures": self.config.base_structures,
                    "depth": self.config.explore_depth,
                }],
                "check_models_top_n": 10,
                "max_model_size": self.config.max_model_size,
            }

        console.print()

        # ── Phase 2: EXECUTE ─────────────────────────────────────
        self._log("EXECUTE", "bold yellow")
        exec_results = self._execute_plan_with_progress(plan)
        candidates_generated = exec_results.get("total_candidates", 0)
        top_candidates = exec_results.get("top_candidates", [])

        for mr in exec_results.get("model_results", []):
            if mr.get("total_models", 0) > 0:
                candidates_with_models += 1

        console.print()

        # ── Phase 3: INTERPRET ───────────────────────────────────
        self._log("INTERPRET", "bold yellow")
        self._log("Asking Claude to analyze results...")

        interpret_prompt = self._build_interpret_prompt(
            cycle_num, plan_response, exec_results
        )
        interpret_response = self._call_claude(
            interpret_prompt, system, label="Claude analyzing"
        )
        reasoning_parts.append(f"## Interpretation Phase\n\n{interpret_response}")

        decisions = self._parse_json_block(interpret_response, "decisions")

        if decisions:
            analysis = decisions.get("analysis", "")
            if analysis:
                short = analysis[:300] + ("..." if len(analysis) > 300 else "")
                self._log(f"Analysis: [italic]{short}[/italic]")
        else:
            self._log("No structured decisions parsed", "yellow")

        console.print()

        # ── Phase 4: ACT ─────────────────────────────────────────
        self._log("ACT", "bold yellow")

        if decisions:
            adds = decisions.get("add_to_library", [])
            conjs = decisions.get("conjectures", [])

            if not adds and not conjs:
                self._log("No discoveries or conjectures this cycle", "dim")

            for add in adds:
                sig_id = add.get("signature_id", "?")
                name = add.get("name", "?")
                try:
                    result = self.tools.execute("add_to_library", add)
                    if result.get("status") == "added":
                        score = result.get("score", "?")
                        score_str = f"{score:.3f}" if isinstance(score, float) else str(score)
                        self._log(
                            f"[bold green]+ Discovery:[/bold green] "
                            f"{name} [dim](from {sig_id}, score: {score_str})[/dim]"
                        )
                        discoveries.append(result)
                    else:
                        err = result.get("error", "unknown error")
                        self._log(f"Failed to add {name}: {err}", "red")
                except Exception as e:
                    self._log(f"Error adding {name}: {e}", "red")

            for conj in conjs:
                about = conj.get("about", "?")
                stmt = conj.get("statement", "?")
                self._log(
                    f"[bold magenta]? Conjecture:[/bold magenta] "
                    f"[{about}] {stmt}"
                )
                conjectures.append(conj)
        else:
            self._log("No decisions from Claude", "dim")

        # ── Cycle summary ────────────────────────────────────────
        duration = time.time() - self._cycle_start

        console.print()
        summary = (
            f"[bold]Cycle {cycle_num} complete[/bold]\n"
            f"  Duration: {_format_elapsed(duration)}\n"
            f"  Candidates: {candidates_generated} generated\n"
            f"  Models: {candidates_with_models} candidates had models\n"
            f"  Discoveries: {len(discoveries)} added\n"
            f"  Conjectures: {len(conjectures)} proposed"
        )
        border = "green" if discoveries else "yellow" if candidates_with_models else "dim"
        console.print(Panel(summary, border_style=border))
        console.print()

        return CycleReport(
            cycle_number=cycle_num,
            goal=self.config.goal,
            plan=plan.get("reasoning", "") if isinstance(plan, dict) else "",
            candidates_generated=candidates_generated,
            candidates_with_models=candidates_with_models,
            top_candidates=top_candidates[:10],
            conjectures=conjectures,
            discoveries=discoveries,
            duration_seconds=duration,
            agent_reasoning="\n\n---\n\n".join(reasoning_parts),
        )

    def _execute_plan_with_progress(self, plan: dict) -> dict:
        """Execute the exploration plan with live progress output."""
        all_candidates = []
        total_generated = 0
        model_results = []

        explorations = plan.get("explorations", [])
        if not explorations:
            explorations = [{
                "base_structures": self.config.base_structures,
                "depth": self.config.explore_depth,
            }]

        # ── Run explorations ─────────────────────────────────────
        for i, exp in enumerate(explorations, 1):
            bases = exp.get("base_structures", self.config.base_structures)
            moves = exp.get("moves")
            depth = exp.get("depth", self.config.explore_depth)
            move_str = ", ".join(moves) if moves else "ALL"

            self._log(
                f"Exploring [{i}/{len(explorations)}]: "
                f"{bases} x {{{move_str}}} depth={depth}"
            )

            explore_start = time.time()
            result = self.tools.execute("explore", {
                "base_structures": bases,
                "moves": moves,
                "depth": depth,
                "score_threshold": self.config.score_threshold,
            })
            explore_elapsed = time.time() - explore_start

            n_candidates = result.get("total_candidates", 0)
            n_above = result.get("above_threshold", 0)
            total_generated += n_candidates
            all_candidates.extend(result.get("candidates", []))

            self._log(
                f"  {n_candidates} candidates generated, "
                f"{n_above} above threshold "
                f"[dim]({explore_elapsed:.1f}s)[/dim]"
            )

        # Sort by score
        all_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

        if all_candidates:
            top = all_candidates[0]
            self._log(
                f"  Top candidate: {top['name'][:50]} "
                f"(score: {top.get('score', 0):.3f})"
            )

        # ── Check models ─────────────────────────────────────────
        top_n = min(plan.get("check_models_top_n", 10), len(all_candidates))
        max_size = plan.get("max_model_size", self.config.max_model_size)

        if top_n > 0:
            self._log(
                f"Checking models for top {top_n} candidates "
                f"(sizes 2-{max_size})..."
            )

            found_count = 0
            empty_count = 0

            for j, candidate in enumerate(all_candidates[:top_n], 1):
                name = candidate["name"]
                short_name = name[:45]
                check_start = time.time()

                try:
                    model_result = self.tools.execute("check_models", {
                        "signature_id": name,
                        "min_size": 2,
                        "max_size": max_size,
                        "max_models_per_size": 10,
                    })
                    check_elapsed = time.time() - check_start

                    spectrum = model_result.get("spectrum", {})
                    total_models = model_result.get("total_models", 0)
                    sizes = model_result.get("sizes_with_models", [])

                    candidate["model_spectrum"] = spectrum
                    candidate["total_models"] = total_models
                    candidate["sizes_with_models"] = sizes
                    model_results.append(model_result)

                    if total_models > 0:
                        found_count += 1
                        # Highlight interesting spectra
                        sizes_str = ",".join(str(s) for s in sorted(sizes))
                        self._log(
                            f"  [{j:2d}/{top_n}] [green]{short_name}[/green] "
                            f"sizes={{{sizes_str}}} "
                            f"models={total_models} "
                            f"[dim]({check_elapsed:.1f}s)[/dim]"
                        )
                    else:
                        empty_count += 1
                        self._log(
                            f"  [{j:2d}/{top_n}] [dim]{short_name} "
                            f"no models ({check_elapsed:.1f}s)[/dim]"
                        )

                except Exception as e:
                    self._log(
                        f"  [{j:2d}/{top_n}] [red]{short_name} error: {e}[/red]"
                    )

            self._log(
                f"Model check: [green]{found_count} with models[/green], "
                f"[dim]{empty_count} empty[/dim]"
            )

        return {
            "total_candidates": total_generated,
            "top_candidates": all_candidates[:50],
            "model_results": model_results,
        }

    def _build_plan_prompt(self, cycle_num: int) -> str:
        """Build the planning prompt for Claude."""
        context = self._build_context(cycle_num)

        return f"""{context}

Based on the context above, plan this research cycle. Think deeply about which
structures and moves will yield the most mathematically interesting results.

Output your plan as a JSON block between <plan> and </plan> tags:

<plan>
{{
  "reasoning": "Your strategic reasoning for this cycle",
  "explorations": [
    {{
      "base_structures": ["Structure1", "Structure2"],
      "moves": ["MOVE1", "MOVE2"],
      "depth": 1
    }}
  ],
  "check_models_top_n": 10,
  "max_model_size": {self.config.max_model_size}
}}
</plan>

Available moves: ABSTRACT, DUALIZE, COMPLETE, QUOTIENT, INTERNALIZE, TRANSFER, DEFORM.
You may omit "moves" to apply all moves."""

    def _build_interpret_prompt(
        self, cycle_num: int, plan_text: str, results: dict
    ) -> str:
        """Build the interpretation prompt for Claude."""
        top = results.get("top_candidates", [])[:20]
        summary_lines = []
        for c in top:
            parts = [f"  - {c['name']} (score: {c.get('score', '?')}, move: {c.get('move', '?')}"]
            spectrum = c.get("model_spectrum")
            if spectrum:
                parts.append(f", spectrum: {spectrum}")
            total_models = c.get("total_models", 0)
            if total_models:
                parts.append(f", models: {total_models}")
            parts.append(")")
            summary_lines.append("".join(parts))

        results_summary = "\n".join(summary_lines) if summary_lines else "  (none)"

        return f"""## Cycle {cycle_num} — Exploration Results

Total candidates generated: {results.get('total_candidates', 0)}

Top candidates (sorted by interestingness score):
{results_summary}

## Your Previous Plan
{plan_text[:3000]}

---

Analyze these results deeply. Consider:
1. Which candidates are most mathematically interesting and why?
2. Do any model spectra show unusual patterns (prime-only, gaps, etc.)?
3. What conjectures can you propose about the interesting structures?
4. Which discoveries should be added to the permanent library?

Output your decisions as a JSON block between <decisions> and </decisions> tags:

<decisions>
{{
  "analysis": "Your detailed mathematical analysis",
  "add_to_library": [
    {{
      "signature_id": "exact_candidate_name_from_results",
      "name": "HumanReadableName",
      "notes": "Why this is mathematically interesting"
    }}
  ],
  "conjectures": [
    {{
      "about": "candidate_name",
      "statement": "The conjecture in natural language"
    }}
  ]
}}
</decisions>

Only add structures that are genuinely novel and have interesting models.
If nothing stands out this cycle, return empty lists."""

    def _build_context(self, cycle_num: int) -> str:
        """Build the context message for the agent."""
        parts = [f"## Research Cycle {cycle_num}"]

        # Library summary
        known = self.library.list_known()
        parts.append(f"\n### Known Structures ({len(known)}):")
        for name in known[:20]:
            parts.append(f"  - {name}")

        discovered = self.library.list_discovered()
        if discovered:
            parts.append(f"\n### Previously Discovered ({len(discovered)}):")
            for d in discovered[:10]:
                parts.append(f"  - {d['name']} (score: {d.get('score', '?')})")

        # Previous cycle results
        if self.history:
            last = self.history[-1]
            parts.append(f"\n### Previous Cycle ({last.cycle_number}) Summary:")
            parts.append(f"  - Candidates generated: {last.candidates_generated}")
            parts.append(f"  - With models: {last.candidates_with_models}")
            parts.append(f"  - Discoveries: {len(last.discoveries)}")
            if last.top_candidates:
                parts.append("  - Top candidates:")
                for c in last.top_candidates[:5]:
                    parts.append(f"    * {c['name']} (score: {c.get('score', '?')})")

        # Config
        parts.append(f"\n### Suggested base structures: {', '.join(self.config.base_structures)}")
        parts.append(f"### Explore depth: {self.config.explore_depth}")
        parts.append(f"### Max model size: {self.config.max_model_size}")

        return "\n".join(parts)

    def _parse_json_block(self, text: str, tag: str) -> dict | None:
        """Extract a JSON block from between XML-style tags."""
        pattern = rf"<{tag}>\s*(.*?)\s*</{tag}>"
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            return None

        json_str = match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try fixing trailing commas
            fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                return None

    def _save_report(self, report: CycleReport) -> None:
        """Save a cycle report to disk."""
        reports_dir = self.library.base_path / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        report_path = reports_dir / f"cycle_{report.cycle_number:03d}_report.md"
        content = self._format_report_md(report)
        report_path.write_text(content)

    def _format_report_md(self, report: CycleReport) -> str:
        """Format a cycle report as Markdown."""
        lines = [
            f"# Research Cycle {report.cycle_number}",
            "",
            f"**Goal:** {report.goal}",
            f"**Duration:** {report.duration_seconds:.1f}s",
            f"**Model:** {self.config.model} (effort: {self.config.effort})",
            "",
            "## Statistics",
            f"- Candidates generated: {report.candidates_generated}",
            f"- Candidates with models: {report.candidates_with_models}",
            f"- Discoveries added: {len(report.discoveries)}",
            f"- Conjectures: {len(report.conjectures)}",
            "",
        ]

        if report.top_candidates:
            lines.append("## Top Candidates")
            lines.append("")
            for c in report.top_candidates[:10]:
                lines.append(f"### {c['name']}")
                lines.append(f"- Move: {c.get('move', '?')}")
                lines.append(f"- Parents: {c.get('parents', [])}")
                lines.append(f"- Score: {c.get('score', '?')}")
                spectrum = c.get("model_spectrum")
                if spectrum:
                    lines.append(f"- Model spectrum: {spectrum}")
                lines.append("")

        if report.discoveries:
            lines.append("## Discoveries")
            lines.append("")
            for d in report.discoveries:
                lines.append(f"- **{d.get('name', '?')}** (score: {d.get('score', '?')})")
            lines.append("")

        if report.conjectures:
            lines.append("## Conjectures")
            lines.append("")
            for c in report.conjectures:
                lines.append(f"- [{c.get('about', '?')}] {c.get('statement', '?')}")
            lines.append("")

        if report.agent_reasoning:
            lines.append("## Agent Reasoning")
            lines.append("")
            lines.append(report.agent_reasoning[:5000])
            lines.append("")

        return "\n".join(lines)
