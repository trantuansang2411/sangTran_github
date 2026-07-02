from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from test_assistant import ask_question
import markdown

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    question = data.get("message", "")
    
    if not question:
        return jsonify({"error": "Empty message"}), 400
        
    try:
        # Get raw markdown answer from the assistant
        raw_answer = ask_question(question)
        
        # Convert markdown to HTML for easier rendering in frontend
        html_answer = markdown.markdown(raw_answer, extensions=['fenced_code', 'nl2br'])
        
        return jsonify({
            "answer": html_answer,
            "raw": raw_answer
        })
    except Exception as e:
        print(f"Error processing chat: {e}")
        return jsonify({"error": "An error occurred while processing your request."}), 500

if __name__ == "__main__":
    print("Starting OptiBot Web UI on http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
