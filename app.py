import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify
from agents.assessment_agent import AssessmentAgent


app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    asmt_agent = AssessmentAgent()
    assessment = asmt_agent.generate_assessment(
        os.environ.get("LECTURE_PDF_PATH"),
        {"type": "MCQ", "difficulty": "Medium", "count": 5, "rubric": True}
    )
    # If assessment is not JSON-serializable, convert to dict:
    # assessment = assessment.to_dict()  # if applicable
    return jsonify(assessment)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
