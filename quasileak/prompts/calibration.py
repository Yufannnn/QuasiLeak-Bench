"""Shared confidence calibration for construction probes."""

CONFIDENCE_CALIBRATION = "CONFIDENCE SCALE (shared by every judge -- singleton, pair, and joint): confidence is P(cold-attacker top-1 == truth | the evidence), calibrated to the decision threshold T:\n- >= T: the evidence makes the truth the clear top-1 (pins / reveals it).\n- between the attribute's base rate and T: the truth is plausible but strong alternatives remain.\n- near the base rate (~0.5 for a binary attribute): little or no signal -- chance, not evidence."
