"""Z3-based finite model finder.

Uses Z3's SMT solver to search for finite models of algebraic signatures.
This serves as either the primary model finder or a fallback when Mace4
is not installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np

from src.core.signature import Axiom, AxiomKind, Signature
from src.core.ast_nodes import App, Const, Equation, Expr, Var
from src.models.cayley import CayleyTable
from src.solvers.mace4 import Mace4Result, ModelSpectrum

try:
    import z3
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False


class Z3ModelFinder:
    """Find finite models of algebraic signatures using Z3."""

    def __init__(self, timeout_ms: int = 30000):
        self.timeout_ms = timeout_ms

    def is_available(self) -> bool:
        return Z3_AVAILABLE

    def find_models(
        self,
        sig: Signature,
        domain_size: int,
        max_models: int = 10,
    ) -> Mace4Result:
        """Search for finite models using Z3.

        We encode the structure as integer arithmetic over [0, domain_size).
        Operations become uninterpreted functions. Axioms become universal
        quantifiers over the domain.
        """
        if not Z3_AVAILABLE:
            return Mace4Result(
                domain_size=domain_size,
                models_found=[],
                exit_code=-1,
                raw_output="",
                error="z3-solver not installed",
            )

        solver = z3.Solver()
        solver.set("timeout", self.timeout_ms)
        n = domain_size

        # Create integer constants for the domain elements
        domain = list(range(n))

        # Create function symbols
        # For binary ops: n*n lookup table as integer variables
        op_tables: dict[str, list[list[z3.ArithRef]]] = {}
        const_vars: dict[str, z3.ArithRef] = {}
        unary_tables: dict[str, list[z3.ArithRef]] = {}

        for op in sig.operations:
            if op.arity == 0:
                v = z3.Int(f"{op.name}")
                solver.add(v >= 0, v < n)
                const_vars[op.name] = v
            elif op.arity == 1:
                table = [z3.Int(f"{op.name}_{i}") for i in range(n)]
                for v in table:
                    solver.add(v >= 0, v < n)
                unary_tables[op.name] = table
            elif op.arity == 2:
                table = [[z3.Int(f"{op.name}_{i}_{j}") for j in range(n)] for i in range(n)]
                for row in table:
                    for v in row:
                        solver.add(v >= 0, v < n)
                op_tables[op.name] = table

        # Encode axioms as constraints
        for axiom in sig.axioms:
            self._encode_axiom(solver, axiom, n, op_tables, const_vars, unary_tables)

        # Find models
        models: list[CayleyTable] = []
        timed_out = False
        for _ in range(max_models):
            result = solver.check()
            if result == z3.unknown:
                timed_out = True
                break
            if result != z3.sat:
                break

            model = solver.model()
            tables = {}
            constants = {}

            for op_name, table in op_tables.items():
                arr = np.zeros((n, n), dtype=int)
                for i in range(n):
                    for j in range(n):
                        val = model.evaluate(table[i][j], model_completion=True)
                        arr[i][j] = val.as_long()
                tables[op_name] = arr

            for name, var in const_vars.items():
                val = model.evaluate(var, model_completion=True)
                constants[name] = val.as_long()

            for name, table in unary_tables.items():
                arr = np.array([
                    model.evaluate(table[i], model_completion=True).as_long()
                    for i in range(n)
                ])
                tables[f"_unary_{name}"] = arr

            ct = CayleyTable(size=n, tables=tables, constants=constants)
            models.append(ct)

            # Block this model to find the next one
            block = []
            for op_name, table in op_tables.items():
                for i in range(n):
                    for j in range(n):
                        val = model.evaluate(table[i][j], model_completion=True)
                        block.append(table[i][j] != val.as_long())
            for name, var in const_vars.items():
                val = model.evaluate(var, model_completion=True)
                block.append(var != val.as_long())
            for name, table in unary_tables.items():
                for i in range(n):
                    val = model.evaluate(table[i], model_completion=True)
                    block.append(table[i] != val.as_long())

            if block:
                solver.add(z3.Or(block))

        return Mace4Result(
            domain_size=domain_size,
            models_found=models,
            exit_code=0 if models else 1,
            raw_output=f"Z3 found {len(models)} model(s)",
            timed_out=timed_out,
        )

    def compute_spectrum(
        self,
        sig: Signature,
        min_size: int = 2,
        max_size: int = 8,
        max_models_per_size: int = 10,
    ) -> ModelSpectrum:
        spectrum = ModelSpectrum(signature_name=sig.name)
        for size in range(min_size, max_size + 1):
            result = self.find_models(sig, size, max_models_per_size)
            spectrum.spectrum[size] = len(result.models_found)
            spectrum.models_by_size[size] = result.models_found
            if result.timed_out:
                spectrum.timed_out_sizes.append(size)
        return spectrum

    def _encode_axiom(
        self,
        solver: z3.Solver,
        axiom: Axiom,
        n: int,
        op_tables: dict[str, list[list[z3.ArithRef]]],
        const_vars: dict[str, z3.ArithRef],
        unary_tables: dict[str, list[z3.ArithRef]],
    ) -> None:
        """Encode an axiom as Z3 constraints.

        For universally quantified equations, we instantiate over all
        domain elements (complete instantiation for finite domains).
        """
        eq = axiom.equation
        var_names = sorted(eq.variables())

        if not var_names:
            # Ground equation
            lhs_val = self._eval_expr(eq.lhs, {}, op_tables, const_vars, unary_tables)
            rhs_val = self._eval_expr(eq.rhs, {}, op_tables, const_vars, unary_tables)
            if lhs_val is not None and rhs_val is not None:
                solver.add(lhs_val == rhs_val)
            return

        # Enumerate all assignments of domain elements to variables
        for assignment in product(range(n), repeat=len(var_names)):
            env = dict(zip(var_names, assignment))
            lhs_val = self._eval_expr(eq.lhs, env, op_tables, const_vars, unary_tables)
            rhs_val = self._eval_expr(eq.rhs, env, op_tables, const_vars, unary_tables)
            if lhs_val is not None and rhs_val is not None:
                solver.add(lhs_val == rhs_val)

    def _eval_expr(
        self,
        expr: Expr,
        env: dict[str, int],
        op_tables: dict[str, list[list[z3.ArithRef]]],
        const_vars: dict[str, z3.ArithRef],
        unary_tables: dict[str, list[z3.ArithRef]],
    ) -> z3.ArithRef | int | None:
        """Evaluate an expression under a given variable assignment.

        For concrete variable values, we can index directly into the operation
        tables, producing Z3 expressions that represent the result.
        """
        if isinstance(expr, Var):
            return env.get(expr.name)

        if isinstance(expr, Const):
            return const_vars.get(expr.name)

        if isinstance(expr, App):
            args = []
            for a in expr.args:
                val = self._eval_expr(a, env, op_tables, const_vars, unary_tables)
                if val is None:
                    return None
                args.append(val)

            if len(args) == 0:
                return const_vars.get(expr.op_name)

            if len(args) == 1:
                table = unary_tables.get(expr.op_name)
                if table is None:
                    return None
                arg = args[0]
                if isinstance(arg, int):
                    return table[arg]
                # For Z3 expression arguments, we need If-Then-Else chains
                return self._z3_lookup_1d(table, arg, len(table))

            if len(args) == 2:
                table = op_tables.get(expr.op_name)
                if table is None:
                    return None
                a, b = args
                if isinstance(a, int) and isinstance(b, int):
                    return table[a][b]
                # Need If-Then-Else for non-concrete indices
                return self._z3_lookup_2d(table, a, b, len(table))

        return None

    def _z3_lookup_1d(
        self, table: list[z3.ArithRef], idx: z3.ArithRef | int, n: int
    ) -> z3.ArithRef:
        """Build a Z3 If-Then-Else chain for 1D table lookup."""
        if isinstance(idx, int):
            return table[idx]
        result = table[n - 1]
        for i in range(n - 2, -1, -1):
            result = z3.If(idx == i, table[i], result)
        return result

    def _z3_lookup_2d(
        self,
        table: list[list[z3.ArithRef]],
        row: z3.ArithRef | int,
        col: z3.ArithRef | int,
        n: int,
    ) -> z3.ArithRef:
        """Build a Z3 If-Then-Else chain for 2D table lookup."""
        if isinstance(row, int) and isinstance(col, int):
            return table[row][col]

        if isinstance(row, int):
            return self._z3_lookup_1d(table[row], col, n)

        # Build row-level ITE
        row_results = []
        for i in range(n):
            row_val = self._z3_lookup_1d(table[i], col, n)
            row_results.append(row_val)

        result = row_results[n - 1]
        for i in range(n - 2, -1, -1):
            result = z3.If(row == i, row_results[i], result)
        return result
