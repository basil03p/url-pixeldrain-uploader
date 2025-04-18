import os
import time
import threading
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from mailjet_rest import Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure secret

# Mailjet API setup
api_key = os.getenv('MAILJET_API_KEY')
api_secret = os.getenv('MAILJET_API_SECRET')
mj = Client(auth=(api_key, api_secret), version='v3.1')

# Global download history
download_history = []

# Function to send email notification via Mailjet
def send_email(subject, message, recipient_email):
    data = {
        'Messages': [
            {
                "From": {
                    "Email": "you@yourdomain.com",  # Replace with a real email
                    "Name": "Your App"
                },
                "To": [
                    {
                        "Email": recipient_email,
                        "Name": "User"
                    }
                ],
                "Subject": subject,
                "TextPart": message,
                "HTMLPart": f"<h3>{message}</h3>"
            }
        ]
    }
    result = mj.send.create(data=data)
    return result.status_code, result.json()

# Function to download file in a thread
def download_file(url, file_name, email):
    try:
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('Content-Length', 0))
        downloaded_size = 0
        start_time = time.time()

        with open(file_name, 'wb') as file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
                    downloaded_size += len(chunk)

                    # Progress tracking
                    progress = (downloaded_size / total_size) * 100
                    elapsed_time = time.time() - start_time
                    estimated_time = (total_size - downloaded_size) / (downloaded_size / elapsed_time) if downloaded_size else 0

                    # Notify on very long downloads
                    if estimated_time > 6000 and email:
                        send_email("Long Download Alert", f"Download of {file_name} is taking too long. ETA: {int(estimated_time // 60)} minutes.", email)

        # Success
        download_history.append({'url': url, 'status': 'success', 'file': file_name})
        send_email("Download Complete", f"Your download of {file_name} has completed.", email)
    except Exception as e:
        # Failure
        download_history.append({'url': url, 'status': 'failed', 'error': str(e)})
        send_email("Download Failed", f"Error while downloading {file_name}: {str(e)}", email)

# Routes
@app.route('/')
def index():
    return render_template('index.html', download_history=download_history)

@app.route('/submit', methods=['POST'])
def submit():
    url = request.form['url']
    email = request.form['email']
    if not url or not email:
        return jsonify({'error': 'URL and email are required.'}), 400

    file_name = f"download_{int(time.time())}.mp4"
    thread = threading.Thread(target=download_file, args=(url, file_name, email))
    thread.start()
    return redirect(url_for('index'))

@app.route('/reset', methods=['POST'])
def reset():
    global download_history
    download_history = []
    return redirect(url_for('index'))

# Run the app on Render
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
