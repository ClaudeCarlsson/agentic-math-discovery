"""The 8 structural moves for generating candidate algebraic signatures.

Each move takes one or two signatures and produces a new candidate signature.
These are the only ways the system generates new mathematics — constraining
the search to syntactically valid, structurally motivated transformations.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from src.core.signature import (
    Axiom, AxiomKind, Operation, Signature, Sort,
    make_assoc_equation, make_comm_equation, make_identity_equation,
    make_inverse_equation, make_distrib_equation, make_idempotent_equation,
    make_self_distrib_equation,
)
from src.core.ast_nodes import App, Const, Equation, Var


class MoveKind(str, Enum):
    ABSTRACT = "ABSTRACT"
    DUALIZE = "DUALIZE"
    COMPLETE = "COMPLETE"
    QUOTIENT = "QUOTIENT"
    INTERNALIZE = "INTERNALIZE"
    TRANSFER = "TRANSFER"
    DEFORM = "DEFORM"
    SELF_DISTRIB = "SELF_DISTRIB"


@dataclass
class MoveResult:
    signature: Signature
    move: MoveKind
    parents: list[str]  # names of parent signatures
    description: str


class MoveEngine:
    """Applies the 8 structural moves to generate candidate signatures."""

    def apply_all_moves(self, sigs: list[Signature]) -> list[MoveResult]:
        """Apply all applicable moves to a list of signatures. Returns candidates."""
        results: list[MoveResult] = []

        for sig in sigs:
            results.extend(self.dualize(sig))
            results.extend(self.complete(sig))
            results.extend(self.quotient(sig))
            results.extend(self.internalize(sig))
            results.extend(self.deform(sig))
            results.extend(self.self_distrib(sig))

        # Pairwise moves
        for i, sig_a in enumerate(sigs):
            for j, sig_b in enumerate(sigs):
                if i < j:
                    results.extend(self.abstract(sig_a, sig_b))
                    results.extend(self.transfer(sig_a, sig_b))

        return results

    def apply_move(self, kind: MoveKind, sigs: list[Signature]) -> list[MoveResult]:
        """Apply a specific move kind."""
        dispatch = {
            MoveKind.ABSTRACT: lambda: self._pairwise(sigs, self.abstract),
            MoveKind.DUALIZE: lambda: self._single(sigs, self.dualize),
            MoveKind.COMPLETE: lambda: self._single(sigs, self.complete),
            MoveKind.QUOTIENT: lambda: self._single(sigs, self.quotient),
            MoveKind.INTERNALIZE: lambda: self._single(sigs, self.internalize),
            MoveKind.TRANSFER: lambda: self._pairwise(sigs, self.transfer),
            MoveKind.DEFORM: lambda: self._single(sigs, self.deform),
            MoveKind.SELF_DISTRIB: lambda: self._single(sigs, self.self_distrib),
        }
        return dispatch[kind]()

    def _single(self, sigs, fn):
        results = []
        for s in sigs:
            results.extend(fn(s))
        return results

    def _pairwise(self, sigs, fn):
        results = []
        for i, a in enumerate(sigs):
            for j, b in enumerate(sigs):
                if i < j:
                    results.extend(fn(a, b))
        return results

    # --- M1: ABSTRACT ---
    def abstract(self, sig_a: Signature, sig_b: Signature) -> list[MoveResult]:
        """Extract shared structure from two signatures.

        Find axiom kinds present in both, create a new signature with
        only the shared axiom kinds applied to a minimal set of operations.
        """
        kinds_a = {a.kind for a in sig_a.axioms}
        kinds_b = {a.kind for a in sig_b.axioms}
        shared_kinds = kinds_a & kinds_b

        if not shared_kinds:
            return []

        # Build a minimal signature with shared axiom types
        new_sig = Signature(
            name=f"Abstract({sig_a.name},{sig_b.name})",
            sorts=[Sort("S", "abstract carrier")],
            operations=[Operation("op", ["S", "S"], "S", "abstract binary operation")],
            derivation_chain=sig_a.derivation_chain + [f"Abstract with {sig_b.name}"],
        )

        for kind in shared_kinds:
            eq = _axiom_for_kind(kind, "op")
            if eq:
                new_sig.axioms.append(Axiom(kind, eq, ["op"]))

        if not new_sig.axioms:
            return []

        return [MoveResult(
            signature=new_sig,
            move=MoveKind.ABSTRACT,
            parents=[sig_a.name, sig_b.name],
            description=f"Shared structure of {sig_a.name} and {sig_b.name}: "
                        f"{[k.value for k in shared_kinds]}",
        )]

    # --- M2: DUALIZE ---
    def dualize(self, sig: Signature) -> list[MoveResult]:
        """Reverse the direction: swap domain arguments of binary operations.

        For each binary operation, produce a variant where op(x,y) becomes op(y,x).
        """
        results = []
        binary_ops = sig.get_ops_by_arity(2)

        for op in binary_ops:
            new_sig = _deep_copy_sig(sig, f"{sig.name}_dual({op.name})")
            new_sig.derivation_chain.append(f"Dualize({op.name})")

            # Check if commutativity is already present
            has_comm = any(
                a.kind == AxiomKind.COMMUTATIVITY and op.name in a.operations
                for a in new_sig.axioms
            )
            if has_comm:
                continue  # Dualizing a commutative op is identity

            # Add commutativity as the dualization
            new_sig.axioms.append(
                Axiom(
                    AxiomKind.COMMUTATIVITY,
                    make_comm_equation(op.name),
                    [op.name],
                    f"dualization of {op.name}",
                )
            )

            results.append(MoveResult(
                signature=new_sig,
                move=MoveKind.DUALIZE,
                parents=[sig.name],
                description=f"Dualize {op.name} in {sig.name} (add commutativity)",
            ))

        return results

    # --- M3: COMPLETE ---
    def complete(self, sig: Signature) -> list[MoveResult]:
        """Add missing structure: identity elements, inverses, second operations, norms."""
        results = []

        binary_ops = sig.get_ops_by_arity(2)

        for op in binary_ops:
            sort = op.codomain

            # Complete with identity
            has_identity = any(
                a.kind == AxiomKind.IDENTITY and op.name in a.operations
                for a in sig.axioms
            )
            if not has_identity:
                new_sig = _deep_copy_sig(sig, f"{sig.name}+id({op.name})")
                new_sig.derivation_chain.append(f"Complete(identity for {op.name})")
                id_name = f"e_{op.name}"
                new_sig.operations.append(Operation(id_name, [], sort, f"identity for {op.name}"))
                new_sig.axioms.append(
                    Axiom(AxiomKind.IDENTITY, make_identity_equation(op.name, id_name),
                          [op.name, id_name])
                )
                results.append(MoveResult(
                    signature=new_sig,
                    move=MoveKind.COMPLETE,
                    parents=[sig.name],
                    description=f"Add identity element for {op.name}",
                ))

            # Complete with inverse (requires identity)
            has_inverse = any(
                a.kind == AxiomKind.INVERSE and op.name in a.operations
                for a in sig.axioms
            )
            if has_identity and not has_inverse:
                new_sig = _deep_copy_sig(sig, f"{sig.name}+inv({op.name})")
                new_sig.derivation_chain.append(f"Complete(inverse for {op.name})")
                inv_name = f"inv_{op.name}"
                # Find the identity constant name
                id_const = None
                for ax in sig.axioms:
                    if ax.kind == AxiomKind.IDENTITY and op.name in ax.operations:
                        for o in ax.operations:
                            if o != op.name:
                                id_const = o
                                break
                if id_const:
                    new_sig.operations.append(
                        Operation(inv_name, [sort], sort, f"inverse for {op.name}")
                    )
                    new_sig.axioms.append(
                        Axiom(AxiomKind.INVERSE,
                              make_inverse_equation(op.name, inv_name, id_const),
                              [op.name, inv_name, id_const])
                    )
                    results.append(MoveResult(
                        signature=new_sig,
                        move=MoveKind.COMPLETE,
                        parents=[sig.name],
                        description=f"Add inverse for {op.name}",
                    ))

        # Complete with a second binary operation + distributivity
        if len(binary_ops) == 1:
            op = binary_ops[0]
            sort = op.codomain
            new_sig = _deep_copy_sig(sig, f"{sig.name}+op2")
            new_sig.derivation_chain.append("Complete(second operation)")
            new_sig.operations.append(
                Operation("op2", [sort, sort], sort, "second binary operation")
            )
            new_sig.axioms.append(
                Axiom(AxiomKind.DISTRIBUTIVITY, make_distrib_equation("op2", op.name),
                      ["op2", op.name], "op2 distributes over original op")
            )
            results.append(MoveResult(
                signature=new_sig,
                move=MoveKind.COMPLETE,
                parents=[sig.name],
                description=f"Add second operation distributing over {op.name}",
            ))

        # Complete with norm (if multi-sorted or has inner product potential)
        if len(sig.sorts) >= 2 or any(op.arity == 2 for op in sig.operations):
            sort = sig.sorts[0].name
            scalar_sort = sig.sorts[1].name if len(sig.sorts) >= 2 else sort
            if not sig.get_op("norm"):
                new_sig = _deep_copy_sig(sig, f"{sig.name}+norm")
                new_sig.derivation_chain.append("Complete(norm)")
                new_sig.operations.append(
                    Operation("norm", [sort], scalar_sort, "norm function")
                )
                x = Var("x")
                new_sig.axioms.append(
                    Axiom(AxiomKind.POSITIVITY,
                          Equation(App("norm", [x]), App("norm", [x])),
                          ["norm"], "norm(x) ≥ 0 (positivity)")
                )
                results.append(MoveResult(
                    signature=new_sig,
                    move=MoveKind.COMPLETE,
                    parents=[sig.name],
                    description=f"Add norm to {sig.name}",
                ))

        return results

    # --- M4: QUOTIENT ---
    def quotient(self, sig: Signature) -> list[MoveResult]:
        """Force additional equations: commutativity, idempotence, nilpotence."""
        results = []
        binary_ops = sig.get_ops_by_arity(2)

        quotient_axioms = [
            (AxiomKind.COMMUTATIVITY, "COMM", make_comm_equation),
            (AxiomKind.IDEMPOTENCE, "IDEM", make_idempotent_equation),
        ]

        for op in binary_ops:
            for kind, label, eq_fn in quotient_axioms:
                already = any(a.kind == kind and op.name in a.operations for a in sig.axioms)
                if not already:
                    new_sig = _deep_copy_sig(sig, f"{sig.name}_q({label},{op.name})")
                    new_sig.derivation_chain.append(f"Quotient({label} on {op.name})")
                    new_sig.axioms.append(Axiom(kind, eq_fn(op.name), [op.name]))
                    results.append(MoveResult(
                        signature=new_sig,
                        move=MoveKind.QUOTIENT,
                        parents=[sig.name],
                        description=f"Quotient {sig.name} by {label} on {op.name}",
                    ))

        return results

    # --- M5: INTERNALIZE ---
    def internalize(self, sig: Signature) -> list[MoveResult]:
        """Turn a binary operation into a first-class sort (Hom-objects).

        For a binary op f: S×S→S, create a new sort Hom with a single
        element for each "partial application" of f.
        """
        results = []
        binary_ops = sig.get_ops_by_arity(2)

        for op in binary_ops:
            new_sig = _deep_copy_sig(sig, f"{sig.name}_int({op.name})")
            new_sig.derivation_chain.append(f"Internalize({op.name})")
            sort = op.codomain

            # Add a new sort for the hom-object
            hom_sort = f"Hom_{op.name}"
            new_sig.sorts.append(Sort(hom_sort, f"internalized {op.name}"))

            # Add evaluation map: eval: Hom × S → S
            new_sig.operations.append(
                Operation(f"eval_{op.name}", [hom_sort, sort], sort,
                          f"evaluate internalized {op.name}")
            )

            # Add curry map: curry: S → Hom
            new_sig.operations.append(
                Operation(f"curry_{op.name}", [sort], hom_sort,
                          f"curry {op.name} to Hom")
            )

            # Axiom: eval(curry(a), b) = op(a, b)
            a, b = Var("a"), Var("b")
            new_sig.axioms.append(
                Axiom(
                    AxiomKind.CUSTOM,
                    Equation(
                        App(f"eval_{op.name}", [App(f"curry_{op.name}", [a]), b]),
                        App(op.name, [a, b]),
                    ),
                    [f"eval_{op.name}", f"curry_{op.name}", op.name],
                    "curry-eval adjunction",
                )
            )

            results.append(MoveResult(
                signature=new_sig,
                move=MoveKind.INTERNALIZE,
                parents=[sig.name],
                description=f"Internalize {op.name} as Hom-object in {sig.name}",
            ))

        return results

    # --- M6: TRANSFER ---
    def transfer(self, sig_a: Signature, sig_b: Signature) -> list[MoveResult]:
        """Map structure from one domain to another via a transfer morphism.

        Creates a combined signature with both structures plus a function
        between their carrier sorts and a functoriality axiom.
        """
        results = []

        sort_a = sig_a.sorts[0].name
        sort_b = sig_b.sorts[0].name

        # Disambiguate sort names if they clash
        if sort_a == sort_b:
            sort_b = f"{sort_b}_2"

        new_sig = Signature(
            name=f"Transfer({sig_a.name},{sig_b.name})",
            sorts=[Sort(sort_a, f"from {sig_a.name}"),
                   Sort(sort_b, f"from {sig_b.name}")],
            operations=[],
            axioms=[],
            derivation_chain=sig_a.derivation_chain + [f"Transfer to {sig_b.name}"],
        )

        # Copy operations from both, prefixing to avoid collisions
        for op in sig_a.operations:
            new_sig.operations.append(Operation(
                f"a_{op.name}", [sort_a if s == sig_a.sorts[0].name else s for s in op.domain],
                sort_a if op.codomain == sig_a.sorts[0].name else op.codomain,
                f"{op.name} from {sig_a.name}",
            ))

        for op in sig_b.operations:
            new_sig.operations.append(Operation(
                f"b_{op.name}", [sort_b if s == sig_b.sorts[0].name else s for s in op.domain],
                sort_b if op.codomain == sig_b.sorts[0].name else op.codomain,
                f"{op.name} from {sig_b.name}",
            ))

        # Copy axioms (with prefixed op names)
        for ax in sig_a.axioms:
            new_sig.axioms.append(Axiom(
                ax.kind, ax.equation, [f"a_{o}" for o in ax.operations], ax.description,
            ))
        for ax in sig_b.axioms:
            new_sig.axioms.append(Axiom(
                ax.kind, ax.equation, [f"b_{o}" for o in ax.operations], ax.description,
            ))

        # Add the transfer morphism
        new_sig.operations.append(
            Operation("transfer", [sort_a], sort_b, f"morphism from {sort_a} to {sort_b}")
        )

        # Functoriality: for the first binary op of each, require transfer to be a homomorphism
        bin_a = sig_a.get_ops_by_arity(2)
        bin_b = sig_b.get_ops_by_arity(2)
        if bin_a and bin_b:
            op_a = bin_a[0]
            op_b = bin_b[0]
            x, y = Var("x"), Var("y")
            # transfer(a_op(x,y)) = b_op(transfer(x), transfer(y))
            new_sig.axioms.append(
                Axiom(
                    AxiomKind.FUNCTORIALITY,
                    Equation(
                        App("transfer", [App(f"a_{op_a.name}", [x, y])]),
                        App(f"b_{op_b.name}", [App("transfer", [x]), App("transfer", [y])]),
                    ),
                    ["transfer", f"a_{op_a.name}", f"b_{op_b.name}"],
                    "transfer is a homomorphism",
                )
            )

        results.append(MoveResult(
            signature=new_sig,
            move=MoveKind.TRANSFER,
            parents=[sig_a.name, sig_b.name],
            description=f"Transfer structure from {sig_a.name} to {sig_b.name}",
        ))

        return results

    # --- M7: DEFORM ---
    def deform(self, sig: Signature) -> list[MoveResult]:
        """Introduce a parameter that relaxes an axiom.

        For each axiom, create a variant where the axiom is weakened
        by a deformation parameter.
        """
        results = []

        for i, axiom in enumerate(sig.axioms):
            if axiom.kind in (AxiomKind.CUSTOM, AxiomKind.POSITIVITY):
                continue  # Skip custom/positivity — hard to deform generically

            new_sig = _deep_copy_sig(sig, f"{sig.name}_deform({axiom.kind.value})")
            new_sig.derivation_chain.append(f"Deform({axiom.kind.value})")

            # Add parameter sort and constant
            if not any(s.name == "Param" for s in new_sig.sorts):
                new_sig.sorts.append(Sort("Param", "deformation parameter"))

            param = Const("q")

            # Remove the original axiom
            new_sig.axioms = [a for j, a in enumerate(new_sig.axioms) if j != i]

            # Add a weakened version based on the axiom kind
            if axiom.kind == AxiomKind.ASSOCIATIVITY:
                # q-associativity: (x*y)*z = q * (x*(y*z))
                op_name = axiom.operations[0] if axiom.operations else "op"
                sort = sig.sorts[0].name
                x, y, z = Var("x"), Var("y"), Var("z")
                # We need a scalar multiplication for the deformation
                deform_op = f"q_{op_name}"
                new_sig.operations.append(
                    Operation(deform_op, ["Param", sort], sort, "deformation scaling")
                )
                lhs = App(op_name, [App(op_name, [x, y]), z])
                rhs = App(deform_op, [param, App(op_name, [x, App(op_name, [y, z])])])
                new_sig.axioms.append(
                    Axiom(AxiomKind.CUSTOM, Equation(lhs, rhs),
                          [op_name, deform_op], f"q-deformed {axiom.kind.value}")
                )
            elif axiom.kind == AxiomKind.COMMUTATIVITY:
                # q-commutativity: x*y = q * (y*x)
                op_name = axiom.operations[0] if axiom.operations else "op"
                sort = sig.sorts[0].name
                x, y = Var("x"), Var("y")
                deform_op = f"q_{op_name}"
                if not new_sig.get_op(deform_op):
                    new_sig.operations.append(
                        Operation(deform_op, ["Param", sort], sort, "deformation scaling")
                    )
                lhs = App(op_name, [x, y])
                rhs = App(deform_op, [param, App(op_name, [y, x])])
                new_sig.axioms.append(
                    Axiom(AxiomKind.CUSTOM, Equation(lhs, rhs),
                          [op_name, deform_op], f"q-deformed {axiom.kind.value}")
                )
            else:
                # Generic deformation: just mark the axiom as deformed without equation
                new_sig.axioms.append(
                    Axiom(AxiomKind.CUSTOM, axiom.equation, axiom.operations,
                          f"deformed-{axiom.kind.value}")
                )

            results.append(MoveResult(
                signature=new_sig,
                move=MoveKind.DEFORM,
                parents=[sig.name],
                description=f"Deform {axiom.kind.value} in {sig.name}",
            ))

        return results


    # --- M8: SELF_DISTRIB ---
    def self_distrib(self, sig: Signature) -> list[MoveResult]:
        """Add left self-distributivity to a binary operation.

        Left self-distributivity: a*(b*c) = (a*b)*(a*c).
        This axiom arises in rack and quandle theory (knot theory).
        """
        results = []
        for op in sig.get_ops_by_arity(2):
            already = any(
                a.kind == AxiomKind.SELF_DISTRIBUTIVITY and op.name in a.operations
                for a in sig.axioms
            )
            if not already:
                new_sig = _deep_copy_sig(sig, f"{sig.name}_sd({op.name})")
                new_sig.derivation_chain.append(f"SelfDistrib({op.name})")
                new_sig.axioms.append(
                    Axiom(
                        AxiomKind.SELF_DISTRIBUTIVITY,
                        make_self_distrib_equation(op.name),
                        [op.name],
                    )
                )
                results.append(MoveResult(
                    signature=new_sig,
                    move=MoveKind.SELF_DISTRIB,
                    parents=[sig.name],
                    description=f"Add self-distributivity to {op.name} in {sig.name}",
                ))
        return results


def _deep_copy_sig(sig: Signature, new_name: str) -> Signature:
    """Deep copy a signature with a new name."""
    return Signature(
        name=new_name,
        sorts=list(sig.sorts),
        operations=list(sig.operations),
        axioms=list(sig.axioms),
        description=sig.description,
        derivation_chain=list(sig.derivation_chain),
        metadata=dict(sig.metadata),
    )


def _axiom_for_kind(kind: AxiomKind, op_name: str) -> Equation | None:
    """Generate a standard equation for a given axiom kind."""
    dispatch = {
        AxiomKind.ASSOCIATIVITY: make_assoc_equation,
        AxiomKind.COMMUTATIVITY: make_comm_equation,
        AxiomKind.IDEMPOTENCE: make_idempotent_equation,
        AxiomKind.SELF_DISTRIBUTIVITY: make_self_distrib_equation,
    }
    fn = dispatch.get(kind)
    return fn(op_name) if fn else None
