"""Tool definitions for the LLM agent.

These are the functions the agent can call to interact with the
mathematical discovery system. Each tool is a structured interface
that the agent invokes via function calling.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.core.signature import Signature
from src.library.known_structures import load_all_known, load_by_name
from src.library.manager import LibraryManager
from src.moves.engine import MoveEngine, MoveKind, MoveResult
from src.scoring.engine import ScoreBreakdown, ScoringEngine
from src.solvers.mace4 import Mace4Result, Mace4Solver, Mace4Fallback, ModelSpectrum
from src.solvers.prover9 import ConjectureGenerator, ProofResult, Prover9Solver
from src.solvers.z3_solver import Z3ModelFinder
from src.core.ast_nodes import Equation


# JSON schema definitions for the agent's tool interface
TOOL_SCHEMAS = [
    {
        "name": "explore",
        "description": (
            "Apply structural moves to generate candidate algebraic structures. "
            "Moves: ABSTRACT, DUALIZE, COMPLETE, QUOTIENT, INTERNALIZE, TRANSFER, DEFORM."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "base_structures": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Names of structures from library to start from",
                },
                "moves": {
                    "type": "array",
                    "items": {"type": "string", "enum": [k.value for k in MoveKind]},
                    "description": "Which moves to apply (or omit for all)",
                },
                "depth": {
                    "type": "integer",
                    "description": "Search depth (1-3)",
                    "minimum": 1,
                    "maximum": 3,
                },
                "score_threshold": {
                    "type": "number",
                    "description": "Only return candidates above this score",
                },
            },
            "required": ["base_structures"],
        },
    },
    {
        "name": "check_models",
        "description": (
            "Search for finite models of a candidate signature using SAT/SMT solvers. "
            "Returns model spectrum and example Cayley tables."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "signature_id": {
                    "type": "string",
                    "description": "Name/ID of the candidate signature",
                },
                "min_size": {"type": "integer", "default": 2},
                "max_size": {"type": "integer", "default": 8},
                "max_models_per_size": {"type": "integer", "default": 10},
            },
            "required": ["signature_id"],
        },
    },
    {
        "name": "prove",
        "description": "Attempt to prove or disprove a conjecture about a signature.",
        "input_schema": {
            "type": "object",
            "properties": {
                "signature_id": {"type": "string"},
                "conjecture": {"type": "string", "description": "The equation to prove"},
                "timeout_sec": {"type": "integer", "default": 30},
            },
            "required": ["signature_id", "conjecture"],
        },
    },
    {
        "name": "score",
        "description": "Compute interestingness scores for a candidate signature.",
        "input_schema": {
            "type": "object",
            "properties": {
                "signature_id": {"type": "string"},
            },
            "required": ["signature_id"],
        },
    },
    {
        "name": "search_library",
        "description": "Search known and discovered structures by properties.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "min_score": {"type": "number"},
                "has_models": {"type": "boolean"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "add_to_library",
        "description": "Add a verified discovery to the permanent library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "signature_id": {"type": "string"},
                "name": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["signature_id", "name"],
        },
    },
]


class ToolExecutor:
    """Executes tool calls from the agent."""

    def __init__(self, library: LibraryManager):
        self.library = library
        self.move_engine = MoveEngine()
        self.scorer = ScoringEngine()

        # Try Mace4 first, fall back to Z3
        self.mace4 = Mace4Solver()
        if not self.mace4.is_available():
            self.model_finder = Mace4Fallback()
        else:
            self.model_finder = self.mace4

        self.prover9 = Prover9Solver()
        self.conjecture_gen = ConjectureGenerator()

        # In-memory cache of candidates from current session
        self._candidates: dict[str, Signature] = {}
        self._spectra: dict[str, ModelSpectrum] = {}

    def execute(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call and return the result."""
        dispatch = {
            "explore": self._explore,
            "check_models": self._check_models,
            "prove": self._prove,
            "score": self._score,
            "search_library": self._search_library,
            "add_to_library": self._add_to_library,
        }

        handler = dispatch.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return handler(args)
        except Exception as e:
            return {"error": str(e)}

    def _explore(self, args: dict[str, Any]) -> dict[str, Any]:
        base_names = args.get("base_structures", [])
        move_names = args.get("moves")
        depth = args.get("depth", 1)
        threshold = args.get("score_threshold", 0.0)

        # Load base structures
        bases = []
        for name in base_names:
            sig = self._candidates.get(name) or load_by_name(name)
            if sig:
                bases.append(sig)

        if not bases:
            return {"error": "No valid base structures found", "candidates": []}

        # Apply moves iteratively for depth > 1
        current = bases
        all_results: list[MoveResult] = []

        for d in range(depth):
            if move_names:
                results = []
                for mk in move_names:
                    kind = MoveKind(mk)
                    results.extend(self.move_engine.apply_move(kind, current))
            else:
                results = self.move_engine.apply_all_moves(current)

            all_results.extend(results)
            current = [r.signature for r in results]

        # Score and filter
        known_fps = set(self.library.all_fingerprints())
        scored = []
        for r in all_results:
            score = self.scorer.score(r.signature, known_fingerprints=known_fps)
            if score.total >= threshold:
                self._candidates[r.signature.name] = r.signature
                scored.append({
                    "name": r.signature.name,
                    "move": r.move.value,
                    "parents": r.parents,
                    "description": r.description,
                    "score": round(score.total, 4),
                    "sorts": len(r.signature.sorts),
                    "operations": len(r.signature.operations),
                    "axioms": len(r.signature.axioms),
                })

        scored.sort(key=lambda x: x["score"], reverse=True)

        return {
            "total_candidates": len(all_results),
            "above_threshold": len(scored),
            "candidates": scored[:50],  # Top 50
        }

    def _check_models(self, args: dict[str, Any]) -> dict[str, Any]:
        sig_id = args["signature_id"]
        min_size = args.get("min_size", 2)
        max_size = args.get("max_size", 8)
        max_models = args.get("max_models_per_size", 10)

        sig = self._candidates.get(sig_id) or load_by_name(sig_id)
        if not sig:
            return {"error": f"Signature '{sig_id}' not found"}

        spectrum = self.model_finder.compute_spectrum(sig, min_size, max_size, max_models)
        self._spectra[sig_id] = spectrum

        return {
            "signature": sig_id,
            "spectrum": spectrum.spectrum,
            "sizes_with_models": spectrum.sizes_with_models(),
            "total_models": spectrum.total_models(),
            "example_models": {
                str(size): [m.to_dict() for m in models[:2]]
                for size, models in spectrum.models_by_size.items()
                if models
            },
        }

    def _prove(self, args: dict[str, Any]) -> dict[str, Any]:
        sig_id = args["signature_id"]
        sig = self._candidates.get(sig_id) or load_by_name(sig_id)
        if not sig:
            return {"error": f"Signature '{sig_id}' not found"}

        if not self.prover9.is_available():
            return {"error": "Prover9 not available. Install from https://www.cs.unm.edu/~mccune/prover9/"}

        # Generate and attempt conjectures
        conjectures = self.conjecture_gen.generate_conjectures(sig)
        results = []
        for conj in conjectures:
            result = self.prover9.prove(sig, conj)
            results.append({
                "conjecture": str(conj),
                "status": result.status.value,
                "proof": result.proof_text[:500] if result.proof_text else "",
            })

        return {"signature": sig_id, "results": results}

    def _score(self, args: dict[str, Any]) -> dict[str, Any]:
        sig_id = args["signature_id"]
        sig = self._candidates.get(sig_id) or load_by_name(sig_id)
        if not sig:
            return {"error": f"Signature '{sig_id}' not found"}

        spectrum = self._spectra.get(sig_id)
        known_fps = set(self.library.all_fingerprints())
        breakdown = self.scorer.score(sig, spectrum, known_fps)

        return {
            "signature": sig_id,
            "scores": breakdown.to_dict(),
        }

    def _search_library(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query", "")
        min_score = args.get("min_score")
        has_models = args.get("has_models")

        results = self.library.search(query, min_score=min_score)
        return {
            "results": [
                {"name": r["name"], "score": r.get("score", 0), "description": r.get("description", "")}
                for r in results
            ]
        }

    def _add_to_library(self, args: dict[str, Any]) -> dict[str, Any]:
        sig_id = args["signature_id"]
        name = args["name"]
        notes = args.get("notes", "")

        sig = self._candidates.get(sig_id)
        if not sig:
            return {"error": f"Candidate '{sig_id}' not found in current session"}

        # Require model verification before saving
        spectrum = self._spectra.get(sig_id)
        if spectrum is None:
            return {
                "error": f"No model check results for '{sig_id}'. "
                "Call check_models first before adding to library."
            }
        if spectrum.total_models() == 0:
            return {
                "error": f"'{sig_id}' has no finite models. "
                "Only structures with verified models can be added."
            }

        known_fps = set(self.library.all_fingerprints())
        score = self.scorer.score(sig, spectrum, known_fps)

        self.library.add_discovery(sig, name, notes, score)

        return {"status": "added", "name": name, "score": score.total}
