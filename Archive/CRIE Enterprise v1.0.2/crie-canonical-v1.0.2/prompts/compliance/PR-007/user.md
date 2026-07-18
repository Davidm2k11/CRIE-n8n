<!-- PR-007 Executive Summary — user prompt template. Injected by SW-022 (§175). -->

Aggregate counts (fixed, platform-computed):
- Total requirements: {{totalRequirements}}
- Overall compliance %: {{overallCompliancePercent}}
- Fully Compliant: {{fullyCompliantCount}}
- Partially Compliant: {{partiallyCompliantCount}}
- Configurable: {{configurableCount}}
- Custom Development Required: {{customDevelopmentCount}}
- Not Supported: {{unsupportedCount}}
- Insufficient Evidence: {{insufficientEvidenceCount}}

Aggregated risks (from the per-requirement risk registers):
{{riskDigestJson}}

Produce a JSON object with:
- "keyRisks": array of short risk statements (most material first).
- "recommendedNextSteps": array of actionable next steps.

Return ONLY the JSON object.
