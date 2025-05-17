from flask import Flask, render_template_string, request, Response
import datetime
import pytz
import scripts.stock_in_excel as stock_processor
import sys
from contextlib import contextmanager
import os
import json
from functools import wraps

app = Flask(__name__)

# Initialize last run time as None
last_run_time = None

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Get scheduler token from environment variable
SCHEDULER_TOKEN = os.environ.get('SCHEDULER_TOKEN', 'your-secret-token')

def require_scheduler_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('X-Scheduler-Token')
        if token != SCHEDULER_TOKEN:
            return Response('Unauthorized', status=401)
        return f(*args, **kwargs)
    return decorated_function

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
        .schedule-info {
            margin-top: 20px;
            padding: 15px;
            background-color: #e8f4f8;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>🛠️ Frono Automation Service</h2>
        <p>Welcome! This Cloud Run service powers the automated stock in/out process for FronoCloud reports.</p>
        
        <div class="nav-links">
            <a href="/status">✅ Status</a>
        </div>

        <div class="schedule-info">
            <h3>📅 Schedule Information</h3>
            <p>The stock process runs automatically every day at 11:00 PM IST.</p>
            <p>Last run status and logs are displayed below.</p>
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

@app.route("/scheduled", methods=["POST"])
@require_scheduler_token
def scheduled_run():
    """Endpoint for scheduled runs"""
    global last_run_time
    
    with capture_logs() as logs:
        try:
            # Run the stock process
            stock_processor.stockInItem("kolkata")
            last_run_time = datetime.datetime.now(pytz.utc)
            logs.append("✅ Scheduled stock process completed successfully")
            
            # Save logs to file
            log_file = save_logs_to_file(logs, "kolkata")
            
            return {
                "status": "success",
                "message": "Stock process completed successfully",
                "log_file": log_file,
                "timestamp": last_run_time.isoformat()
            }, 200
            
        except Exception as e:
            error_msg = f"❌ Error in scheduled run: {str(e)}"
            logs.append(error_msg)
            log_file = save_logs_to_file(logs, "kolkata")
            
            return {
                "status": "error",
                "message": error_msg,
                "log_file": log_file,
                "timestamp": datetime.datetime.now(pytz.utc).isoformat()
            }, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
