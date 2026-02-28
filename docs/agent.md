# Agent Controller

The LLM agent is the strategic layer that drives mathematical discovery. It plans research directions, interprets results, proposes conjectures, and steers the search toward genuinely novel structures.

The agent uses the **Claude Code CLI** (`claude --print`) as a subprocess — no Python SDK or API key management required. Just install the CLI and authenticate once.

## Overview

The agent operates in **research cycles**. Each cycle has four phases:

```
PLAN → EXECUTE → INTERPRET → ACT
```

- **PLAN**: Claude designs the exploration strategy (which structures, moves, depth)
- **EXECUTE**: Tools run locally — generate candidates, check models via Z3/Mace4
- **INTERPRET**: Claude analyzes results and proposes conjectures
- **ACT**: Interesting discoveries are added to the persistent library

The agent does NOT do heavy mathematical computation — that's the job of the structure engine, model checker, and proof engine. The agent is the **strategist and storyteller**.

---

## Live Observability

Every phase prints real-time progress so you always know what's happening:

```
────────────────────────── Cycle 1/3 ──────────────────────────
[    0s] Goal: Find novel loop variants

[    0s] PLAN
[    0s] Asking Claude to design exploration strategy...
[   43s] Claude planning done (43s, 55 lines)
[   43s] Strategy: Loops occupy a rich intermediate space between
         quasigroups and groups...
[   43s]   Explore ['Loop'] with [COMPLETE, DEFORM] at depth 2
[   43s]   Explore ['Loop', 'Lattice'] with [TRANSFER] at depth 1

[   43s] EXECUTE
[   43s] Exploring [1/7]: ['Loop'] x {COMPLETE, DEFORM} depth=2
[   43s]   30 candidates generated, 30 above threshold (0.0s)
[   43s] Checking models for top 10 candidates (sizes 2-6)...
[   44s]   [ 1/10] Quasigroup_dual(mul)_deform(COMM) sizes={2,3,4,5,6} models=50 (0.6s)
[   48s]   [ 7/10] Loop_q(IDEM,mul)_int(mul) no models (0.2s)
[   49s] Model check: 7 with models, 3 empty

[   49s] INTERPRET
[   49s] Asking Claude to analyze results...
[ 2m09s] Claude analyzing done (1m20s, 82 lines)
[ 2m09s] Analysis: Of 289 candidates, three distinct behavioral classes...

[ 2m09s] ACT
[ 2m09s] + Discovery: EvenLoop (from Loop_q(COMM,ldiv)_int(mul), score: 0.842)
[ 2m09s] ? Conjecture: [EvenLoop] has models iff domain size is even

╭──────────────────────────────────────╮
│ Cycle 1 complete                     │
│   Duration: 2m09s                    │
│   Candidates: 289 generated          │
│   Models: 7 candidates had models    │
│   Discoveries: 1 added              │
│   Conjectures: 4 proposed           │
╰──────────────────────────────────────╯
```

Features:
- **Timestamped log lines** — elapsed time since cycle start on every line
- **Animated spinners** — live timer during Claude CLI calls (the longest waits)
- **Per-candidate model checking** — see each candidate's status as it's checked
- **Inline reasoning summaries** — Claude's strategy and analysis shown immediately
- **Phase headers** — clear PLAN/EXECUTE/INTERPRET/ACT transitions
- **Cycle summary panel** — duration, candidate counts, discoveries, conjectures

---

## Agent Configuration

```python
@dataclass
class AgentConfig:
    model: str = "claude-opus-4-6"      # Claude model to use
    effort: str = "high"                # Thinking effort: low, medium, high
    max_cycles: int = 10                # Maximum research cycles
    goal: str = "Explore broadly"       # Natural language research goal
    explore_depth: int = 2              # Move depth per cycle
    max_model_size: int = 6             # Z3/Mace4 domain size limit
    score_threshold: float = 0.3        # Minimum score to consider
    base_structures: list[str] = [      # Starting structures
        "Group", "Ring", "Lattice", "Quasigroup"
    ]
```

### CLI Usage

```bash
# Broad exploration (default: Opus 4.6, high effort thinking)
python3 run.py agent --cycles 5 --goal "explore broadly"

# Targeted search
python3 run.py agent --cycles 10 \
  --goal "find structures with positivity that constrain spectra" \
  --base InnerProductSpace --base LieAlgebra

# Use a different model or effort level
python3 run.py agent --model sonnet --effort medium --cycles 3
```

### Prerequisites

Install the Claude Code CLI:

```bash
npm install -g @anthropic-ai/claude-code
claude auth          # Authenticate once
```

---

## The 6 Tools

The agent's Python-side tool executor provides 6 tools. These are called locally — Claude never executes them directly. Instead, Claude outputs a structured plan, and the controller executes the tools on its behalf.

### 1. `explore`

Generate candidate algebraic structures by applying structural moves.

```json
{
  "base_structures": ["Group", "Ring"],
  "moves": ["COMPLETE", "TRANSFER"],
  "depth": 2,
  "score_threshold": 0.3
}
```

**Returns**: List of scored candidates with name, move, parents, score, and structural stats.

### 2. `check_models`

Search for finite models of a candidate using Z3/Mace4.

```json
{
  "signature_id": "Group_int(mul)",
  "min_size": 2,
  "max_size": 8,
  "max_models_per_size": 10
}
```

**Returns**: Model spectrum (size → count), sizes with models, total count, and example Cayley tables.

### 3. `prove`

Attempt to prove or disprove automatically generated conjectures about a signature.

```json
{
  "signature_id": "Group_int(mul)",
  "conjecture": "commutativity of mul",
  "timeout_sec": 30
}
```

**Returns**: List of conjecture results with status (proved/disproved/timeout).

### 4. `score`

Compute the full 10-dimensional interestingness score.

```json
{
  "signature_id": "Group_int(mul)"
}
```

**Returns**: All 10 score dimensions plus the weighted total.

### 5. `search_library`

Search known and discovered structures by name or properties.

```json
{
  "query": "positivity",
  "min_score": 0.5
}
```

**Returns**: Matching structures with names, types, scores, and descriptions.

### 6. `add_to_library`

Persist a verified discovery for future cycles.

```json
{
  "signature_id": "Transfer(LieAlgebra,Ring)_q(COMM)",
  "name": "NormedLieBridge",
  "notes": "Novel structure combining Lie bracket with deformed ring multiplication"
}
```

**Returns**: Confirmation with the assigned score.

---

## The Research Cycle in Detail

### Phase 1: PLAN

The controller sends Claude a prompt containing:
- List of all known structures (14 seed + any discovered)
- Summary of the previous cycle (candidates generated, models found, discoveries)
- Top candidates from the last run
- Current research goal
- Suggested base structures and exploration depth

Claude responds with a structured JSON plan specifying which structures to explore, which moves to apply, search depth, and how many candidates to model-check.

### Phase 2: EXECUTE

The controller executes Claude's plan locally:

1. Run each exploration (structure × moves × depth) via the `explore` tool
2. Sort all candidates by interestingness score
3. Check models for the top N candidates using Z3/Mace4
4. Attach model spectrum data to each candidate

Progress is printed live — each exploration step, each model check with results.

### Phase 3: INTERPRET

The controller sends Claude the execution results:
- Total candidates generated
- Top 20 candidates with scores and model spectra
- Claude's original plan for context

Claude responds with:
- Detailed mathematical analysis of the results
- Which discoveries should be added to the library
- Conjectures about interesting structures

### Phase 4: ACT

The controller executes Claude's decisions:
- Add discoveries to the persistent library via `add_to_library`
- Log conjectures for future investigation
- Save a Markdown cycle report to `library/reports/`

---

## How Claude Is Called

The agent calls the Claude CLI as a subprocess:

```python
cmd = [
    "claude", "--print",
    "--model", "claude-opus-4-6",
    "--effort", "high",
    "--output-format", "text",
    "--tools", "",                    # Disable CLI tools — we only want text
    "--no-session-persistence",
    "--system-prompt", system_prompt,
]

result = subprocess.run(cmd, input=user_prompt, capture_output=True, text=True)
```

Key details:
- `--tools ""` disables all built-in Claude Code tools (Read, Edit, Bash, etc.) — Claude acts purely as a planner/analyst
- `--effort high` enables maximum thinking depth for complex mathematical reasoning
- `--no-session-persistence` prevents cluttering the Claude session history
- The `CLAUDECODE` environment variable is unset to allow spawning from within an existing Claude Code session
- Claude outputs structured JSON between `<plan>...</plan>` or `<decisions>...</decisions>` tags, which the controller parses

Two Claude calls per cycle: one for planning, one for interpretation. Each call takes 30-90 seconds with Opus at high effort.

---

## Agent Behaviors

### Pattern Recognition

The agent is expected to notice patterns across candidates:
- "Candidates #42, #87, and #103 all have model spectrums with only prime sizes"
- "All high-scoring Transfer results involve InnerProductSpace"

### Strategic Exploration

The agent balances exploration vs. exploitation:
- **Explore**: Try new combinations, different base structures, diverse moves
- **Exploit**: Deepen investigation of promising finds (more model sizes, prove conjectures)

### Failure Analysis

When conjectures fail or model checking produces unexpected results:
- Analyze the counterexample
- Extract interesting sub-structures
- Adjust the search direction

### Research Goal Decomposition

Complex goals are broken into sub-goals:
```
Goal: "Find structures relevant to number theory"
  → G1: Find structures with models only at prime sizes
  → G2: Among those, find ones with positivity
  → G3: Check if any have Frobenius-like automorphisms
```

---

## Cycle Reports

Reports are saved as Markdown in `library/reports/` with persistent numbering.
Each new report is numbered from the highest existing report number + 1, so
running the agent multiple times never overwrites earlier reports. View them via:

```bash
python3 run.py report --cycle latest
python3 run.py report --cycle 3
python3 run.py report --top 20 --sort-by score
```

### Example Report

```markdown
# Research Cycle 7

**Goal:** Find structures with positivity that constrain spectra
**Duration:** 129.3s
**Model:** claude-opus-4-6 (effort: high)

## Statistics
- Candidates generated: 847
- Candidates with models: 23
- Discoveries added: 2
- Conjectures: 4

## Top Candidates
### Transfer(LieAlg_op+norm → Ring_q(ASSOC))
- Move: TRANSFER
- Score: 0.873
- Model spectrum: {3: 1, 5: 2, 7: 3, 11: 5}
- Only prime sizes! Flagged for investigation.

## Discoveries
- **NormedLieBridge** (score: 0.873)
- **PositiveSemifield** (score: 0.812)

## Conjectures
- [NormedLieBridge] Models exist only at prime sizes
- [PositiveSemifield] The number of models at size p follows floor(p/2) - 1
```

---

## Programmatic Usage

```python
from src.agent.controller import AgentConfig, AgentController
from src.library.manager import LibraryManager

library = LibraryManager("library")
config = AgentConfig(
    model="claude-opus-4-6",
    effort="high",
    max_cycles=10,
    goal="find novel quasigroup variants",
    base_structures=["Quasigroup", "Loop"],
)

controller = AgentController(config, library)
reports = controller.run(num_cycles=5)

for report in reports:
    print(f"Cycle {report.cycle_number}: "
          f"{report.candidates_generated} candidates, "
          f"{len(report.discoveries)} discoveries")
```
