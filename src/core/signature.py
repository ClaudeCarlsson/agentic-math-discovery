"""Core algebraic signature representation.

A signature defines an algebraic structure: sorts (types), operations
(functions between sorts), and axioms (equational laws the operations satisfy).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.ast_nodes import App, Const, Equation, Expr, Var, parse_equation


class AxiomKind(str, Enum):
    """Standard axiom kinds in universal algebra."""

    ASSOCIATIVITY = "ASSOCIATIVITY"
    COMMUTATIVITY = "COMMUTATIVITY"
    IDENTITY = "IDENTITY"
    INVERSE = "INVERSE"
    DISTRIBUTIVITY = "DISTRIBUTIVITY"
    ANTICOMMUTATIVITY = "ANTICOMMUTATIVITY"
    IDEMPOTENCE = "IDEMPOTENCE"
    NILPOTENCE = "NILPOTENCE"
    JACOBI = "JACOBI"
    POSITIVITY = "POSITIVITY"
    BILINEARITY = "BILINEARITY"
    HOMOMORPHISM = "HOMOMORPHISM"
    FUNCTORIALITY = "FUNCTORIALITY"
    ABSORPTION = "ABSORPTION"
    MODULARITY = "MODULARITY"
    SELF_DISTRIBUTIVITY = "SELF_DISTRIBUTIVITY"
    RIGHT_SELF_DISTRIBUTIVITY = "RIGHT_SELF_DISTRIBUTIVITY"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class Sort:
    """A sort (type) in the algebraic signature."""

    name: str
    description: str = ""


@dataclass(frozen=True)
class Operation:
    """An operation in the algebraic signature.

    domain: list of input sort names
    codomain: output sort name
    """

    name: str
    domain: tuple[str, ...]
    codomain: str
    description: str = ""

    @property
    def arity(self) -> int:
        return len(self.domain)

    def __init__(self, name: str, domain: list[str] | tuple[str, ...],
                 codomain: str, description: str = ""):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "domain", tuple(domain))
        object.__setattr__(self, "codomain", codomain)
        object.__setattr__(self, "description", description)


@dataclass(frozen=True)
class Axiom:
    """An axiom (equational law) in the signature."""

    kind: AxiomKind
    equation: Equation
    operations: tuple[str, ...]  # which operations this axiom constrains
    description: str = ""

    def __init__(self, kind: AxiomKind, equation: Equation,
                 operations: list[str] | tuple[str, ...], description: str = ""):
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "equation", equation)
        object.__setattr__(self, "operations", tuple(operations))
        object.__setattr__(self, "description", description)


@dataclass
class Signature:
    """A complete algebraic signature: sorts + operations + axioms."""

    name: str
    sorts: list[Sort] = field(default_factory=list)
    operations: list[Operation] = field(default_factory=list)
    axioms: list[Axiom] = field(default_factory=list)
    description: str = ""
    derivation_chain: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def sort_names(self) -> list[str]:
        return [s.name for s in self.sorts]

    def op_names(self) -> list[str]:
        return [op.name for op in self.operations]

    def get_op(self, name: str) -> Operation | None:
        for op in self.operations:
            if op.name == name:
                return op
        return None

    def get_ops_by_arity(self, arity: int) -> list[Operation]:
        return [op for op in self.operations if op.arity == arity]

    def fingerprint(self) -> str:
        """Compute a canonical fingerprint for novelty checking.

        Two signatures with the same fingerprint are structurally isomorphic
        (same sorts, arities, axiom kinds, up to renaming).
        """
        sort_count = len(self.sorts)
        op_arities = sorted(op.arity for op in self.operations)
        axiom_kinds = sorted(a.kind.value for a in self.axioms)
        canon = {
            "sorts": sort_count,
            "op_arities": op_arities,
            "axiom_kinds": axiom_kinds,
        }
        blob = json.dumps(canon, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sorts": [{"name": s.name, "description": s.description} for s in self.sorts],
            "operations": [
                {
                    "name": op.name,
                    "domain": list(op.domain),
                    "codomain": op.codomain,
                    "description": op.description,
                }
                for op in self.operations
            ],
            "axioms": [
                {
                    "kind": a.kind.value,
                    "equation": repr(a.equation),
                    "operations": list(a.operations),
                    "description": a.description,
                }
                for a in self.axioms
            ],
            "description": self.description,
            "derivation_chain": self.derivation_chain,
            "fingerprint": self.fingerprint(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Signature:
        """Reconstruct a Signature from its to_dict() representation.

        Parses serialized equation strings back into AST objects.
        """
        sorts = [Sort(s["name"], s.get("description", "")) for s in data.get("sorts", [])]

        operations = [
            Operation(
                op["name"],
                op["domain"],
                op["codomain"],
                op.get("description", ""),
            )
            for op in data.get("operations", [])
        ]

        # Identify constants (0-arity ops) and all op names for the parser
        constants = {op.name for op in operations if op.arity == 0}
        op_names = {op.name for op in operations}

        axioms = []
        for ax_data in data.get("axioms", []):
            kind = AxiomKind(ax_data["kind"])
            equation = parse_equation(ax_data["equation"], constants, op_names)
            ops = ax_data.get("operations", [])
            description = ax_data.get("description", "")
            axioms.append(Axiom(kind, equation, ops, description))

        return cls(
            name=data.get("name", ""),
            sorts=sorts,
            operations=operations,
            axioms=axioms,
            description=data.get("description", ""),
            derivation_chain=data.get("derivation_chain", []),
        )

    def __repr__(self) -> str:
        sorts = ", ".join(s.name for s in self.sorts)
        ops = ", ".join(f"{op.name}/{op.arity}" for op in self.operations)
        return f"Sig({self.name}: sorts=[{sorts}], ops=[{ops}], axioms={len(self.axioms)})"


# --- Builders for common axiom equations ---

def make_assoc_equation(op_name: str) -> Equation:
    x, y, z = Var("x"), Var("y"), Var("z")
    lhs = App(op_name, [App(op_name, [x, y]), z])
    rhs = App(op_name, [x, App(op_name, [y, z])])
    return Equation(lhs, rhs)


def make_comm_equation(op_name: str) -> Equation:
    x, y = Var("x"), Var("y")
    lhs = App(op_name, [x, y])
    rhs = App(op_name, [y, x])
    return Equation(lhs, rhs)


def make_identity_equation(op_name: str, id_name: str) -> Equation:
    x = Var("x")
    lhs = App(op_name, [x, Const(id_name)])
    rhs = x
    return Equation(lhs, rhs)


def make_inverse_equation(op_name: str, inv_name: str, id_name: str) -> Equation:
    x = Var("x")
    lhs = App(op_name, [x, App(inv_name, [x])])
    rhs = Const(id_name)
    return Equation(lhs, rhs)


def make_idempotent_equation(op_name: str) -> Equation:
    x = Var("x")
    lhs = App(op_name, [x, x])
    rhs = x
    return Equation(lhs, rhs)


def make_anticomm_equation(op_name: str) -> Equation:
    """x*y = -(y*x). Requires a negation/inverse operation exists."""
    x, y = Var("x"), Var("y")
    lhs = App(op_name, [x, y])
    rhs = App("neg", [App(op_name, [y, x])])
    return Equation(lhs, rhs)


def make_distrib_equation(mul_name: str, add_name: str) -> Equation:
    """Left distributivity: a*(b+c) = a*b + a*c."""
    a, b, c = Var("a"), Var("b"), Var("c")
    lhs = App(mul_name, [a, App(add_name, [b, c])])
    rhs = App(add_name, [App(mul_name, [a, b]), App(mul_name, [a, c])])
    return Equation(lhs, rhs)


def make_self_distrib_equation(op_name: str) -> Equation:
    """Left self-distributivity: a*(b*c) = (a*b)*(a*c)."""
    a, b, c = Var("a"), Var("b"), Var("c")
    lhs = App(op_name, [a, App(op_name, [b, c])])
    rhs = App(op_name, [App(op_name, [a, b]), App(op_name, [a, c])])
    return Equation(lhs, rhs)


def make_right_self_distrib_equation(op_name: str) -> Equation:
    """Right self-distributivity: (a*b)*c = (a*c)*(b*c)."""
    a, b, c = Var("a"), Var("b"), Var("c")
    lhs = App(op_name, [App(op_name, [a, b]), c])
    rhs = App(op_name, [App(op_name, [a, c]), App(op_name, [b, c])])
    return Equation(lhs, rhs)


def make_jacobi_equation(bracket_name: str) -> Equation:
    """Jacobi identity: [x,[y,z]] + [y,[z,x]] + [z,[x,y]] = 0.

    We represent this as: [x,[y,z]] + [y,[z,x]] = -[z,[x,y]] using neg/add.
    """
    x, y, z = Var("x"), Var("y"), Var("z")
    t1 = App(bracket_name, [x, App(bracket_name, [y, z])])
    t2 = App(bracket_name, [y, App(bracket_name, [z, x])])
    t3 = App(bracket_name, [z, App(bracket_name, [x, y])])
    lhs = App("add", [t1, t2])
    rhs = App("neg", [t3])
    return Equation(lhs, rhs)
