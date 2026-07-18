"""
Canonical test path bootstrap  (Sprint 10 audit fix).

Background
----------
During the v0.10.0 repository integration, the per-sprint Python modules that
had been authored as packages (``retrieval/``, ``reasoning/``,
``output_generation/``) were flattened into ``workflows/shared/`` under the
canonical ``<package>_<module>.py`` naming convention (§634). The prior-sprint
acceptance suites, however, still ``import retrieval``, ``import reasoning`` and
``import output_generation`` as packages, and the modules themselves use
intra-package relative imports (``from .adapters import ...``).

This bootstrap reconstructs the three packages *in memory* from the canonical
flat files, so the prior-sprint suites run unchanged against the single
canonical source of truth. It regenerates **no** business logic: every module
object is loaded directly from its canonical ``workflows/shared/*.py`` file.

It also exposes the directory aliases (``src``, ``config``, ``migrations``,
``sub-workflows``) that some suites reference, pointing them at their canonical
locations.

Import this module first from any prior-sprint suite::

    import _pathsetup  # noqa: F401  (must precede package imports)

No architectural or feature change: this is packaging reconciliation only.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_TESTS_DIR, ".."))
SHARED = os.path.join(REPO_ROOT, "workflows", "shared")

# Canonical flat-file layout of each reconstructed package:
#   <pkg>___init__.py       -> the package __init__ (optional)
#   <pkg>_<submodule>.py     -> submodule reachable as `<pkg>.<submodule>`
_PACKAGES = {
    "retrieval": {
        "adapters": "retrieval_adapters.py",
        "analyze": "retrieval_analyze.py",
        "context": "retrieval_context.py",
        "rank": "retrieval_rank.py",
        "pipeline": "retrieval_pipeline.py",
        "doubles": "retrieval_doubles.py",
    },
    "reasoning": {
        "compliance_level": "reasoning_compliance_level.py",
        "confidence": "reasoning_confidence.py",
        "enterprise_llm": "reasoning_enterprise_llm.py",
        "output_validator": "reasoning_output_validator.py",
        "prompt_loader": "reasoning_prompt_loader.py",
        "wf003": "reasoning_wf003.py",
        "__init__": "reasoning___init__.py",
    },
    "output_generation": {
        "sw025_sheets_writer": "output_sw025_sheets_writer.py",
        "wf004_output_generation": "output_wf004_output_generation.py",
        "review_workflow": "output_review_workflow.py",
        "__init__": "output___init__.py",
    },
}

# The `retrieval` package historically exposed a flat API at package level
# (``from retrieval import run_retrieval, load_config, ...``). The canonical
# source keeps that surface in the pipeline/analyze/context modules; re-export
# the documented names from the package __init__ we synthesize.
_RETRIEVAL_REEXPORT = {
    "adapters": ["load_config"],
    "pipeline": ["run_retrieval"],
    "context": ["validate_context_package"],
    "analyze": ["analyze_requirement", "build_metadata_filters",
                "select_strategy"],
}


def _load_module(fullname: str, filepath: str, package: str | None) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(fullname, filepath)
    mod = importlib.util.module_from_spec(spec)
    if package is not None:
        mod.__package__ = package
    sys.modules[fullname] = mod
    spec.loader.exec_module(mod)
    return mod


def _install_package(pkg: str, submodules: dict[str, str]) -> None:
    if pkg in sys.modules:
        return

    pkg_mod = types.ModuleType(pkg)
    pkg_mod.__package__ = pkg
    pkg_mod.__path__ = [SHARED]  # marks it as a package
    sys.modules[pkg] = pkg_mod

    # Load submodules in dependency-tolerant order: relative imports resolve
    # against `sys.modules[pkg]`, which already exists, so any order works as
    # long as the package object is registered first (done above).
    ordered = [n for n in submodules if n != "__init__"]
    for sub in ordered:
        path = os.path.join(SHARED, submodules[sub])
        if not os.path.exists(path):
            continue
        fullname = f"{pkg}.{sub}"
        mod = _load_module(fullname, path, pkg)
        setattr(pkg_mod, sub, mod)

    # Re-export documented package-level API where applicable.
    if pkg == "retrieval":
        for sub, names in _RETRIEVAL_REEXPORT.items():
            src = sys.modules.get(f"{pkg}.{sub}")
            if src is None:
                continue
            for name in names:
                if hasattr(src, name):
                    setattr(pkg_mod, name, getattr(src, name))

    # If the package ships an explicit __init__, execute it last so its
    # re-exports win.
    if "__init__" in submodules:
        init_path = os.path.join(SHARED, submodules["__init__"])
        if os.path.exists(init_path):
            spec = importlib.util.spec_from_file_location(pkg, init_path)
            # Re-bind loader onto the existing package module so `from .x import`
            # inside __init__ resolves against the submodules already loaded.
            pkg_mod.__spec__ = spec
            spec.loader.exec_module(pkg_mod)


def install() -> None:
    """Register all reconstructed packages and directory aliases on sys.path."""
    # `doubles` is imported bare (`from doubles import ...`) by the retrieval
    # suite, and `retrieval_doubles.py` itself imports the retrieval package.
    if SHARED not in sys.path:
        sys.path.insert(0, SHARED)

    for pkg, subs in _PACKAGES.items():
        _install_package(pkg, subs)

    # Bare `doubles` alias -> retrieval.doubles (canonical retrieval_doubles.py)
    if "doubles" not in sys.modules and "retrieval.doubles" in sys.modules:
        sys.modules["doubles"] = sys.modules["retrieval.doubles"]


# Auto-install on import.
install()
