import os
import time
import threading
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_default_secret_key')

# Gofile API setup
GOFILE_API_KEY = os.getenv('GOFILE_API_KEY')  # Your Gofile API Key from .env file

# Download history
download_history = []

# Upload file to Gofile
def upload_to_gofile(file_path):
    url = 'https://api.gofile.io/uploadFile'
    headers = {
        'Authorization': f'Bearer {GOFILE_API_KEY}',
    }
    files = {'file': open(file_path, 'rb')}
    response = requests.post(url, headers=headers, files=files)
    
    if response.status_code == 200:
        response_data = response.json()
        if response_data['status'] == 'ok':
            return response_data['data']['downloadPage']
    return None

# Download handler
def download_file(url, file_name, email):
    try:
        response = requests.get(url, stream=True, timeout=10)
        total_size = int(response.headers.get('Content-Length', 0))
        downloaded = 0
        start_time = time.time()

        with open(file_name, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    elapsed = time.time() - start_time
                    if downloaded > 0:
                        speed = downloaded / elapsed
                        eta = (total_size - downloaded) / speed if speed > 0 else 0

        # Upload the file to Gofile after download
        download_link = upload_to_gofile(file_name)
        if download_link:
            download_history.append({
                'url': url,
                'status': 'success',
                'file': file_name,
                'gofile_link': download_link
            })
            print(f"Download completed: {file_name}")
        else:
            download_history.append({
                'url': url,
                'status': 'failed',
                'error': 'Failed to upload to Gofile'
            })

    except Exception as e:
        error_msg = str(e)
        download_history.append({'url': url, 'status': 'failed', 'error': error_msg})

# Routes
@app.route('/')
def index():
    return render_template('index.html', download_history=download_history)

@app.route('/submit', methods=['POST'])
def submit():
    url = request.form.get('url')
    email = request.form.get('email')

    if not url or not email:
        return jsonify({'error': 'URL and email are required.'}), 400

    file_name = f"download_{int(time.time())}.file"
    thread = threading.Thread(target=download_file, args=(url, file_name, email))
    thread.start()

    return redirect(url_for('index'))

@app.route('/reset', methods=['POST'])
def reset():
    download_history.clear()
    return redirect(url_for('index'))

# Entry
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Required for Render
    app.run(host='0.0.0.0', port=port, debug=True)
