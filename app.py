"""Provenance Guard API.

Milestone 3 endpoints:
  POST /submit  - classify text, store it, return the structured result
  GET  /log     - recent audit-log entries (for documentation / grading visibility)

Rate limiting (M5), the stylometry signal + real confidence combine (M4), the
appeal endpoint and finalized labels (M5) are added in later milestones.
"""

import os
import uuid

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import db
import signals
import scoring

app = Flask(__name__)
db.init_db()

# Rate limiting on /submit. Limits reflect a real creator's pace and make flooding
# expensive (reasoning documented in the README). Disable for automated tests with
# PG_RATELIMIT_ENABLED=false.
SUBMIT_LIMITS = os.getenv("PG_SUBMIT_LIMITS", "2 per minute;10 per hour;50 per day")
app.config["RATELIMIT_ENABLED"] = (
    os.getenv("PG_RATELIMIT_ENABLED", "true").lower() != "false"
)
limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "error": "Rate limit exceeded. Please slow down and try again later.",
        "limit": str(e.description),
    }), 429


@app.route("/submit", methods=["POST"])
@limiter.limit(SUBMIT_LIMITS)
def submit():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    creator_id = data.get("creator_id")
    if not text or not creator_id:
        return jsonify({"error": "Both 'text' and 'creator_id' are required."}), 400

    content_id = str(uuid.uuid4())

    sig = signals.signal_llm(text)
    llm_score = sig["llm_score"]

    stylo = signals.signal_stylometry(text)
    stylo_score = stylo["stylo_score"]
    stylo_metrics = stylo.get("metrics", {})

    confidence = scoring.combine_confidence(llm_score, stylo_score)
    attribution = scoring.band(confidence)
    label = scoring.label_for(attribution)

    db.record_classification(
        content_id, creator_id, text, attribution,
        confidence, llm_score, stylo_score, label,
    )

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "signals": {"llm_score": llm_score, "stylo_score": stylo_score},
        "reason": sig["reason"],
        "label": label,
        "status": "classified",
        # Stretch (ensemble detection): expose each individual signal score behind the
        # combined confidence. The required "signals" field above is unchanged; this is additive.
        "ensemble_signals": {
            "llm": llm_score,
            "stylometry_variance": stylo_metrics.get("sub_var"),
            "stylometry_type_token_ratio": stylo_metrics.get("sub_ttr"),
            "stylometry_punctuation": stylo_metrics.get("sub_punc"),
        },
    })


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    creator_reasoning = data.get("creator_reasoning")
    evidence_url = data.get("evidence_url")  # optional supporting evidence

    if not content_id or not creator_reasoning:
        return jsonify(
            {"error": "Both 'content_id' and 'creator_reasoning' are required."}
        ), 400

    content = db.record_appeal(content_id, creator_reasoning, evidence_url)
    if content is None:
        return jsonify({"error": f"No content found with content_id '{content_id}'."}), 404

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": "Appeal received. The content is now under review.",
    })


@app.route("/log", methods=["GET"])
def log():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"entries": db.get_log(limit)})


# Stretch (analytics dashboard): read-only metrics view over the audit log.
@app.route("/analytics", methods=["GET"])
def analytics():
    return jsonify(db.get_analytics())


if __name__ == "__main__":
    app.run(port=5000, debug=True)
