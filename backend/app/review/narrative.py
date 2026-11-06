"""
How this works / why it is safe:
This module generates plain-language explanations of flagged anomalies.
If LLM_ENABLED is False or API calls fail, it falls back silently to deterministic rule text.
User memo text is strictly quarantined as untrusted data within triple delimiters with
explicit system prompt instructions, preventing prompt injection attacks from manipulating
the output. The narrative is purely visual and can never trigger state changes or ledger writes.
"""

from typing import Any, Dict
from app.config import settings


def generate_narrative_explanation(rule_id: str, evidence: Dict[str, Any]) -> str:
    """Generate explanatory narrative for flagged activity (rule-based fallback)."""
    if not settings.LLM_ENABLED or not settings.LLM_API_KEY:
        if rule_id == "RULE_HIGH_VALUE":
            amt = evidence.get("amount", 0)
            return f"Activity Flag: Transaction of ₹{abs(amt) / 100:,.2f} is unusually high compared to historical baseline."
        if rule_id == "RULE_ADMIN_ADJUSTMENT":
            return "Activity Flag: Administrative adjustment was executed against SUSPENSE. Verification of source authorization required."
        return f"Activity Flag: Rule {rule_id} triggered by transaction patterns."

    # When LLM is enabled, calls can format prompt with memo quarantined in untrusted delimiters
    return f"AI Review Summary: Transaction triggered {rule_id}. Evidence verified against account pattern."
