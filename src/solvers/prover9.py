"""Prover9 integration: automated theorem proving for equational theories.

Prover9 proves theorems in first-order logic. We use it to verify conjectures
about algebraic structures — e.g., "does this axiom set imply commutativity?"
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum

from src.core.signature import Signature
from src.core.ast_nodes import Equation
from src.solvers.fol_translator import FOLTranslator


class ProofStatus(str, Enum):
    PROVED = "proved"
    DISPROVED = "disproved"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ProofResult:
    status: ProofStatus
    conjecture: str
    proof_text: str = ""
    counterexample: str = ""
    time_seconds: float = 0.0
    raw_output: str = ""


class Prover9Solver:
    """Interface to Prover9 automated theorem prover."""

    def __init__(self, prover9_path: str = "prover9", timeout: int = 30):
        self.prover9_path = prover9_path
        self.timeout = timeout
        self.translator = FOLTranslator()

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                [self.prover9_path, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode in (0, 1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def prove(self, sig: Signature, conjecture: Equation) -> ProofResult:
        """Attempt to prove that the axioms of `sig` imply `conjecture`."""
        input_text = self.translator.to_prover9(sig, conjecture)
        conj_str = repr(conjecture)

        try:
            result = subprocess.run(
                [self.prover9_path, f"-t{self.timeout}"],
                input=input_text,
                capture_output=True,
                text=True,
                timeout=self.timeout + 5,
            )

            if result.returncode == 0 and "THEOREM PROVED" in result.stdout:
                return ProofResult(
                    status=ProofStatus.PROVED,
                    conjecture=conj_str,
                    proof_text=self._extract_proof(result.stdout),
                    raw_output=result.stdout,
                )
            elif "SEARCH FAILED" in result.stdout:
                return ProofResult(
                    status=ProofStatus.DISPROVED,
                    conjecture=conj_str,
                    raw_output=result.stdout,
                )
            else:
                return ProofResult(
                    status=ProofStatus.TIMEOUT,
                    conjecture=conj_str,
                    raw_output=result.stdout,
                )

        except subprocess.TimeoutExpired:
            return ProofResult(
                status=ProofStatus.TIMEOUT,
                conjecture=conj_str,
            )
        except FileNotFoundError:
            return ProofResult(
                status=ProofStatus.ERROR,
                conjecture=conj_str,
                raw_output=f"Prover9 not found at {self.prover9_path}",
            )

    def _extract_proof(self, output: str) -> str:
        """Extract the proof portion from Prover9 output."""
        lines = output.split("\n")
        proof_lines = []
        in_proof = False
        for line in lines:
            if "PROOF" in line:
                in_proof = True
            if in_proof:
                proof_lines.append(line)
            if in_proof and "end of proof" in line.lower():
                break
        return "\n".join(proof_lines)


class ConjectureGenerator:
    """Generate testable conjectures about algebraic signatures.

    Uses templates to produce conjectures that Prover9 can attempt to verify.
    """

    def generate_conjectures(self, sig: Signature) -> list[Equation]:
        """Generate a list of conjectures about the given signature."""
        from src.core.ast_nodes import App, Var

        conjectures = []
        x, y, z = Var("x"), Var("y"), Var("z")

        for op in sig.operations:
            if op.arity != 2:
                continue

            # Conjecture: commutativity
            has_comm = any(
                a.kind.value == "COMMUTATIVITY" and op.name in a.operations
                for a in sig.axioms
            )
            if not has_comm:
                conjectures.append(Equation(
                    App(op.name, [x, y]),
                    App(op.name, [y, x]),
                ))

            # Conjecture: idempotence
            has_idem = any(
                a.kind.value == "IDEMPOTENCE" and op.name in a.operations
                for a in sig.axioms
            )
            if not has_idem:
                conjectures.append(Equation(
                    App(op.name, [x, x]),
                    x,
                ))

            # Conjecture: associativity
            has_assoc = any(
                a.kind.value == "ASSOCIATIVITY" and op.name in a.operations
                for a in sig.axioms
            )
            if not has_assoc:
                conjectures.append(Equation(
                    App(op.name, [App(op.name, [x, y]), z]),
                    App(op.name, [x, App(op.name, [y, z])]),
                ))

        return conjectures
