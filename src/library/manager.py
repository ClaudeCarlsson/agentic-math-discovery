"""Library Manager: persistent storage of known and discovered structures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.signature import Signature
from src.scoring.engine import ScoreBreakdown


class LibraryManager:
    """Manages the library of known and discovered algebraic structures."""

    def __init__(self, base_path: Path | str = "library"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        (self.base_path / "known").mkdir(exist_ok=True)
        (self.base_path / "discovered").mkdir(exist_ok=True)
        (self.base_path / "conjectures").mkdir(exist_ok=True)
        (self.base_path / "reports").mkdir(exist_ok=True)

        self._known_cache: dict[str, dict] | None = None

    def known_fingerprints(self) -> list[str]:
        """Get fingerprints of all known structures."""
        from src.library.known_structures import load_all_known
        return [sig.fingerprint() for sig in load_all_known()]

    def list_known(self) -> list[str]:
        """List names of all known structures."""
        from src.library.known_structures import KNOWN_STRUCTURES
        return list(KNOWN_STRUCTURES.keys())

    def list_discovered(self) -> list[dict[str, Any]]:
        """List all discovered structures with metadata."""
        discovered_dir = self.base_path / "discovered"
        results = []
        for f in sorted(discovered_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                results.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def add_discovery(
        self,
        sig: Signature,
        name: str,
        notes: str,
        score: ScoreBreakdown,
    ) -> Path:
        """Add a new discovery to the library."""
        discovered_dir = self.base_path / "discovered"
        existing = list(discovered_dir.glob("disc_*.json"))
        next_id = len(existing) + 1

        filename = f"disc_{next_id:04d}_{_safe_name(name)}.json"
        path = discovered_dir / filename

        data = {
            "id": f"disc_{next_id:04d}",
            "name": name,
            "signature": sig.to_dict(),
            "derivation_chain": sig.derivation_chain,
            "score": score.total,
            "score_breakdown": score.to_dict(),
            "notes": notes,
            "fingerprint": sig.fingerprint(),
        }

        path.write_text(json.dumps(data, indent=2))
        return path

    def add_conjecture(
        self,
        signature_name: str,
        statement: str,
        status: str,
        details: str = "",
    ) -> None:
        """Record a conjecture."""
        conj_dir = self.base_path / "conjectures"
        status_file = conj_dir / f"{status}.json"

        existing = []
        if status_file.exists():
            try:
                existing = json.loads(status_file.read_text())
            except json.JSONDecodeError:
                existing = []

        existing.append({
            "signature": signature_name,
            "statement": statement,
            "status": status,
            "details": details,
        })

        status_file.write_text(json.dumps(existing, indent=2))

    def search(
        self,
        query: str,
        min_score: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search known and discovered structures."""
        results = []

        # Search known
        from src.library.known_structures import KNOWN_STRUCTURES
        query_lower = query.lower()
        for name in KNOWN_STRUCTURES:
            if query_lower in name.lower():
                results.append({"name": name, "type": "known", "description": ""})

        # Search discovered
        for disc in self.list_discovered():
            name = disc.get("name", "")
            notes = disc.get("notes", "")
            score = disc.get("score", 0)

            if min_score and score < min_score:
                continue

            if query_lower in name.lower() or query_lower in notes.lower():
                results.append({
                    "name": name,
                    "type": "discovered",
                    "score": score,
                    "description": notes,
                })

        return results

    def get_discovery(self, discovery_id: str) -> dict[str, Any] | None:
        """Get a specific discovery by ID."""
        for disc in self.list_discovered():
            if disc.get("id") == discovery_id:
                return disc
        return None


def _safe_name(name: str) -> str:
    """Convert a name to a safe filename."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:50]
