# All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying,
# modification, distribution, or commercial use is prohibited without written
# permission.
"""
SW-022 — Prompt Loader.

Governance: §262, §173 (canonical catalog PR-001..PR-008 / R-04), §174
(versioning), §175 (loading flow), §176 (variable injection), §86 (execution
rules), §177 (model settings), §178 (guardrails).

Behavior:
  - Loads a prompt by ID + version from the Prompt Registry manifest (source of
    truth per R-08; bodies live in the registry, never embedded in workflows —
    §86/§175 "Prompts SHALL NOT be hardcoded / embedded inside workflows").
  - Injects runtime variables (§176). A missing required variable SHALL stop
    execution (§176 "Missing variables SHALL stop execution").

For Sprint 6, WF-003 loads PR-004 (Compliance Assessment) for SW-023 and PR-005
(Output Validation) for SW-024, per §173 and the S6 backlog (S6-1, S6-5).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


class PromptNotFoundError(Exception):
    pass


class MissingVariableError(Exception):
    """Raised per §176 when a declared prompt variable is not supplied."""


@dataclass(frozen=True)
class PromptModelSettings:
    """§177 model settings owned by the prompt, not the workflow."""

    provider: str
    model: str
    temperature: float
    top_p: float
    max_tokens: int
    frequency_penalty: float
    presence_penalty: float
    timeout: int


@dataclass(frozen=True)
class PromptObject:
    """Output of SW-022 (§262 'Prompt Object')."""

    prompt_id: str
    version: str
    purpose: str
    system_prompt: str
    user_template: str
    declared_variables: List[str]
    guardrails: List[str]
    model_settings: PromptModelSettings


_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def _declared_from_template(template: str) -> List[str]:
    seen: List[str] = []
    for m in _VAR_PATTERN.finditer(template):
        name = m.group(1)
        if name not in seen:
            seen.append(name)
    return seen


class PromptLoader:
    """
    SW-022 implementation.

    `registry` is the parsed Prompt Registry manifest keyed as
    registry[prompt_id][version] -> prompt record dict. The manifest is the
    authored source of truth (Sprint 1 artifact, extended in Sprint 6 with the
    PR-004 / PR-005 bodies actually needed by WF-003).
    """

    def __init__(self, registry: Dict[str, Dict[str, dict]]):
        self._registry = registry

    def load(self, prompt_id: str, version: Optional[str] = None) -> PromptObject:
        versions = self._registry.get(prompt_id)
        if not versions:
            raise PromptNotFoundError(f"Prompt {prompt_id} not in registry")

        if version is None:
            # §174: workflows reference a specific version; when unspecified,
            # resolve the highest published version deterministically.
            version = max(versions.keys(), key=_version_key)

        record = versions.get(version)
        if record is None:
            raise PromptNotFoundError(f"Prompt {prompt_id} v{version} not found")

        ms = record["modelSettings"]
        user_template = record["userTemplate"]
        return PromptObject(
            prompt_id=prompt_id,
            version=version,
            purpose=record["purpose"],
            system_prompt=record["systemPrompt"],
            user_template=user_template,
            declared_variables=record.get(
                "variables", _declared_from_template(user_template)
            ),
            guardrails=record.get("guardrails", []),
            model_settings=PromptModelSettings(
                provider=ms["provider"],
                model=ms["model"],
                temperature=ms["temperature"],
                top_p=ms["topP"],
                max_tokens=ms["maxTokens"],
                frequency_penalty=ms["frequencyPenalty"],
                presence_penalty=ms["presencePenalty"],
                timeout=ms["timeout"],
            ),
        )

    @staticmethod
    def inject(prompt: PromptObject, variables: Dict[str, str]) -> str:
        """
        §176 variable injection into the user template.

        Every declared variable MUST be supplied; a missing one stops execution
        (raises MissingVariableError). Unused supplied variables are ignored.
        """
        missing = [v for v in prompt.declared_variables if v not in variables]
        if missing:
            raise MissingVariableError(
                f"{prompt.prompt_id}: missing variables {sorted(missing)}"
            )

        def _sub(m: re.Match) -> str:
            return str(variables[m.group(1)])

        return _VAR_PATTERN.sub(_sub, prompt.user_template)


def _version_key(v: str):
    return tuple(int(p) for p in v.split("."))
