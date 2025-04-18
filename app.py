import os
import threading
import time
import uuid
import requests
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
import json

# Load environment variables (e.g., PIXELDRAIN_API_KEY)
load_dotenv()

app = Flask(__name__)

# Load Pixeldrain API key from environment variable
PIXELDRAIN_API_KEY = os.getenv("PIXELDRAIN_API_KEY")

# Path to the JSON file for job history
JOB_HISTORY_FILE = "jobs.json"

# Load job history from JSON file on startup
def load_jobs_from_file():
    if os.path.exists(JOB_HISTORY_FILE):
        with open(JOB_HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

# Save job history to JSON file
def save_jobs_to_file(jobs):
    with open(JOB_HISTORY_FILE, "w") as f:
        json.dump(jobs, f)

# Upload to Pixeldrain using API key (if available)
def upload_to_pixeldrain(url):
    headers = {}
    if PIXELDRAIN_API_KEY:
        headers["Authorization"] = f"Bearer {PIXELDRAIN_API_KEY}"
    
    response = requests.post(
        "https://pixeldrain.com/api/file/fetch",
        headers=headers,
        data={"url": url},
        timeout=600
    )
    result = response.json()
    if result.get("success"):
        return f"https://pixeldrain.com/u/{result['id']}"
    else:
        raise Exception(result)

# Background worker to process queued jobs
def job_worker():
    while True:
        with jobs_lock:
            pending_jobs = [job for job in jobs if job['status'] == 'pending']

        for job in pending_jobs:
            try:
                with jobs_lock:
                    job['status'] = 'uploading'

                link = upload_to_pixeldrain(job['url'])
                with jobs_lock:
                    job['status'] = 'complete'
                    job['result'] = link
            except Exception as e:
                with jobs_lock:
                    job['status'] = 'failed'
                    job['error'] = str(e)

        # Save the job history to the JSON file after every update
        save_jobs_to_file(jobs)

        time.sleep(3)  # Polling interval

# Start worker thread
threading.Thread(target=job_worker, daemon=True).start()

# Load job history into memory
jobs = load_jobs_from_file()
jobs_lock = threading.Lock()

# Home route to show the form and job history
@app.route('/', methods=['GET'])
def index():
    with jobs_lock:
        job_display = list(reversed(jobs))  # Newest first

    return render_template_string("""
    <h2>Multi URL Uploader to Pixeldrain</h2>
    <form method="POST" action="/submit">
        <textarea name="urls" rows="5" cols="60" placeholder="Paste one URL per line" required></textarea><br>
        <button type="submit">Upload</button>
    </form>
    <h3>Job History</h3>
    <ul>
        {% for job in jobs %}
            <li>
                <b>{{ job['url'] }}</b> - <i>{{ job['status'] }}</i>
                {% if job.get('result') %} ➜ <a href="{{ job['result'] }}" target="_blank">Download</a>{% endif %}
                {% if job.get('error') %} ⚠️ {{ job['error'] }}{% endif %}
            </li>
        {% endfor %}
    </ul>
    """, jobs=job_display)

# Submit route to add jobs to the queue
@app.route('/submit', methods=['POST'])
def submit():
    urls_text = request.form.get('urls')
    if not urls_text:
        return "No URLs provided", 400

    urls = [u.strip() for u in urls_text.strip().splitlines() if u.strip()]
    with jobs_lock:
        for url in urls:
            job_id = str(uuid.uuid4())
            jobs.append({
                "id": job_id,
                "url": url,
                "status": "pending",
                "result": None,
                "error": None
            })

    # Save the updated job history to the JSON file
    save_jobs_to_file(jobs)

    return f"Submitted {len(urls)} job(s). <a href='/'>Back</a>"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
