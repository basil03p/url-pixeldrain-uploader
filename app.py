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
app.secret_key = 'your_secret_key'  # Replace with a secret key of your choice

# Mailjet API setup
api_key = os.getenv('MAILJET_API_KEY')  # Replace with your Mailjet API Key in .env file
api_secret = os.getenv('MAILJET_API_SECRET')  # Replace with your Mailjet API Secret in .env file
mj = Client(auth=(api_key, api_secret), version='v3.1')

# Global download history to keep track of download status and errors
download_history = []

# Function to send email notification via Mailjet
def send_email(subject, message, recipient_email):
    data = {
        'Messages': [
            {
                "From": {
                    "Email": "you@yourdomain.com",  # Replace with your sender email
                    "Name": "Your Name"
                },
                "To": [
                    {
                        "Email": recipient_email,
                        "Name": "Recipient"
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

# Function to download the file
def download_file(url, file_name, email):
    try:
        # Download the file
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('Content-Length', 0))
        downloaded_size = 0
        start_time = time.time()

        with open(file_name, 'wb') as file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
                    downloaded_size += len(chunk)

                    # Calculate download progress
                    progress = (downloaded_size / total_size) * 100
                    elapsed_time = time.time() - start_time
                    estimated_time = (total_size - downloaded_size) / (downloaded_size / elapsed_time) if downloaded_size > 0 else 0

                    # Notify progress
                    print(f"Downloading... {int(progress)}% ETA: {int(estimated_time // 60)} min")

                    # Notify user if download is taking too long
                    if estimated_time > 6000 and email:
                        send_email("Long Download Alert", f"Your download of {file_name} is taking too long. ETA: {int(estimated_time // 60)} minutes.", email)

        # Successful download
        download_history.append({'url': url, 'status': 'success', 'file': file_name})
        print(f"Download completed: {file_name}")
        send_email("Download Complete", f"Your download of {file_name} has completed.", email)
    except Exception as e:
        # On error, notify user
        download_history.append({'url': url, 'status': 'failed', 'error': str(e)})
        send_email("Download Failed", f"An error occurred while downloading {file_name}: {str(e)}", email)
        print(f"Download failed: {e}")

# Home page route
@app.route('/')
def index():
    return render_template('index.html', download_history=download_history)

# Handle file download submission
@app.route('/submit', methods=['POST'])
def submit():
    url = request.form['url']
    email = request.form['email']

    if not url or not email:
        return jsonify({'error': 'URL and email are required.'}), 400

    # Create a unique file name based on the URL and timestamp
    file_name = f"download_{int(time.time())}.mp4"
    
    # Start the download in a separate thread
    thread = threading.Thread(target=download_file, args=(url, file_name, email))
    thread.start()

    return redirect(url_for('index'))

# Reset the job history
@app.route('/reset', methods=['POST'])
def reset():
    global download_history
    download_history = []
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
