"""Cayley table representation and analysis for finite algebraic models."""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Any
from math import log2


@dataclass
class CayleyTable:
    """A finite model represented as a Cayley (multiplication) table.

    The table is an n×n matrix where entry [i][j] = i op j.
    For multi-operation structures, we store one table per operation.
    """

    size: int
    tables: dict[str, np.ndarray]  # op_name -> n×n array
    constants: dict[str, int] = field(default_factory=dict)  # const_name -> element index

    def is_latin_square(self, op_name: str) -> bool:
        """Check if the table for `op_name` is a Latin square (quasigroup property)."""
        table = self.tables.get(op_name)
        if table is None:
            return False
        n = self.size
        for i in range(n):
            if len(set(table[i])) != n:
                return False
            if len(set(table[:, i])) != n:
                return False
        return True

    def is_commutative(self, op_name: str) -> bool:
        table = self.tables.get(op_name)
        if table is None:
            return False
        return np.array_equal(table, table.T)

    def has_identity(self, op_name: str) -> int | None:
        """Return the identity element index, or None if no identity exists."""
        table = self.tables.get(op_name)
        if table is None:
            return None
        n = self.size
        for e in range(n):
            is_id = True
            for x in range(n):
                if table[e][x] != x or table[x][e] != x:
                    is_id = False
                    break
            if is_id:
                return e
        return None

    def is_associative(self, op_name: str) -> bool:
        table = self.tables.get(op_name)
        if table is None:
            return False
        n = self.size
        for a in range(n):
            for b in range(n):
                for c in range(n):
                    if table[table[a][b]][c] != table[a][table[b][c]]:
                        return False
        return True

    def row_entropy(self, op_name: str) -> float:
        """Average Shannon entropy across rows of the Cayley table."""
        table = self.tables.get(op_name)
        if table is None:
            return 0.0
        n = self.size
        total_h = 0.0
        for row in table:
            counts = np.bincount(row.astype(int), minlength=n)
            probs = counts / n
            probs = probs[probs > 0]
            total_h += -np.sum(probs * np.log2(probs))
        return total_h / n

    def column_entropy(self, op_name: str) -> float:
        """Average Shannon entropy across columns of the Cayley table."""
        table = self.tables.get(op_name)
        if table is None:
            return 0.0
        n = self.size
        total_h = 0.0
        for col_idx in range(n):
            col = table[:, col_idx]
            counts = np.bincount(col.astype(int), minlength=n)
            probs = counts / n
            probs = probs[probs > 0]
            total_h += -np.sum(probs * np.log2(probs))
        return total_h / n

    def max_entropy(self) -> float:
        """Maximum possible entropy for a table of this size."""
        if self.size <= 1:
            return 0.0
        return log2(self.size)

    def symmetry_score(self, op_name: str) -> float:
        """Score how structured/symmetric the table is. 1.0 = perfect Latin square."""
        table = self.tables.get(op_name)
        if table is None:
            return 0.0
        n = self.size
        score = 0.0
        for i in range(n):
            row_unique = len(set(table[i]))
            col_unique = len(set(table[:, i]))
            score += (row_unique + col_unique) / (2 * n)
        return score / n

    def automorphism_count_estimate(self, op_name: str) -> int:
        """Estimate the number of automorphisms by checking permutations
        on small models. Only feasible for size <= 8."""
        table = self.tables.get(op_name)
        if table is None or self.size > 8:
            return 0
        from itertools import permutations
        n = self.size
        count = 0
        for perm in permutations(range(n)):
            is_auto = True
            for a in range(n):
                for b in range(n):
                    if perm[table[a][b]] != table[perm[a]][perm[b]]:
                        is_auto = False
                        break
                if not is_auto:
                    break
            if is_auto:
                count += 1
        return count

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "tables": {k: v.tolist() for k, v in self.tables.items()},
            "constants": self.constants,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CayleyTable:
        return cls(
            size=data["size"],
            tables={k: np.array(v) for k, v in data["tables"].items()},
            constants=data.get("constants", {}),
        )

    def __repr__(self) -> str:
        ops = ", ".join(self.tables.keys())
        return f"CayleyTable(size={self.size}, ops=[{ops}])"


def models_are_isomorphic(m1: CayleyTable, m2: CayleyTable, op_name: str) -> bool:
    """Check if two models are isomorphic for a given operation.

    Brute-force check over all permutations. Only feasible for size <= 10.
    """
    if m1.size != m2.size:
        return False
    if m1.size > 10:
        return False  # too expensive

    from itertools import permutations
    n = m1.size
    t1 = m1.tables[op_name]
    t2 = m2.tables[op_name]

    for perm in permutations(range(n)):
        match = True
        for a in range(n):
            for b in range(n):
                if perm[t1[a][b]] != t2[perm[a]][perm[b]]:
                    match = False
                    break
            if not match:
                break
        if match:
            return True
    return False
