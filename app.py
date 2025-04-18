import os
import threading
import json
import uuid
import requests
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
JOBS_FILE = "jobs.json"
UPLOAD_API = "https://api.pixeldrain.com/upload"

# Ensure jobs.json exists and is valid
if not os.path.exists(JOBS_FILE) or os.stat(JOBS_FILE).st_size == 0:
    with open(JOBS_FILE, "w") as f:
        json.dump([], f)

jobs_lock = threading.Lock()

def load_jobs():
    with open(JOBS_FILE, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []

def save_jobs(jobs):
    with open(JOBS_FILE, "w") as file:
        json.dump(jobs, file, indent=4)

def add_job(job):
    with jobs_lock:
        jobs = load_jobs()
        jobs.append(job)
        save_jobs(jobs)

def update_job(job_id, updates):
    with jobs_lock:
        jobs = load_jobs()
        for job in jobs:
            if job["id"] == job_id:
                job.update(updates)
                break
        save_jobs(jobs)

def reset_jobs():
    with jobs_lock:
        save_jobs([])

def download_file(url, temp_file_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        total_length = r.headers.get('content-length')
        if total_length is None:
            with open(temp_file_path, 'wb') as f:
                f.write(r.content)
            return
        total_length = int(total_length)
        downloaded = 0
        with open(temp_file_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    percent = int((downloaded / total_length) * 100)
                    print(f"Downloading... {percent}%")

def upload_to_pixeldrain(file_path):
    with open(file_path, 'rb') as f:
        response = requests.put(UPLOAD_API, files={"file": f})
        response.raise_for_status()
        return response.json().get("id")

def job_worker(job_id, url):
    temp_file = f"temp_{uuid.uuid4().hex}.bin"
    try:
        update_job(job_id, {"status": "downloading ⬇️"})
        download_file(url, temp_file)

        update_job(job_id, {"status": "uploading ⬆️"})
        file_id = upload_to_pixeldrain(temp_file)

        link = f"https://pixeldrain.com/u/{file_id}"
        update_job(job_id, {"status": "completed ✅", "link": link})
    except Exception as e:
        update_job(job_id, {"status": f"failed ⚠️ {str(e)}"})
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

@app.route("/", methods=["GET"])
def index():
    jobs = load_jobs()
    return render_template("index.html", jobs=jobs)

@app.route("/submit", methods=["POST"])
def submit():
    url = request.form["url"]
    job_id = uuid.uuid4().hex
    job = {"id": job_id, "url": url, "status": "queued 🕒", "link": ""}
    add_job(job)
    threading.Thread(target=job_worker, args=(job_id, url)).start()
    return redirect(url_for("index"))

@app.route("/reset", methods=["POST"])
def reset():
    reset_jobs()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
