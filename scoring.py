"""Confidence bands and labels.

`confidence` is the system's probability the content is AI-generated (0..1).
Thresholds match planning.md (asymmetric, biased against false positives):
  < 0.35       likely_human
  0.35 - 0.70  uncertain
  > 0.70       likely_ai

`confidence` is the weighted combine of the two signals (see scoring.combine_confidence),
and each band maps to one finalized transparency label below.
"""

HUMAN_MAX = 0.35   # confidence < HUMAN_MAX -> likely_human
AI_MIN = 0.70      # confidence > AI_MIN   -> likely_ai

W_LLM = 0.7        # weighted average: trust the holistic signal more
W_STYLO = 0.3


def combine_confidence(llm_score, stylo_score):
    """Combine the two signals into the AI-likelihood confidence (0..1)."""
    return round(W_LLM * llm_score + W_STYLO * stylo_score, 4)

# Finalized transparency-label text (verbatim from planning.md, Transparency Labels).
_LABELS = {
    "likely_ai": (
        "🤖 Likely AI-generated. Our analysis suggests this text was probably produced "
        "with significant help from an AI writing tool. This is an automated estimate, "
        "not a certainty. If you wrote it yourself, you can appeal."
    ),
    "uncertain": (
        "❓ Inconclusive. Human writing like an AI, or AI writing like a human? "
        "You've got us, no verdict on this one."
    ),
    "likely_human": (
        "✍️ Likely human-written. Our analysis found no strong signs of AI generation "
        "in this text."
    ),
}


def band(confidence):
    """Map a confidence score to an attribution band."""
    if confidence < HUMAN_MAX:
        return "likely_human"
    if confidence > AI_MIN:
        return "likely_ai"
    return "uncertain"


def label_for(attribution):
    return _LABELS[attribution]
