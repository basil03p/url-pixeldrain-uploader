import os
import time
import threading
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for
from mailjet_rest import Client
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_default_secret_key')

# Mailjet API setup
api_key = os.getenv('MAILJET_API_KEY')
api_secret = os.getenv('MAILJET_API_SECRET')
mj = Client(auth=(api_key, api_secret), version='v3.1')

# Download history
download_history = []

# Email sender
SENDER_EMAIL = os.getenv('SENDER_EMAIL', 'you@yourdomain.com')
SENDER_NAME = os.getenv('SENDER_NAME', 'Cloud Downloader')

# Send email via Mailjet
def send_email(subject, message, recipient_email):
    data = {
        'Messages': [
            {
                "From": {
                    "Email": SENDER_EMAIL,
                    "Name": SENDER_NAME
                },
                "To": [{"Email": recipient_email}],
                "Subject": subject,
                "TextPart": message,
                "HTMLPart": f"<h3>{message}</h3>"
            }
        ]
    }
    try:
        result = mj.send.create(data=data)
        return result.status_code, result.json()
    except Exception as e:
        print(f"Email sending failed: {e}")
        return 500, {'error': str(e)}

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

                        if eta > 6000:
                            send_email(
                                "⚠️ Long Download Alert",
                                f"Your download of '{file_name}' is taking too long (ETA: {int(eta // 60)} min).",
                                email
                            )

        download_history.append({'url': url, 'status': 'success', 'file': file_name})
        send_email("✅ Download Complete", f"Your download of '{file_name}' has completed.", email)

    except Exception as e:
        error_msg = str(e)
        download_history.append({'url': url, 'status': 'failed', 'error': error_msg})
        send_email("❌ Download Failed", f"Failed to download from {url}\nError: {error_msg}", email)

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
