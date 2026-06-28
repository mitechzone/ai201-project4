"""Confidence bands and labels.

`confidence` is the system's probability the content is AI-generated (0..1).
Thresholds match planning.md (asymmetric, biased against false positives):
  < 0.35       likely_human
  0.35 - 0.70  uncertain
  > 0.70       likely_ai

Milestone 3 note: confidence is provisional here (the LLM score alone). The weighted
combine with stylometry arrives in M4, and the finalized transparency-label text in M5.
"""

HUMAN_MAX = 0.35   # confidence < HUMAN_MAX -> likely_human
AI_MIN = 0.70      # confidence > AI_MIN   -> likely_ai

# Provisional labels for M3 so /submit returns something readable.
# Replaced by the finalized transparency-label text in M5.
_PROVISIONAL_LABELS = {
    "likely_human": "Likely human-written (provisional label)",
    "uncertain": "Inconclusive (provisional label)",
    "likely_ai": "Likely AI-generated (provisional label)",
}


def band(confidence):
    """Map a confidence score to an attribution band."""
    if confidence < HUMAN_MAX:
        return "likely_human"
    if confidence > AI_MIN:
        return "likely_ai"
    return "uncertain"


def label_for(attribution):
    return _PROVISIONAL_LABELS[attribution]
