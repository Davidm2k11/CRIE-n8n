"""
Review States + Reviewer Workflow (S7-8).
All Rights Reserved, Copyright (c) 2026 Dawod Manasra.

Authoritative: §106 (Reviewer Workflow), §107 (Review States), §551 (Human Review
Workflow). Rejected responses return to the Enterprise Reasoning Engine WF-003
(§106/§551). This module is pure state logic; the actual re-queue to WF-003 is
performed by the orchestrator in the target deployment.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# §107 supported values (superset) + §551 'Assigned' stage.
STATES = [
    "Pending", "Assigned", "In Review", "Approved",
    "Rejected", "Needs Clarification", "Archived",
]

# Allowed transitions (§106 + §551). Rejected -> (route to WF-003) is modeled as a
# terminal state for the review workflow; regeneration produces a new result.
_TRANSITIONS: Dict[str, List[str]] = {
    "Pending": ["Assigned", "In Review", "Archived"],
    "Assigned": ["In Review", "Pending", "Archived"],
    "In Review": ["Approved", "Rejected", "Needs Clarification", "Archived"],
    "Needs Clarification": ["In Review", "Rejected", "Archived"],
    "Approved": ["Archived"],          # Approved -> Published handled by export gate
    "Rejected": ["Archived"],          # returns to WF-003 for regeneration
    "Archived": [],
}

PUBLISH_REQUIRES = "Approved"          # §551: only Approved may be published


class ReviewError(ValueError):
    """Raised on an illegal review-state transition."""


def can_transition(current: str, target: str) -> bool:
    if current not in _TRANSITIONS:
        raise ReviewError(f"unknown state '{current}'")
    if target not in STATES:
        raise ReviewError(f"unknown target state '{target}'")
    return target in _TRANSITIONS[current]


def transition(current: str, target: str) -> str:
    if not can_transition(current, target):
        raise ReviewError(f"illegal transition {current} -> {target} (§106/§551)")
    return target


def route_on_reject(result: Dict) -> Dict:
    """
    §106/§551: a rejected response returns to the Enterprise Reasoning Engine.
    Returns a routing directive; does not mutate the result (§99).
    """
    return {
        "action": "return-to-reasoning",
        "target": "WF-003",
        "requirementId": result.get("requirementId"),
    }


def can_publish(state: str) -> bool:
    return state == PUBLISH_REQUIRES


def apply_review(result: Dict, target_state: str,
                 reviewer: Optional[str] = None,
                 comment: Optional[str] = None) -> Dict:
    """
    Return a NEW result copy with an updated 'review' block (does not mutate input).
    Reviewer comments are preserved (§99).
    """
    current = (result.get("review") or {}).get("status", "Pending")
    new_state = transition(current, target_state)
    updated = dict(result)
    review = dict(result.get("review") or {})
    review["status"] = new_state
    if reviewer is not None:
        review["reviewer"] = reviewer
    if comment is not None:
        comments = list(review.get("comments") or [])
        comments.append(comment)
        review["comments"] = comments
    updated["review"] = review
    return updated
