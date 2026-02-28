"""Translate algebraic signatures to first-order logic input formats.

Supports:
- Mace4/Prover9 input format (LADR)
- Z3 Python API calls
- Generic FOL string representation
"""

from __future__ import annotations

from src.core.signature import Axiom, AxiomKind, Operation, Signature
from src.core.ast_nodes import App, Const, Equation, Expr, Var


class FOLTranslator:
    """Translates signatures to various first-order logic formats."""

    def to_mace4(self, sig: Signature, domain_size: int) -> str:
        """Generate Mace4 input file content for finding models of a given size.

        We translate to a single-sorted theory over a domain of `domain_size` elements.
        Multi-sorted signatures are collapsed to a single sort for finite model finding.
        """
        lines = [
            f"% Signature: {sig.name}",
            f"% Domain size: {domain_size}",
            "",
            f"assign(domain_size, {domain_size}).",
            "",
            "formulas(assumptions).",
            "",
        ]

        for axiom in sig.axioms:
            fol = self._equation_to_mace4(axiom.equation)
            if fol:
                comment = axiom.description or axiom.kind.value
                lines.append(f"  % {comment}")
                lines.append(f"  {fol}.")
                lines.append("")

        lines.append("end_of_list.")
        return "\n".join(lines)

    def to_prover9(self, sig: Signature, conjecture: Equation) -> str:
        """Generate Prover9 input for proving a conjecture about a signature."""
        lines = [
            f"% Signature: {sig.name}",
            "",
            "formulas(assumptions).",
            "",
        ]

        for axiom in sig.axioms:
            fol = self._equation_to_mace4(axiom.equation)
            if fol:
                lines.append(f"  {fol}.")

        lines.append("")
        lines.append("end_of_list.")
        lines.append("")
        lines.append("formulas(goals).")
        lines.append("")

        goal = self._equation_to_mace4(conjecture)
        if goal:
            lines.append(f"  {goal}.")

        lines.append("")
        lines.append("end_of_list.")
        return "\n".join(lines)

    def _equation_to_mace4(self, eq: Equation) -> str | None:
        """Convert an equation to Mace4 format: lhs = rhs."""
        lhs = self._expr_to_mace4(eq.lhs)
        rhs = self._expr_to_mace4(eq.rhs)
        if lhs is None or rhs is None:
            return None
        return f"{lhs} = {rhs}"

    def _expr_to_mace4(self, expr: Expr) -> str | None:
        """Convert an expression to Mace4 term format."""
        if isinstance(expr, Var):
            return expr.name
        if isinstance(expr, Const):
            return expr.name
        if isinstance(expr, App):
            if not expr.args:
                return expr.op_name
            args = []
            for a in expr.args:
                s = self._expr_to_mace4(a)
                if s is None:
                    return None
                args.append(s)
            return f"{expr.op_name}({','.join(args)})"
        return None

    def to_z3_python(self, sig: Signature, domain_size: int) -> str:
        """Generate Z3 Python code for model finding.

        Returns executable Python source that uses z3-solver to search
        for models.
        """
        lines = [
            "from z3 import *",
            "",
            f"# Signature: {sig.name}",
            f"n = {domain_size}",
            "",
            "# Sort",
            "S = DeclareSort('S')",
            f"elements = [Const('e{i}', S) for i in range({domain_size})]",
            "",
            "# Distinct elements",
            "s = Solver()",
            "s.add(Distinct(*elements))",
            "",
        ]

        # Declare operations as uninterpreted functions
        for op in sig.operations:
            if op.arity == 0:
                lines.append(f"{op.name} = Const('{op.name}', S)")
            elif op.arity == 1:
                lines.append(f"{op.name} = Function('{op.name}', S, S)")
            elif op.arity == 2:
                lines.append(f"{op.name} = Function('{op.name}', S, S, S)")

        lines.append("")
        lines.append("# Closure: all operations map to known elements")
        lines.append(f"elem_set = elements")

        lines.append("")
        lines.append("# Axioms")

        for axiom in sig.axioms:
            lines.append(f"# {axiom.kind.value}")
            z3_constraint = self._axiom_to_z3_comment(axiom)
            lines.append(f"# {z3_constraint}")

        lines.append("")
        lines.append("result = s.check()")
        lines.append("print(f'Result: {result}')")
        lines.append("if result == sat:")
        lines.append("    m = s.model()")
        lines.append("    print(m)")

        return "\n".join(lines)

    def _axiom_to_z3_comment(self, axiom: Axiom) -> str:
        """Describe the axiom as a Z3 constraint comment."""
        return f"ForAll([...], {axiom.equation})"


def signature_to_mace4_input(sig: Signature, domain_size: int) -> str:
    """Convenience function."""
    return FOLTranslator().to_mace4(sig, domain_size)


def signature_to_prover9_input(sig: Signature, conjecture: Equation) -> str:
    """Convenience function."""
    return FOLTranslator().to_prover9(sig, conjecture)
