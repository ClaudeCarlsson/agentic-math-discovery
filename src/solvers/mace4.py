"""Mace4 integration: finite model finding via subprocess.

Mace4 is a program that searches for finite models of first-order
theories. It's part of the LADR (Library for Automated Deduction Research)
package by William McCune.

Install: https://www.cs.unm.edu/~mccune/prover9/
Or: apt-get install prover9 (on Debian/Ubuntu)
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from src.core.signature import Signature
from src.models.cayley import CayleyTable
from src.solvers.fol_translator import FOLTranslator


@dataclass
class Mace4Result:
    """Result from a Mace4 model search."""

    domain_size: int
    models_found: list[CayleyTable]
    exit_code: int
    raw_output: str
    error: str = ""
    timed_out: bool = False


@dataclass
class ModelSpectrum:
    """The spectrum of model sizes for a signature.

    Maps domain size → number of non-isomorphic models found.
    """

    signature_name: str
    spectrum: dict[int, int] = field(default_factory=dict)
    models_by_size: dict[int, list[CayleyTable]] = field(default_factory=dict)
    timed_out_sizes: list[int] = field(default_factory=list)

    def sizes_with_models(self) -> list[int]:
        return sorted(k for k, v in self.spectrum.items() if v > 0)

    def total_models(self) -> int:
        return sum(self.spectrum.values())

    def is_empty(self) -> bool:
        return self.total_models() == 0

    def any_timed_out(self) -> bool:
        return len(self.timed_out_sizes) > 0

    def __repr__(self) -> str:
        sizes = self.sizes_with_models()
        return f"Spectrum({self.signature_name}: {dict((s, self.spectrum[s]) for s in sizes)})"


class Mace4Solver:
    """Interface to Mace4 finite model finder."""

    def __init__(self, mace4_path: str = "mace4", timeout: int = 30):
        self.mace4_path = mace4_path
        self.timeout = timeout
        self.translator = FOLTranslator()

    def is_available(self) -> bool:
        """Check if Mace4 is installed and accessible."""
        try:
            result = subprocess.run(
                [self.mace4_path, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode in (0, 1)  # mace4 may return 1 for --version
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError, OSError):
            return False

    def find_models(
        self,
        sig: Signature,
        domain_size: int,
        max_models: int = 10,
    ) -> Mace4Result:
        """Search for finite models of the given signature at a specific domain size."""
        input_text = self.translator.to_mace4(sig, domain_size)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".in", delete=False) as f:
            f.write(input_text)
            input_path = f.name

        try:
            cmd = [self.mace4_path, "-n", str(domain_size), "-N", str(domain_size)]
            if max_models > 1:
                cmd.extend(["-m", str(max_models)])

            result = subprocess.run(
                cmd,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            models = self._parse_output(result.stdout, sig, domain_size)

            return Mace4Result(
                domain_size=domain_size,
                models_found=models,
                exit_code=result.returncode,
                raw_output=result.stdout,
                error=result.stderr,
            )

        except subprocess.TimeoutExpired:
            return Mace4Result(
                domain_size=domain_size,
                models_found=[],
                exit_code=-1,
                raw_output="",
                error="Timed out",
                timed_out=True,
            )
        finally:
            os.unlink(input_path)

    def compute_spectrum(
        self,
        sig: Signature,
        min_size: int = 2,
        max_size: int = 8,
        max_models_per_size: int = 10,
    ) -> ModelSpectrum:
        """Compute the model spectrum: how many models exist at each size."""
        spectrum = ModelSpectrum(signature_name=sig.name)

        for size in range(min_size, max_size + 1):
            result = self.find_models(sig, size, max_models_per_size)
            n_models = len(result.models_found)
            spectrum.spectrum[size] = n_models
            spectrum.models_by_size[size] = result.models_found

        return spectrum

    def _parse_output(
        self, output: str, sig: Signature, domain_size: int
    ) -> list[CayleyTable]:
        """Parse Mace4 output into CayleyTable objects.

        Mace4 output format for a binary function:
        function(f(_,_), [
            0,1,2,
            1,2,0,
            2,0,1
        ]).
        """
        models: list[CayleyTable] = []

        # Split by interpretation blocks
        interp_blocks = re.split(r"={10,}", output)

        for block in interp_blocks:
            if "interpretation" not in block:
                continue

            tables: dict[str, np.ndarray] = {}
            constants: dict[str, int] = {}

            # Parse function tables
            func_pattern = r"function\((\w+)\(_,_\),\s*\[\s*([\d,\s]+)\]\)"
            for match in re.finditer(func_pattern, block):
                name = match.group(1)
                values_str = match.group(2)
                values = [int(v.strip()) for v in values_str.split(",") if v.strip()]

                n = domain_size
                if len(values) == n * n:
                    table = np.array(values).reshape(n, n)
                    tables[name] = table

            # Parse constants
            const_pattern = r"function\((\w+),\s*\[\s*(\d+)\s*\]\)"
            for match in re.finditer(const_pattern, block):
                name = match.group(1)
                value = int(match.group(2))
                constants[name] = value

            # Parse unary functions
            unary_pattern = r"function\((\w+)\(_\),\s*\[\s*([\d,\s]+)\]\)"
            for match in re.finditer(unary_pattern, block):
                name = match.group(1)
                values_str = match.group(2)
                values = [int(v.strip()) for v in values_str.split(",") if v.strip()]
                # Store unary as 1×n array in tables with special key
                tables[f"_unary_{name}"] = np.array(values)

            if tables:
                models.append(CayleyTable(
                    size=domain_size,
                    tables=tables,
                    constants=constants,
                ))

        return models


class Mace4Fallback:
    """Fallback model finder using Z3 when Mace4 is not installed.

    Provides the same interface but uses Z3's finite model finding capabilities.
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def find_models(
        self,
        sig: Signature,
        domain_size: int,
        max_models: int = 10,
    ) -> Mace4Result:
        """Search for models using Z3."""
        try:
            from src.solvers.z3_solver import Z3ModelFinder
            z3_solver = Z3ModelFinder(timeout_ms=self.timeout * 1000)
            return z3_solver.find_models(sig, domain_size, max_models)
        except ImportError:
            return Mace4Result(
                domain_size=domain_size,
                models_found=[],
                exit_code=-1,
                raw_output="",
                error="Neither Mace4 nor Z3 available",
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
        return spectrum
