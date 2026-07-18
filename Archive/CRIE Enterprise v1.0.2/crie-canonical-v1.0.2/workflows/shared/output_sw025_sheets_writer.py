"""
SW-025 — Google Sheets Writer.
All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
Unauthorized copying, modification, distribution, or commercial use is prohibited
without written permission.

Authoritative: §265 (SW-025), Module 35 §363-§364 (configurable column mapping),
§102/§547 (Compliance Matrix columns), R-08 (YAML-authored config).

This node maps a Compliance Result (§295) to a Google Sheet row using the
configuration-driven column mapping ONLY. No column numbers are hardcoded here
(§364). Live spreadsheet I/O is performed by the Provider Adapter layer in the
target deployment (scaffold-then-provision); this module produces the deterministic
row payload the adapter consumes.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _resolve(source: str, result: Dict[str, Any]) -> Any:
    """Resolve a dotted 'source' path against a Compliance Result (§295)."""
    node: Any = result
    for part in source.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return None
    return node


def _stringify(value: Any) -> str:
    """Deterministic string rendering for a sheet cell (§113)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, list):
        # Join list-valued fields (citations, evidence) deterministically.
        parts: List[str] = []
        for item in value:
            if isinstance(item, dict):
                # Prefer a human-readable field if present, else stable JSON-ish.
                for key in ("citation", "text", "summary", "reference", "id"):
                    if key in item and item[key] is not None:
                        parts.append(str(item[key]))
                        break
                else:
                    parts.append("; ".join(f"{k}={item[k]}" for k in sorted(item)))
            else:
                parts.append(str(item))
        return " | ".join(parts)
    return str(value)


def build_row(result: Dict[str, Any], output_config: Dict[str, Any]) -> Dict[str, str]:
    """
    Build one sheet row keyed by sheetsColumn (e.g. 'A', 'B', ...) from the
    configured Compliance Matrix column mapping. Deterministic (§113).
    """
    columns = output_config["complianceMatrix"]["columns"]
    row: Dict[str, str] = {}
    for col in columns:
        cell = _resolve(col["source"], result)
        row[col["sheetsColumn"]] = _stringify(cell)
    return row


def build_header(output_config: Dict[str, Any]) -> Dict[str, str]:
    """Header row keyed by sheetsColumn, in configured order."""
    columns = output_config["complianceMatrix"]["columns"]
    return {col["sheetsColumn"]: col["header"] for col in columns}


def build_matrix(results: List[Dict[str, Any]], output_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assemble the full Compliance Matrix payload for the Google Sheets adapter.
    Ordering follows the input requirement order (deterministic, §113).
    """
    return {
        "tab": output_config["googleSheets"]["tabs"]["complianceMatrix"],
        "freezeHeaderRow": output_config["googleSheets"]["freezeHeaderRow"],
        "header": build_header(output_config),
        "rows": [build_row(r, output_config) for r in results],
    }
