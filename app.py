import os
import json
import requests
import threading
import time
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Define API key and base URL for Pixeldrain
PIXELDRAIN_API_KEY = os.getenv("PIXELDRAIN_API_KEY")
PIXELDRAIN_UPLOAD_URL = "https://pixeldrain.com/api/file"

# Job storage (in-memory or persistent)
jobs_file = "jobs.json"

# Load job history from jobs.json
def load_jobs():
    if os.path.exists(jobs_file):
        with open(jobs_file, 'r') as file:
            return json.load(file)
    return []

# Save job history to jobs.json
def save_jobs(jobs):
    with open(jobs_file, 'w') as file:
        json.dump(jobs, file, indent=4)

# Function to upload a file to Pixeldrain
def upload_file_to_pixeldrain(job_id, url):
    try:
        response = requests.get(url, stream=True)
        file_name = url.split("/")[-1]
        
        headers = {
            "Authorization": f"Bearer {PIXELDRAIN_API_KEY}"
        }
        progress = 0
        total_size = int(response.headers.get('content-length', 0))

        with open(f"temp_{job_id}_{file_name}", 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
                    progress += len(chunk)
                    # Update job progress in the job history
                    update_job_progress(job_id, int((progress / total_size) * 100))

        # Upload the file to Pixeldrain after downloading
        with open(f"temp_{job_id}_{file_name}", 'rb') as file:
            upload_response = requests.post(PIXELDRAIN_UPLOAD_URL, headers=headers, files={'file': file})
            if upload_response.status_code == 200:
                job_result = upload_response.json()
                job_url = job_result.get('link')
                update_job_result(job_id, job_url)
                os.remove(f"temp_{job_id}_{file_name}")
            else:
                update_job_error(job_id, "Upload failed.")
    except Exception as e:
        update_job_error(job_id, str(e))

# Update job status in history
def update_job_status(job_id, status):
    jobs = load_jobs()
    for job in jobs:
        if job['id'] == job_id:
            job['status'] = status
            save_jobs(jobs)
            break

# Update job progress in history
def update_job_progress(job_id, progress):
    jobs = load_jobs()
    for job in jobs:
        if job['id'] == job_id:
            job['progress'] = progress
            save_jobs(jobs)
            break

# Update job result in history
def update_job_result(job_id, result):
    jobs = load_jobs()
    for job in jobs:
        if job['id'] == job_id:
            job['result'] = result
            job['status'] = 'completed'
            save_jobs(jobs)
            break

# Update job error in history
def update_job_error(job_id, error):
    jobs = load_jobs()
    for job in jobs:
        if job['id'] == job_id:
            job['error'] = error
            job['status'] = 'failed'
            save_jobs(jobs)
            break

# Flask route for home page
@app.route('/')
def index():
    jobs = load_jobs()
    return render_template('index.html', jobs=jobs)

# Flask route to submit new jobs
@app.route('/submit', methods=['POST'])
def submit():
    urls = request.form['urls'].splitlines()
    jobs = load_jobs()

    # Add job entries and start processing
    for url in urls:
        job_id = str(len(jobs) + 1)
        job = {
            'id': job_id,
            'url': url,
            'status': 'queued',
            'progress': 0,
            'result': None,
            'error': None
        }
        jobs.append(job)
        save_jobs(jobs)

        # Start a background thread for each upload
        threading.Thread(target=upload_file_to_pixeldrain, args=(job_id, url)).start()

    return render_template('index.html', jobs=jobs)

# Flask route to get the status of a job
@app.route('/job_status/<job_id>')
def job_status(job_id):
    jobs = load_jobs()
    job = next((job for job in jobs if job['id'] == job_id), None)
    if job:
        return jsonify({
            'status': job['status'],
            'progress': job.get('progress', 0)
        })
    return jsonify({'status': 'not found', 'progress': 0})

# Run Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
