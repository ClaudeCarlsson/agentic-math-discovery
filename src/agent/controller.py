"""Agent Controller: the LLM-driven research loop.

The agent operates in cycles, each consisting of:
1. ASSESS - Review current state
2. PLAN - Decide what to explore
3. EXECUTE - Run tools
4. INTERPRET - Analyze results
5. CONJECTURE - Propose testable conjectures
6. VERIFY - Test conjectures
7. UPDATE - Add discoveries to library
8. REPORT - Generate human-readable summary
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.agent.tools import TOOL_SCHEMAS, ToolExecutor
from src.library.manager import LibraryManager


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

    model: str = "claude-sonnet-4-6"
    api_key: str = ""
    max_cycles: int = 10
    goal: str = "Explore broadly: find novel algebraic structures"
    explore_depth: int = 2
    max_model_size: int = 6
    score_threshold: float = 0.3
    base_structures: list[str] = field(default_factory=lambda: [
        "Group", "Ring", "Lattice", "Quasigroup",
    ])


SYSTEM_PROMPT = """\
You are a mathematical research agent specializing in automated theory formation \
in universal algebra. Your goal is to discover structurally novel, non-trivial \
mathematical concepts by exploring the space of algebraic signatures.

You have access to the following tools:

1. **explore** - Apply structural moves (ABSTRACT, DUALIZE, COMPLETE, QUOTIENT, \
INTERNALIZE, TRANSFER, DEFORM) to generate candidate algebraic structures from \
known ones.

2. **check_models** - Search for finite models of a candidate signature using \
SAT/SMT solvers (Mace4 or Z3). Returns the model spectrum and example Cayley tables.

3. **prove** - Attempt to prove conjectures about a signature using Prover9.

4. **score** - Compute interestingness scores for a candidate.

5. **search_library** - Search known and discovered structures.

6. **add_to_library** - Add a verified discovery to the permanent library.

## Your Research Process

Each cycle, you should:
1. Review what you know and what was found in previous cycles
2. Choose which structures to focus on and which moves to apply
3. Generate candidates using `explore`
4. Check the top candidates for finite models using `check_models`
5. Score the most promising ones using `score`
6. Generate conjectures about the interesting structures
7. If a structure is genuinely novel and interesting, add it to the library

## What Makes a Structure Interesting

- It has non-trivial finite models (not just the 1-element model)
- Its model spectrum shows a pattern (e.g., only at prime sizes, only powers of 2)
- It combines axiom types that don't usually appear together
- It bridges two mathematical domains (e.g., order theory + group theory)
- It has a simple description but rich model theory

## Current Research Goal

{goal}
"""


class AgentController:
    """Orchestrates the LLM-driven mathematical discovery loop."""

    def __init__(self, config: AgentConfig, library: LibraryManager):
        self.config = config
        self.library = library
        self.tools = ToolExecutor(library)
        self.history: list[CycleReport] = []
        self._client = None

    def _get_client(self):
        """Lazily initialize the LLM client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.config.api_key or None)
        return self._client

    def run(self, num_cycles: int | None = None) -> list[CycleReport]:
        """Run the agent for the specified number of cycles."""
        cycles = num_cycles or self.config.max_cycles
        reports = []

        for i in range(cycles):
            report = self._run_cycle(i + 1)
            reports.append(report)
            self.history.append(report)

            # Save report to disk
            self._save_report(report)

        return reports

    def _run_cycle(self, cycle_num: int) -> CycleReport:
        """Execute one complete research cycle."""
        start = time.time()

        system = SYSTEM_PROMPT.format(goal=self.config.goal)

        # Build the user message with context
        context = self._build_context(cycle_num)

        messages = [{"role": "user", "content": context}]

        # Run the agent loop with tool use
        candidates_generated = 0
        candidates_with_models = 0
        top_candidates = []
        conjectures = []
        discoveries = []
        reasoning_parts = []

        client = self._get_client()

        # Multi-turn tool-use loop
        for turn in range(20):  # Max 20 turns per cycle
            response = client.messages.create(
                model=self.config.model,
                max_tokens=4096,
                system=system,
                messages=messages,
                tools=self._format_tools(),
            )

            # Process the response
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            # Check for tool use
            tool_uses = [b for b in assistant_content if b.type == "tool_use"]
            text_blocks = [b for b in assistant_content if b.type == "text"]

            for tb in text_blocks:
                reasoning_parts.append(tb.text)

            if not tool_uses:
                break  # Agent is done with this cycle

            # Execute tools
            tool_results = []
            for tu in tool_uses:
                result = self.tools.execute(tu.name, tu.input)

                # Track statistics
                if tu.name == "explore":
                    candidates_generated += result.get("total_candidates", 0)
                    top_candidates.extend(result.get("candidates", [])[:5])
                elif tu.name == "check_models":
                    if result.get("total_models", 0) > 0:
                        candidates_with_models += 1
                elif tu.name == "add_to_library":
                    if result.get("status") == "added":
                        discoveries.append(result)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})

            if response.stop_reason == "end_turn":
                break

        duration = time.time() - start

        return CycleReport(
            cycle_number=cycle_num,
            goal=self.config.goal,
            plan=reasoning_parts[0] if reasoning_parts else "",
            candidates_generated=candidates_generated,
            candidates_with_models=candidates_with_models,
            top_candidates=top_candidates[:10],
            conjectures=conjectures,
            discoveries=discoveries,
            duration_seconds=duration,
            agent_reasoning="\n\n".join(reasoning_parts),
        )

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
            parts.append(f"\n### Discovered Structures ({len(discovered)}):")
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
                for c in last.top_candidates[:3]:
                    parts.append(f"    * {c['name']} (score: {c.get('score', '?')})")

        # Suggested base structures
        parts.append(f"\n### Suggested base structures: {', '.join(self.config.base_structures)}")
        parts.append(f"### Explore depth: {self.config.explore_depth}")
        parts.append(f"### Max model size: {self.config.max_model_size}")

        parts.append("\n\nPlease execute this research cycle. Use tools to explore, "
                      "check models, score candidates, and add any interesting discoveries.")

        return "\n".join(parts)

    def _format_tools(self) -> list[dict]:
        """Format tool schemas for the Anthropic API."""
        return [
            {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
            for t in TOOL_SCHEMAS
        ]

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
            f"",
            f"**Goal:** {report.goal}",
            f"**Duration:** {report.duration_seconds:.1f}s",
            f"",
            f"## Statistics",
            f"- Candidates generated: {report.candidates_generated}",
            f"- Candidates with models: {report.candidates_with_models}",
            f"- Discoveries added: {len(report.discoveries)}",
            f"",
        ]

        if report.top_candidates:
            lines.append("## Top Candidates")
            lines.append("")
            for c in report.top_candidates:
                lines.append(f"### {c['name']}")
                lines.append(f"- Move: {c.get('move', '?')}")
                lines.append(f"- Parents: {c.get('parents', [])}")
                lines.append(f"- Score: {c.get('score', '?')}")
                lines.append(f"- Description: {c.get('description', '')}")
                lines.append("")

        if report.discoveries:
            lines.append("## Discoveries")
            lines.append("")
            for d in report.discoveries:
                lines.append(f"- **{d.get('name', '?')}** (score: {d.get('score', '?')})")
            lines.append("")

        if report.agent_reasoning:
            lines.append("## Agent Reasoning")
            lines.append("")
            lines.append(report.agent_reasoning[:2000])
            lines.append("")

        return "\n".join(lines)
