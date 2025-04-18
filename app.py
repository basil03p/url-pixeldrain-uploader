import os
import json
import threading
import time
from flask import Flask, render_template, request
import requests

app = Flask(__name__)

# Lock to handle concurrent access to jobs
jobs_lock = threading.Lock()

# File where job history is stored
JOBS_FILE = "jobs.json"

def load_jobs():
    """Load the job history from the JSON file."""
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []
    else:
        return []

def save_jobs(jobs):
    """Save the job history to the JSON file."""
    with open(JOBS_FILE, "w") as file:
        json.dump(jobs, file, indent=4)

@app.route("/", methods=["GET"])
def index():
    """Render the job history page."""
    jobs = load_jobs()
    return render_template("index.html", jobs=jobs)

@app.route("/submit", methods=["POST"])
def submit():
    """Submit a new upload job."""
    url = request.form["url"]
    job = {
        "url": url,
        "status": "Uploading",
        "progress": 0
    }

    # Load current jobs and append the new job
    with jobs_lock:
        jobs = load_jobs()
        jobs.append(job)
        save_jobs(jobs)

    # Start the upload in a separate thread
    threading.Thread(target=upload_file, args=(job,)).start()

    return render_template("index.html", jobs=jobs)

def upload_file(job):
    """Simulate the file upload process."""
    url = job["url"]
    job["status"] = "Uploading"
    
    # Simulate a file upload and update progress
    total_file_size = 1000  # Example: 1000 bytes total file size (you'll need to get real file size in a real scenario)
    uploaded_size = 0

    try:
        while uploaded_size < total_file_size:
            time.sleep(1)  # Simulate time taken for uploading a chunk
            uploaded_size += 100  # Simulate uploading 100 bytes at a time
            
            # Calculate progress as a percentage
            if total_file_size > 0:
                job["progress"] = (uploaded_size / total_file_size) * 100
            else:
                job["progress"] = 0

            # Update job status if completed
            if uploaded_size >= total_file_size:
                job["status"] = "Completed"
                job["progress"] = 100

            # Save job history to file
            with jobs_lock:
                jobs = load_jobs()
                for saved_job in jobs:
                    if saved_job["url"] == job["url"]:
                        saved_job["status"] = job["status"]
                        saved_job["progress"] = job["progress"]
                save_jobs(jobs)
                
    except Exception as e:
        job["status"] = f"Failed: {str(e)}"
        job["progress"] = 0
        with jobs_lock:
            jobs = load_jobs()
            for saved_job in jobs:
                if saved_job["url"] == job["url"]:
                    saved_job["status"] = job["status"]
                    saved_job["progress"] = job["progress"]
            save_jobs(jobs)

@app.route("/clear", methods=["POST"])
def clear_jobs():
    """Clear the job history."""
    with jobs_lock:
        save_jobs([])
    return render_template("index.html", jobs=[])

if __name__ == "__main__":
    # Ensure that the jobs.json file exists
    if not os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, "w") as file:
            json.dump([], file)

    app.run(host="0.0.0.0", port=10000, debug=True)
