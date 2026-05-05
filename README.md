# 🔐 SecureVault — Face Recognition Document Vault

A Python Flask web application that uses **facial recognition** to control access to a secure document vault. Users register their face via webcam, then authenticate using only their face — no passwords required.

## Features

- **Face Registration** — Capture your face via webcam to create a biometric identity
- **Face Authentication** — Log in using facial recognition with confidence scoring
- **Document Vault** — Upload, view, download, and delete confidential files
- **Access Logs** — Track all authentication attempts (granted/denied) with timestamps
- **Per-User Isolation** — Each user has their own isolated file storage directory

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend   | Python 3 + Flask |
| Face AI   | DeepFace (FaceNet model) |
| Vision    | OpenCV |
| Frontend  | HTML, CSS, Vanilla JavaScript |
| Camera    | WebRTC (getUserMedia API) |

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
│   Browser    │────▶│   Flask App      │────▶│  DeepFace      │
│  (Webcam)    │     │   (app.py)       │     │  (face_utils)  │
│  HTML/JS/CSS │◀────│   Routes + API   │◀────│  FaceNet Model │
└──────────────┘     └──────────────────┘     └────────────────┘
                              │
                     ┌────────┴────────┐
                     │  File System    │
                     │  - uploads/     │
                     │  - reg. faces/  │
                     │  - encodings    │
                     └─────────────────┘
```

## Setup

### Prerequisites
- Python 3.9+
- Webcam access
- cmake (`brew install cmake` on macOS)

### Installation

```bash
# Clone / navigate to project directory
cd siot_face_detection

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install tf-keras  # Required for TF 2.x compatibility

# Run the application
python app.py
```

The server starts at **http://127.0.0.1:5050**

## Usage

1. **Register** → Go to `/register`, enter your name/username, capture your face
2. **Login** → Go to `/login`, look into the camera, click Authenticate
3. **Access Vault** → If authenticated, you're redirected to your file vault
4. **Upload Files** → Click "Upload File" to add documents (PDF, images, text, etc.)
5. **View Logs** → Check `/access-logs` to see all authentication attempts

## How Face Recognition Works

1. **Registration**: DeepFace extracts a face embedding (128-dimensional vector) using the FaceNet model
2. **Storage**: The embedding is stored as JSON alongside a reference photo
3. **Authentication**: A new face capture is compared against all stored embeddings using **cosine distance**
4. **Decision**: If the distance is below the threshold (0.40), access is granted with a confidence score

## Project Structure

```
siot_face_detection/
├── app.py                 # Flask application (routes + API)
├── face_utils.py          # Face recognition logic (DeepFace)
├── requirements.txt       # Python dependencies
├── templates/
│   ├── base.html          # Base template (nav, footer)
│   ├── index.html         # Landing page
│   ├── register.html      # Face registration
│   ├── login.html         # Face authentication
│   ├── vault.html         # Document vault (protected)
│   ├── access_logs.html   # Auth attempt logs
│   └── denied.html        # Access denied page
├── static/
│   ├── css/style.css      # Styles
│   └── js/
│       ├── main.js        # General utilities
│       └── camera.js      # WebRTC camera handler
├── registered_faces/      # Face encodings + reference photos
└── uploads/               # Per-user document storage
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/register` | Register face (JSON: image, username, full_name) |
| POST | `/api/authenticate` | Authenticate face (JSON: image) |
| POST | `/api/upload` | Upload file to vault |
| POST | `/api/delete-file` | Delete file from vault |
| GET  | `/api/download/<file>` | Download file from vault |
| GET  | `/api/users` | List registered users |
| GET  | `/api/access-logs` | Get access logs as JSON |
