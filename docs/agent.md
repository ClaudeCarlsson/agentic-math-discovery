# Agent Controller

The LLM agent is the strategic layer that drives mathematical discovery. It plans research directions, interprets results, proposes conjectures, and steers the search toward genuinely novel structures.

## Overview

The agent operates in **research cycles**. Each cycle is one complete iteration of the discovery loop:

```
ASSESS → PLAN → EXECUTE → INTERPRET → CONJECTURE → VERIFY → UPDATE → REPORT
```

The agent does NOT do heavy mathematical computation — that's the job of the structure engine, model checker, and proof engine. The agent is the **strategist and storyteller**: it decides what to explore, recognizes patterns in results, and communicates findings.

---

## Agent Configuration

```python
@dataclass
class AgentConfig:
    model: str = "claude-sonnet-4-6"       # LLM model to use
    api_key: str = ""                      # Anthropic API key (or env var)
    max_cycles: int = 10                   # Maximum research cycles
    goal: str = "Explore broadly"          # Natural language research goal
    explore_depth: int = 2                 # Move depth per cycle
    max_model_size: int = 6                # Z3/Mace4 domain size limit
    score_threshold: float = 0.3           # Minimum score to consider
    base_structures: list[str] = [         # Starting structures
        "Group", "Ring", "Lattice", "Quasigroup"
    ]
```

### CLI Usage

```bash
# Broad exploration
python3 run.py agent --cycles 5 --goal "explore broadly"

# Targeted search
python3 run.py agent --cycles 10 \
  --goal "find structures with positivity that constrain spectra" \
  --base InnerProductSpace --base LieAlgebra

# Using a specific model
python3 run.py agent --model claude-opus-4-6 --cycles 3
```

---

## The 6 Tools

The agent interacts with the system exclusively through 6 tools, defined as JSON schemas for function calling:

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

### 1. ASSESS

The controller builds a context message containing:
- List of all known structures (14 seed + any discovered)
- Summary of the previous cycle (candidates generated, models found, discoveries)
- Top candidates from the last run
- Current research goal
- Suggested base structures and exploration depth

### 2. PLAN

The LLM reads the context and decides:
- Which base structures to focus on this cycle
- Which moves to apply (all 7, or a targeted subset)
- Whether to explore broadly (many structures, shallow depth) or deeply (few structures, deep moves)
- Whether to follow up on promising candidates from the last cycle

### 3. EXECUTE

The agent calls tools in a multi-turn loop:

```
Turn 1: Agent calls explore() with chosen parameters
Turn 2: Agent reviews candidates, calls check_models() on top ones
Turn 3: Agent calls score() on candidates with interesting models
Turn 4: Agent calls prove() to test conjectures
Turn 5: Agent calls add_to_library() for discoveries
...
```

The loop runs for up to 20 turns per cycle.

### 4. INTERPRET

Between tool calls, the agent produces text blocks analyzing results:
- "This structure has models only at prime sizes — investigating further"
- "The Transfer of LieAlgebra to Ring produced a high-scoring candidate with positivity"
- "Model checking timed out at size 7 — this suggests computational complexity"

### 5. CONJECTURE

The agent proposes testable statements:
- "Every model of this structure has a commutative sub-operation"
- "No model exists at composite sizes"
- "The number of models at size p follows floor(p/2) - 1"

These are tested via `check_models()` (exhaustive for small sizes) or `prove()` (Prover9).

### 6. VERIFY

Conjectures are checked and classified:
- **Verified**: Holds for all tested sizes
- **Disproved**: Counterexample found
- **Open**: Neither proved nor disproved within timeout

### 7. UPDATE

Interesting discoveries are persisted via `add_to_library()`. The library manager writes JSON files to `library/discovered/` with full metadata.

### 8. REPORT

The controller generates a Markdown report saved to `library/reports/cycle_NNN_report.md` containing:
- Statistics (candidates generated, models found, discoveries)
- Top candidates with scores
- Agent reasoning excerpts
- Any discoveries added to the library

---

## System Prompt

The agent receives a system prompt that defines its role:

```
You are a mathematical research agent specializing in automated theory
formation in universal algebra. Your goal is to discover structurally
novel, non-trivial mathematical concepts...
```

The prompt:
- Describes each tool and its purpose
- Outlines the research process (explore → check → score → conjecture → add)
- Defines what makes a structure "interesting"
- Includes the current research goal (configurable per run)

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

Reports are saved as Markdown in `library/reports/`. View them via:

```bash
python3 run.py report --cycle latest
python3 run.py report --cycle 3
python3 run.py report --top 20 --sort-by score
```

### Example Report

```markdown
# Research Cycle 7

**Goal:** Find structures with positivity that constrain spectra
**Duration:** 45.2s

## Statistics
- Candidates generated: 847
- Candidates with models: 23
- Discoveries added: 2

## Top Candidates
### Transfer(LieAlg_op+norm → Ring_q(ASSOC))
- Move: TRANSFER
- Score: 0.873
- Model spectrum: {3: 1, 5: 2, 7: 3, 11: 5}
- Only prime sizes! Flagged for investigation.

## Discoveries
- **NormedLieBridge** (score: 0.873)
- **PositiveSemifield** (score: 0.812)
```

---

## Model Requirements

The agent needs an LLM that supports:
- **Tool use / function calling** — all modern Claude and GPT models support this
- **Structured JSON output** — for tool arguments
- **Multi-turn conversation** — the tool-use loop requires multiple exchanges
- **Basic mathematical knowledge** — for interpreting model spectra and recognizing known structures

Recommended: `claude-sonnet-4-6` for cost-effective cycles, `claude-opus-4-6` for deeper mathematical reasoning.

---

## Programmatic Usage

```python
from src.agent.controller import AgentConfig, AgentController
from src.library.manager import LibraryManager

library = LibraryManager("library")
config = AgentConfig(
    model="claude-sonnet-4-6",
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
