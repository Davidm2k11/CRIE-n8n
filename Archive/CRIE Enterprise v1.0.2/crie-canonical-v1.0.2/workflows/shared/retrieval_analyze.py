"""
CRIE Retrieval — SW-016 Requirement Analyzer and SW-017 Metadata Filter.

  SW-016 (§256, §453): normalize requirement, expand acronyms/synonyms,
          derive metadata expansions, produce Requirement Profile.
  strategy selection (§456).
  SW-017 (§257, §457): metadata filtering before retrieval.

License: All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .adapters import DictionaryStore, RetrievalConfig

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with",
    "is", "are", "be", "must", "shall", "should", "that", "this", "it",
    "as", "by", "at", "from", "will",
}
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-]*")
_PUNCT_RE = re.compile(r"[^\w\s\-]")
# Capitalised tokens in the *raw* requirement are treated as entities/acronyms.
_ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}\b")
_ENTITY_RE = re.compile(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b")


@dataclass
class RequirementProfile:
    """SW-016 output (§256/§453/§76)."""

    normalized_query: str
    keywords: list[str]
    entities: list[str]
    modules: list[str]
    product: str | None
    intent: str | None
    language: str
    filters: dict[str, Any] = field(default_factory=dict)
    expanded_terms: list[str] = field(default_factory=list)  # synonym/acronym/metadata

    def to_json(self) -> dict[str, Any]:
        return {
            "normalizedQuery": self.normalized_query,
            "keywords": self.keywords,
            "entities": self.entities,
            "modules": self.modules,
            "product": self.product,
            "intent": self.intent,
            "language": self.language,
            "filters": self.filters,
        }


def _detect_language(text: str) -> str:
    # Deterministic, dependency-free heuristic; live impl uses a detector.
    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"
    return "en"


def _detect_intent(raw: str) -> str | None:
    low = raw.lower()
    if any(k in low for k in ("support", "compliant", "does it", "can it")):
        return "compliance_check"
    if any(k in low for k in ("how", "configure", "setup", "steps")):
        return "how_to"
    return None


def analyze_requirement(
    raw_requirement: str,
    cfg: RetrievalConfig,
    dictionaries: DictionaryStore,
    metadata_hints: dict[str, Any] | None = None,
) -> RequirementProfile:
    """SW-016 (§256) + normalization (§453) + expansions (§454/§455)."""
    metadata_hints = metadata_hints or {}
    language = _detect_language(raw_requirement)
    intent = _detect_intent(raw_requirement)

    # Raw-case extraction (before lowercasing) for entities/acronyms.
    raw_acronyms = _ACRONYM_RE.findall(raw_requirement)
    entities = sorted(set(_ENTITY_RE.findall(raw_requirement)))

    # §453 normalization: lowercase → remove punctuation → tokenize → stopwords.
    lowered = raw_requirement.lower()
    depunct = _PUNCT_RE.sub(" ", lowered)
    tokens = [t for t in _WORD_RE.findall(depunct) if t not in _STOPWORDS]

    expanded: list[str] = []

    # §453/§455 acronym normalization + synonym expansion (config-gated).
    if cfg.expansion.get("acronymNormalization", True):
        for ac in raw_acronyms:
            exp = dictionaries.acronym_expansion(ac)
            if exp:
                for w in _WORD_RE.findall(exp.lower()):
                    if w not in _STOPWORDS:
                        expanded.append(w)

    if cfg.expansion.get("synonymExpansion", True):
        for t in list(tokens):
            for syn in dictionaries.synonyms(t):
                for w in _WORD_RE.findall(syn.lower()):
                    if w not in _STOPWORDS:
                        expanded.append(w)

    # §454 metadata expansion → derived filters (config-gated).
    derived_filters: dict[str, Any] = dict(metadata_hints)
    if cfg.expansion.get("metadataExpansion", True):
        derived: list[str] = []
        for t in tokens + [e.lower() for e in entities]:
            derived.extend(dictionaries.metadata_expansions(t))
        if derived:
            derived_filters.setdefault("expandedTopics", sorted(set(derived)))

    keywords = _dedup_preserve(tokens + expanded)
    normalized_query = " ".join(_dedup_preserve(tokens + expanded))
    expanded_terms = _dedup_preserve(expanded)

    modules = list(dict.fromkeys(
        list(metadata_hints.get("modules", [])) + derived_filters.get("expandedTopics", [])
    )) if metadata_hints.get("modules") else list(metadata_hints.get("modules", []))

    product = metadata_hints.get("product")

    return RequirementProfile(
        normalized_query=normalized_query,
        keywords=keywords,
        entities=entities,
        modules=modules,
        product=product,
        intent=intent,
        language=language,
        filters=derived_filters,
        expanded_terms=expanded_terms,
    )


def select_strategy(profile: RequirementProfile, cfg: RetrievalConfig) -> str:
    """§456 Retrieval Strategy Selection. Default Hybrid."""
    if not profile.keywords:
        return "SemanticOnly"
    if profile.filters and not profile.normalized_query:
        return "MetadataOnly"
    return cfg.default_strategy


def build_metadata_filters(
    profile: RequirementProfile, cfg: RetrievalConfig
) -> dict[str, Any]:
    """SW-017 (§257/§457). Supported filters; executes before retrieval.

    §457 filters: Product, Module, Feature, Version, Authority, Language,
    Customer, Repository Status. Only 'Certified' repository objects are
    retrievable by default.
    """
    if not cfg.metadata_filtering:
        return {"repositoryStatus": "Certified"}

    filters: dict[str, Any] = {"repositoryStatus": "Certified"}
    if profile.product:
        filters["product"] = profile.product
    if profile.modules:
        filters["module"] = profile.modules
    if profile.language:
        filters["language"] = profile.language
    # carry forward derived / hinted filters (§454)
    for k in ("feature", "version", "authority", "customer"):
        if k in profile.filters:
            filters[k] = profile.filters[k]
    return filters


def _dedup_preserve(items: list[str]) -> list[str]:
    return list(dict.fromkeys(i for i in items if i))
