"""Tests for core data structures: AST nodes and signatures."""

import pytest
from src.core.ast_nodes import App, Const, Equation, Var
from src.core.signature import (
    Axiom, AxiomKind, Operation, Signature, Sort,
    make_assoc_equation, make_comm_equation, make_identity_equation,
)


class TestExpr:
    def test_var(self):
        x = Var("x")
        assert x.size() == 1
        assert x.variables() == {"x"}
        assert repr(x) == "x"

    def test_const(self):
        e = Const("e")
        assert e.size() == 1
        assert e.variables() == set()

    def test_app_binary(self):
        x, y = Var("x"), Var("y")
        expr = App("mul", [x, y])
        assert expr.size() == 3
        assert expr.variables() == {"x", "y"}
        assert "mul" in repr(expr)

    def test_app_unary(self):
        x = Var("x")
        expr = App("inv", [x])
        assert expr.size() == 2
        assert expr.variables() == {"x"}

    def test_nested_app(self):
        x, y, z = Var("x"), Var("y"), Var("z")
        inner = App("mul", [x, y])
        outer = App("mul", [inner, z])
        assert outer.size() == 5
        assert outer.variables() == {"x", "y", "z"}

    def test_substitute(self):
        x, y = Var("x"), Var("y")
        expr = App("mul", [x, y])
        a = Var("a")
        result = expr.substitute({"x": a})
        assert isinstance(result, App)
        assert result.args[0] == a
        assert result.args[1] == y

    def test_equation(self):
        x, y = Var("x"), Var("y")
        eq = Equation(App("mul", [x, y]), App("mul", [y, x]))
        assert eq.variables() == {"x", "y"}
        assert eq.size() == 6


class TestSignature:
    def test_basic_signature(self):
        sig = Signature(
            name="Test",
            sorts=[Sort("S", "carrier")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[],
        )
        assert sig.name == "Test"
        assert len(sig.sorts) == 1
        assert len(sig.operations) == 1
        assert sig.op_names() == ["mul"]

    def test_fingerprint_deterministic(self):
        sig1 = Signature(
            name="A",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"])],
        )
        sig2 = Signature(
            name="B",
            sorts=[Sort("T")],
            operations=[Operation("op", ["T", "T"], "T")],
            axioms=[Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("op"), ["op"])],
        )
        # Same structural shape → same fingerprint
        assert sig1.fingerprint() == sig2.fingerprint()

    def test_fingerprint_differs(self):
        sig1 = Signature(
            name="A",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"])],
        )
        sig2 = Signature(
            name="B",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"]),
                Axiom(AxiomKind.COMMUTATIVITY, make_comm_equation("mul"), ["mul"]),
            ],
        )
        assert sig1.fingerprint() != sig2.fingerprint()

    def test_to_dict(self):
        sig = Signature(
            name="Test",
            sorts=[Sort("S", "carrier")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"])],
        )
        d = sig.to_dict()
        assert d["name"] == "Test"
        assert len(d["sorts"]) == 1
        assert len(d["operations"]) == 1
        assert len(d["axioms"]) == 1

    def test_get_ops_by_arity(self):
        sig = Signature(
            name="Test",
            sorts=[Sort("S")],
            operations=[
                Operation("mul", ["S", "S"], "S"),
                Operation("inv", ["S"], "S"),
                Operation("e", [], "S"),
            ],
        )
        assert len(sig.get_ops_by_arity(2)) == 1
        assert len(sig.get_ops_by_arity(1)) == 1
        assert len(sig.get_ops_by_arity(0)) == 1


class TestEquationBuilders:
    def test_assoc(self):
        eq = make_assoc_equation("mul")
        assert eq.variables() == {"x", "y", "z"}

    def test_comm(self):
        eq = make_comm_equation("mul")
        assert eq.variables() == {"x", "y"}

    def test_identity(self):
        eq = make_identity_equation("mul", "e")
        assert "x" in eq.variables()
