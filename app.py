from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from models import SurveySubmission, StoredSurveyRecord
from storage import append_json_line
import hashlib

app = Flask(__name__)
# Allow cross-origin requests so the static HTML can POST from localhost or file://
CORS(app, resources={r"/v1/*": {"origins": "*"}})

@app.route("/ping", methods=["GET"])
def ping():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "message": "API is alive",
        "utc_time": datetime.now(timezone.utc).isoformat()
    })

@app.post("/v1/survey")
def submit_survey():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "invalid_json", "detail": "Body must be application/json"}), 400

    try:
        submission = SurveySubmission(**payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": ve.errors()}), 422

    email_hash = hashlib.sha256(submission.email.encode()).hexdigest()
    age_hash = hashlib.sha256(str(submission.age).encode()).hexdigest()

    if submission.submission_id:
        submission_id = submission.submission_id
    else:
        dt_key = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        submission_id = hashlib.sha256((submission.email + dt_key).encode()).hexdigest()

    record = StoredSurveyRecord(
        **submission.dict(exclude={"email", "age", "submission_id", "user_agent"}),
        email=email_hash,
        age=age_hash,
        submission_id=submission_id,
        user_agent=request.headers.get("User-Agent"),
        received_at=datetime.now(timezone.utc),
        ip=request.headers.get("X-Forwarded-For", request.remote_addr or "")
    )
    append_json_line(record.dict())
    return jsonify({"status": "ok"}), 201

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
