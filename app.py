from flask import Flask, render_template_string
import datetime
import pytz
import scripts.stock_in_excel as stock_processor
import sys
from contextlib import contextmanager
import os
import json

app = Flask(__name__)

# Initialize last run time as None
last_run_time = None

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

def save_logs_to_file(logs, location):
    """Save logs to a JSON file with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{LOGS_DIR}/stock_process_{location}_{timestamp}.json"
    
    log_data = {
        "timestamp": datetime.datetime.now(pytz.utc).isoformat(),
        "location": location,
        "logs": logs
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    return filename

@contextmanager
def capture_logs():
    """Context manager to capture logs for a single request"""
    logs = []
    
    class LogCapture:
        def write(self, message):
            if message.strip():  # Only store non-empty messages
                logs.append(message.strip())
        
        def flush(self):
            pass
    
    # Redirect stdout to our custom handler
    original_stdout = sys.stdout
    log_capture = LogCapture()
    sys.stdout = log_capture
    
    try:
        yield logs
    finally:
        # Restore original stdout
        sys.stdout = original_stdout

# HTML template for the page
PAGE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Frono Automation Service</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h2 { color: #2c3e50; }
        .nav-links {
            margin: 20px 0;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
        }
        .nav-links a {
            display: inline-block;
            margin-right: 20px;
            color: #3498db;
            text-decoration: none;
        }
        .nav-links a:hover {
            text-decoration: underline;
        }
        .log-container {
            margin-top: 20px;
            padding: 15px;
            background-color: #2c3e50;
            color: #ecf0f1;
            border-radius: 4px;
            font-family: monospace;
            white-space: pre-wrap;
            max-height: 500px;
            overflow-y: auto;
        }
        .success { color: #2ecc71; }
        .error { color: #e74c3c; }
        .info { color: #3498db; }
        .log-file {
            margin-top: 10px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 4px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>🛠️ Frono Automation Service</h2>
        <p>Welcome! This Cloud Run service powers the automated stock in/out process for FronoCloud reports.</p>
        
        <div class="nav-links">
            <a href="/status">✅ Status</a>
            <a href="/stock">📦 Stock In/Out</a>
        </div>

        <hr>
        <p><b>🕒 Last Run (IST):</b> {{ last_run }}</p>

        {% if logs %}
        <div class="log-container">
            {% for log in logs %}
                {% if '❌' in log %}
                    <div class="error">{{ log }}</div>
                {% elif '✅' in log %}
                    <div class="success">{{ log }}</div>
                {% else %}
                    <div class="info">{{ log }}</div>
                {% endif %}
            {% endfor %}
        </div>
        {% if log_file %}
        <div class="log-file">
            📝 Logs saved to: {{ log_file }}
        </div>
        {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def home():
    global last_run_time
    if last_run_time:
        ist_time = last_run_time.astimezone(IST)
        last_run = ist_time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        last_run = "No runs yet"

    return render_template_string(PAGE_TEMPLATE, last_run=last_run, logs=[])

@app.route("/status", methods=["GET"])
def health_check():
    return "✅ Service is healthy", 200

@app.route("/stock", methods=["GET"])
def run_stock_process():
    global last_run_time
    
    with capture_logs() as logs:
        try:
            # Run the stock process
            stock_processor.stockInItem("kolkata")
            last_run_time = datetime.datetime.now(pytz.utc)
            logs.append("✅ Stock process completed successfully")
        except Exception as e:
            logs.append(f"❌ Error: {str(e)}")
        
        # Save logs to file
        log_file = save_logs_to_file(logs, "kolkata")
    
    return render_template_string(PAGE_TEMPLATE,
                                last_run=last_run_time.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S") if last_run_time else "No runs yet",
                                logs=logs,
                                log_file=log_file)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
