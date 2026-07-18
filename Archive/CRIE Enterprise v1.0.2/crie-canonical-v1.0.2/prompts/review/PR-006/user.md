<!-- PR-006 Proposal Writing — user prompt template.
Variables injected by SW-022 (Prompt Loader) per §175. No hardcoded prompt text. -->

Requirement ID: {{requirementId}}
Requirement: {{requirement}}
Category: {{category}}
Compliance Level (fixed, platform-computed): {{complianceLevel}}
Confidence (fixed, platform-computed): {{confidence}}

Certified evidence (the ONLY permissible basis for claims):
{{supportingEvidenceJson}}

Supporting knowledge units:
{{supportingKnowledgeUnitsJson}}

Citations:
{{citationsJson}}

Produce a JSON object with:
- "response": proposal-ready answer text (§544/§545), grounded strictly in the evidence.
- "assumptions": array of explicit assumptions (may be empty).
- "limitations": array of stated limitations (may be empty).
- "gapAnalysis": array of {gapType, description} using only the three allowed gap types.
- "riskRegister": array of {risk, description, severity, likelihood, mitigation, owner}.

Return ONLY the JSON object.
