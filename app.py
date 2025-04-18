import os
import json
import threading
import requests
from flask import Flask, render_template, request, redirect, url_for
from urllib.parse import urlparse
from time import time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

JOBS_FILE = "jobs.json"
UPLOAD_URL = "https://pixeldrain.com/api/file"

jobs_lock = threading.Lock()
active_jobs = []

# Load jobs from file
def load_jobs():
    if not os.path.exists(JOBS_FILE):
        return []
    with open(JOBS_FILE, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []

# Save jobs to file
def save_jobs(jobs):
    with open(JOBS_FILE, "w") as file:
        json.dump(jobs, file, indent=4)

# Background worker
def job_worker():
    while True:
        if active_jobs:
            job = active_jobs.pop(0)
            url = job["url"]
            filename = urlparse(url).path.split("/")[-1] or "file"

            try:
                start = time()
                with requests.get(url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    total = int(r.headers.get("Content-Length", 0))
                    uploaded = 0

                    with requests.Session() as s:
                        with s.post(UPLOAD_URL, files={"file": (filename, r.raw)}) as upload_response:
                            upload_response.raise_for_status()
                            res_json = upload_response.json()
                            job["status"] = "success ✅"
                            job["link"] = f"https://pixeldrain.com/u/{res_json['id']}"

                duration = time() - start
                job["eta"] = f"{int(duration)}s"

            except Exception as e:
                job["status"] = f"failed ⚠️ {str(e)}"
                job["link"] = ""

            with jobs_lock:
                jobs = load_jobs()
                jobs.insert(0, job)
                save_jobs(jobs)

# Start background thread
threading.Thread(target=job_worker, daemon=True).start()

@app.route("/", methods=["GET"])
def index():
    with jobs_lock:
        jobs = load_jobs()
    return render_template("index.html", jobs=jobs)

@app.route("/submit", methods=["POST"])
def submit():
    url = request.form.get("url")
    if url:
        job = {
            "url": url,
            "status": "pending ⏳",
            "link": "",
            "eta": ""
        }
        active_jobs.append(job)
    return redirect(url_for("index"))

@app.route("/reset", methods=["POST"])
def reset():
    with jobs_lock:
        save_jobs([])
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
