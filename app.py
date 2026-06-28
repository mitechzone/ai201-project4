"""Provenance Guard API.

Milestone 3 endpoints:
  POST /submit  - classify text, store it, return the structured result
  GET  /log     - recent audit-log entries (for documentation / grading visibility)

Rate limiting (M5), the stylometry signal + real confidence combine (M4), the
appeal endpoint and finalized labels (M5) are added in later milestones.
"""

import uuid

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify

import db
import signals
import scoring

app = Flask(__name__)
db.init_db()


@app.route("/submit", methods=["POST"])
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
    })


@app.route("/log", methods=["GET"])
def log():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"entries": db.get_log(limit)})


if __name__ == "__main__":
    app.run(port=5000, debug=True)
