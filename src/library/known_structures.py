"""Library of known algebraic structures as signatures.

These are the seed structures the agent uses as starting points
for structural exploration.
"""

from src.core.signature import (
    Axiom, AxiomKind, Operation, Signature, Sort,
    make_assoc_equation, make_comm_equation, make_identity_equation,
    make_inverse_equation, make_distrib_equation, make_idempotent_equation,
    make_anticomm_equation, make_jacobi_equation,
)


def magma() -> Signature:
    """A set with a binary operation. No axioms."""
    return Signature(
        name="Magma",
        sorts=[Sort("S", "carrier set")],
        operations=[Operation("mul", ["S", "S"], "S", "binary operation")],
        axioms=[],
        description="A set with a single binary operation and no axioms.",
    )


def semigroup() -> Signature:
    return Signature(
        name="Semigroup",
        sorts=[Sort("S", "carrier set")],
        operations=[Operation("mul", ["S", "S"], "S", "associative binary operation")],
        axioms=[
            Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"]),
        ],
        description="A set with an associative binary operation.",
    )


def monoid() -> Signature:
    return Signature(
        name="Monoid",
        sorts=[Sort("S", "carrier set")],
        operations=[
            Operation("mul", ["S", "S"], "S", "associative binary operation"),
            Operation("e", [], "S", "identity element"),
        ],
        axioms=[
            Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"]),
            Axiom(AxiomKind.IDENTITY, make_identity_equation("mul", "e"), ["mul", "e"]),
        ],
        description="A semigroup with an identity element.",
    )


def group() -> Signature:
    return Signature(
        name="Group",
        sorts=[Sort("G", "group elements")],
        operations=[
            Operation("mul", ["G", "G"], "G", "group multiplication"),
            Operation("e", [], "G", "identity element"),
            Operation("inv", ["G"], "G", "group inverse"),
        ],
        axioms=[
            Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"]),
            Axiom(AxiomKind.IDENTITY, make_identity_equation("mul", "e"), ["mul", "e"]),
            Axiom(AxiomKind.INVERSE, make_inverse_equation("mul", "inv", "e"), ["mul", "inv", "e"]),
        ],
        description="A set with associative operation, identity, and inverses.",
    )


def abelian_group() -> Signature:
    sig = group()
    sig.name = "AbelianGroup"
    sig.axioms.append(
        Axiom(AxiomKind.COMMUTATIVITY, make_comm_equation("mul"), ["mul"])
    )
    sig.description = "A group where the operation is commutative."
    return sig


def ring() -> Signature:
    return Signature(
        name="Ring",
        sorts=[Sort("R", "ring elements")],
        operations=[
            Operation("add", ["R", "R"], "R", "addition"),
            Operation("mul", ["R", "R"], "R", "multiplication"),
            Operation("zero", [], "R", "additive identity"),
            Operation("neg", ["R"], "R", "additive inverse"),
        ],
        axioms=[
            Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("add"), ["add"]),
            Axiom(AxiomKind.COMMUTATIVITY, make_comm_equation("add"), ["add"]),
            Axiom(AxiomKind.IDENTITY, make_identity_equation("add", "zero"), ["add", "zero"]),
            Axiom(AxiomKind.INVERSE, make_inverse_equation("add", "neg", "zero"), ["add", "neg"]),
            Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"]),
            Axiom(AxiomKind.DISTRIBUTIVITY, make_distrib_equation("mul", "add"), ["mul", "add"]),
        ],
        description="Abelian group under addition with associative, distributive multiplication.",
    )


def field() -> Signature:
    sig = ring()
    sig.name = "Field"
    sig.operations.append(Operation("one", [], "R", "multiplicative identity"))
    sig.operations.append(Operation("recip", ["R"], "R", "multiplicative inverse (nonzero)"))
    sig.axioms.append(
        Axiom(AxiomKind.COMMUTATIVITY, make_comm_equation("mul"), ["mul"])
    )
    sig.axioms.append(
        Axiom(AxiomKind.IDENTITY, make_identity_equation("mul", "one"), ["mul", "one"])
    )
    sig.description = "A commutative ring where every nonzero element has a multiplicative inverse."
    return sig


def lattice() -> Signature:
    from src.core.ast_nodes import Var, App, Equation
    x, y, z = Var("x"), Var("y"), Var("z")

    return Signature(
        name="Lattice",
        sorts=[Sort("L", "lattice elements")],
        operations=[
            Operation("meet", ["L", "L"], "L", "greatest lower bound"),
            Operation("join", ["L", "L"], "L", "least upper bound"),
        ],
        axioms=[
            Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("meet"), ["meet"]),
            Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("join"), ["join"]),
            Axiom(AxiomKind.COMMUTATIVITY, make_comm_equation("meet"), ["meet"]),
            Axiom(AxiomKind.COMMUTATIVITY, make_comm_equation("join"), ["join"]),
            Axiom(AxiomKind.IDEMPOTENCE, make_idempotent_equation("meet"), ["meet"]),
            Axiom(AxiomKind.IDEMPOTENCE, make_idempotent_equation("join"), ["join"]),
            # Absorption: x meet (x join y) = x
            Axiom(
                AxiomKind.ABSORPTION,
                Equation(App("meet", [x, App("join", [x, y])]), x),
                ["meet", "join"],
                "meet absorbs join",
            ),
            Axiom(
                AxiomKind.ABSORPTION,
                Equation(App("join", [x, App("meet", [x, y])]), x),
                ["meet", "join"],
                "join absorbs meet",
            ),
        ],
        description="A set with meet and join satisfying absorption laws.",
    )


def quasigroup() -> Signature:
    """A set with a binary operation that is a Latin square (left/right division)."""
    from src.core.ast_nodes import Var, App, Equation
    x, y = Var("x"), Var("y")

    return Signature(
        name="Quasigroup",
        sorts=[Sort("Q", "quasigroup elements")],
        operations=[
            Operation("mul", ["Q", "Q"], "Q", "binary operation"),
            Operation("ldiv", ["Q", "Q"], "Q", "left division: a\\b"),
            Operation("rdiv", ["Q", "Q"], "Q", "right division: a/b"),
        ],
        axioms=[
            # a * (a \ b) = b
            Axiom(
                AxiomKind.CUSTOM,
                Equation(App("mul", [x, App("ldiv", [x, y])]), y),
                ["mul", "ldiv"],
                "left cancellation",
            ),
            # (a / b) * b = a
            Axiom(
                AxiomKind.CUSTOM,
                Equation(App("mul", [App("rdiv", [x, y]), y]), x),
                ["mul", "rdiv"],
                "right cancellation",
            ),
            # a \ (a * b) = b
            Axiom(
                AxiomKind.CUSTOM,
                Equation(App("ldiv", [x, App("mul", [x, y])]), y),
                ["mul", "ldiv"],
                "left division cancellation",
            ),
            # (a * b) / b = a
            Axiom(
                AxiomKind.CUSTOM,
                Equation(App("rdiv", [App("mul", [x, y]), y]), x),
                ["mul", "rdiv"],
                "right division cancellation",
            ),
        ],
        description="A Latin square: binary operation with unique solutions to a*x=b and y*a=b.",
    )


def loop() -> Signature:
    """A quasigroup with an identity element."""
    sig = quasigroup()
    sig.name = "Loop"
    sig.operations.append(Operation("e", [], "Q", "identity element"))
    sig.axioms.append(
        Axiom(AxiomKind.IDENTITY, make_identity_equation("mul", "e"), ["mul", "e"])
    )
    sig.description = "A quasigroup with a two-sided identity element."
    return sig


def lie_algebra() -> Signature:
    """Lie algebra: vector space with antisymmetric bracket satisfying Jacobi."""
    return Signature(
        name="LieAlgebra",
        sorts=[Sort("L", "Lie algebra elements"), Sort("K", "scalar field")],
        operations=[
            Operation("add", ["L", "L"], "L", "vector addition"),
            Operation("scale", ["K", "L"], "L", "scalar multiplication"),
            Operation("bracket", ["L", "L"], "L", "Lie bracket"),
            Operation("neg", ["L"], "L", "additive inverse"),
            Operation("zero", [], "L", "zero vector"),
        ],
        axioms=[
            Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("add"), ["add"]),
            Axiom(AxiomKind.COMMUTATIVITY, make_comm_equation("add"), ["add"]),
            Axiom(AxiomKind.IDENTITY, make_identity_equation("add", "zero"), ["add", "zero"]),
            Axiom(AxiomKind.INVERSE, make_inverse_equation("add", "neg", "zero"), ["add", "neg"]),
            Axiom(AxiomKind.ANTICOMMUTATIVITY, make_anticomm_equation("bracket"),
                  ["bracket", "neg"], "antisymmetry of bracket"),
            Axiom(AxiomKind.JACOBI, make_jacobi_equation("bracket"),
                  ["bracket", "add", "neg"], "Jacobi identity"),
            Axiom(AxiomKind.BILINEARITY, make_distrib_equation("bracket", "add"),
                  ["bracket", "add"], "bracket is bilinear (left)"),
        ],
        description="A vector space with an antisymmetric bracket satisfying the Jacobi identity.",
    )


def vector_space() -> Signature:
    """Vector space over a field."""
    return Signature(
        name="VectorSpace",
        sorts=[Sort("V", "vectors"), Sort("K", "scalars")],
        operations=[
            Operation("add", ["V", "V"], "V", "vector addition"),
            Operation("scale", ["K", "V"], "V", "scalar multiplication"),
            Operation("neg", ["V"], "V", "additive inverse"),
            Operation("zero", [], "V", "zero vector"),
        ],
        axioms=[
            Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("add"), ["add"]),
            Axiom(AxiomKind.COMMUTATIVITY, make_comm_equation("add"), ["add"]),
            Axiom(AxiomKind.IDENTITY, make_identity_equation("add", "zero"), ["add", "zero"]),
            Axiom(AxiomKind.INVERSE, make_inverse_equation("add", "neg", "zero"), ["add", "neg"]),
        ],
        description="A module over a field with vector addition and scalar multiplication.",
    )


def inner_product_space() -> Signature:
    """Vector space with an inner product."""
    from src.core.ast_nodes import Var, App, Equation
    sig = vector_space()
    sig.name = "InnerProductSpace"
    sig.operations.append(
        Operation("inner", ["V", "V"], "K", "inner product ⟨·,·⟩")
    )
    x, y = Var("x"), Var("y")
    sig.axioms.append(
        Axiom(AxiomKind.COMMUTATIVITY,
              Equation(App("inner", [x, y]), App("inner", [y, x])),
              ["inner"], "symmetry of inner product")
    )
    sig.axioms.append(
        Axiom(AxiomKind.POSITIVITY,
              Equation(App("inner", [x, x]), App("inner", [x, x])),
              ["inner"], "⟨x,x⟩ ≥ 0 (positivity, encoded symbolically)")
    )
    sig.description = "A vector space with a symmetric, positive-definite inner product."
    return sig


def category_sig() -> Signature:
    """The signature of a category (objects, morphisms, composition)."""
    from src.core.ast_nodes import Var, App, Equation
    f, g, h = Var("f"), Var("g"), Var("h")

    return Signature(
        name="Category",
        sorts=[Sort("Ob", "objects"), Sort("Mor", "morphisms")],
        operations=[
            Operation("comp", ["Mor", "Mor"], "Mor", "morphism composition"),
            Operation("id", ["Ob"], "Mor", "identity morphism"),
            Operation("dom", ["Mor"], "Ob", "domain of a morphism"),
            Operation("cod", ["Mor"], "Ob", "codomain of a morphism"),
        ],
        axioms=[
            Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("comp"), ["comp"]),
            Axiom(
                AxiomKind.IDENTITY,
                Equation(App("comp", [f, App("id", [App("dom", [f])])]), f),
                ["comp", "id", "dom"],
                "right identity",
            ),
            Axiom(
                AxiomKind.IDENTITY,
                Equation(App("comp", [App("id", [App("cod", [f])]), f]), f),
                ["comp", "id", "cod"],
                "left identity",
            ),
        ],
        description="Objects and morphisms with associative composition and identities.",
    )


# Registry of all known structures
KNOWN_STRUCTURES: dict[str, callable] = {
    "Magma": magma,
    "Semigroup": semigroup,
    "Monoid": monoid,
    "Group": group,
    "AbelianGroup": abelian_group,
    "Ring": ring,
    "Field": field,
    "Lattice": lattice,
    "Quasigroup": quasigroup,
    "Loop": loop,
    "LieAlgebra": lie_algebra,
    "VectorSpace": vector_space,
    "InnerProductSpace": inner_product_space,
    "Category": category_sig,
}


def load_all_known() -> list[Signature]:
    """Load all known structures."""
    return [factory() for factory in KNOWN_STRUCTURES.values()]


def load_by_name(name: str) -> Signature | None:
    factory = KNOWN_STRUCTURES.get(name)
    return factory() if factory else None
