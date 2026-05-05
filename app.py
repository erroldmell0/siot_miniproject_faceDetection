"""
SecureVault — Face-Recognition Protected Document Vault
Main Flask application.
"""

import os
import uuid
import base64
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, send_from_directory, flash
)
from werkzeug.utils import secure_filename

from face_utils import register_face, authenticate_face, get_registered_users, delete_user

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "securevault-dev-key-change-in-production")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
TEMP_DIR = os.path.join(BASE_DIR, "temp_captures")
FACES_DIR = os.path.join(BASE_DIR, "registered_faces")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(FACES_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "docx", "xlsx", "csv", "md"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    """Decorator to protect routes behind face-auth."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            flash("You must authenticate with your face to access the vault.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def save_base64_image(data_url):
    """Save a base64-encoded camera capture to a temp file and return the path."""
    # data:image/jpeg;base64,/9j/4AAQ...
    header, encoded = data_url.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = os.path.join(TEMP_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(img_bytes)
    return filepath


def get_user_upload_dir(username):
    """Each user gets their own upload directory."""
    user_dir = os.path.join(UPLOAD_DIR, secure_filename(username))
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


# ---------------------------------------------------------------------------
# Access Logs (in-memory for simplicity)
# ---------------------------------------------------------------------------
access_logs = []


def log_access(username, full_name, success, confidence, ip_address):
    access_logs.append({
        "timestamp": datetime.now().isoformat(),
        "username": username or "Unknown",
        "full_name": full_name or "Unknown",
        "success": success,
        "confidence": confidence,
        "ip_address": ip_address,
    })
    # Keep only the last 50 logs
    if len(access_logs) > 50:
        access_logs.pop(0)


# ---------------------------------------------------------------------------
# Public Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register")
def register():
    return render_template("register.html")


@app.route("/login")
def login():
    if session.get("authenticated"):
        return redirect(url_for("vault"))
    return render_template("login.html")


@app.route("/denied")
def denied():
    return render_template("denied.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Protected Routes
# ---------------------------------------------------------------------------
@app.route("/vault")
@login_required
def vault():
    username = session.get("username")
    full_name = session.get("full_name")
    user_dir = get_user_upload_dir(username)
    
    # List user's files
    files = []
    if os.path.exists(user_dir):
        for fname in os.listdir(user_dir):
            fpath = os.path.join(user_dir, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                files.append({
                    "name": fname,
                    "size": round(stat.st_size / 1024, 2),  # KB
                    "uploaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "extension": fname.rsplit(".", 1)[-1].lower() if "." in fname else "file",
                })
    
    files.sort(key=lambda x: x["name"])
    
    return render_template(
        "vault.html",
        username=username,
        full_name=full_name,
        files=files,
        allowed_extensions=", ".join(sorted(ALLOWED_EXTENSIONS)),
    )


@app.route("/access-logs")
@login_required
def view_access_logs():
    return render_template(
        "access_logs.html",
        logs=list(reversed(access_logs)),
        username=session.get("username"),
        full_name=session.get("full_name"),
    )


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------
@app.route("/api/register", methods=["POST"])
def api_register():
    """Register a new face via webcam capture."""
    data = request.get_json()
    
    if not data:
        return jsonify({"success": False, "message": "No data received."}), 400
    
    image_data = data.get("image")
    username = data.get("username", "").strip().lower()
    full_name = data.get("full_name", "").strip()
    
    if not image_data:
        return jsonify({"success": False, "message": "No image captured."}), 400
    if not username or len(username) < 3:
        return jsonify({"success": False, "message": "Username must be at least 3 characters."}), 400
    if not full_name or len(full_name) < 2:
        return jsonify({"success": False, "message": "Full name is required."}), 400
    if not username.isalnum():
        return jsonify({"success": False, "message": "Username must be alphanumeric."}), 400
    
    # Save the captured image temporarily
    filepath = save_base64_image(image_data)
    
    try:
        result = register_face(filepath, username, full_name)
        return jsonify(result)
    finally:
        # Clean up temp file
        if os.path.exists(filepath):
            os.remove(filepath)


@app.route("/api/authenticate", methods=["POST"])
def api_authenticate():
    """Authenticate a face via webcam capture."""
    data = request.get_json()
    
    if not data or not data.get("image"):
        return jsonify({"authenticated": False, "message": "No image received."}), 400
    
    filepath = save_base64_image(data["image"])
    
    try:
        result = authenticate_face(filepath)
        
        # Log the attempt
        log_access(
            username=result.get("username"),
            full_name=result.get("full_name"),
            success=result["authenticated"],
            confidence=result.get("confidence", 0),
            ip_address=request.remote_addr,
        )
        
        if result["authenticated"]:
            session["authenticated"] = True
            session["username"] = result["username"]
            session["full_name"] = result["full_name"]
            session["login_time"] = datetime.now().isoformat()
        
        return jsonify(result)
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    """Upload a file to the authenticated user's vault."""
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file provided."}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No file selected."}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"success": False, "message": f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"}), 400
    
    filename = secure_filename(file.filename)
    user_dir = get_user_upload_dir(session["username"])
    
    # Avoid overwriting — append a number if file exists
    base, ext = os.path.splitext(filename)
    counter = 1
    final_name = filename
    while os.path.exists(os.path.join(user_dir, final_name)):
        final_name = f"{base}_{counter}{ext}"
        counter += 1
    
    file.save(os.path.join(user_dir, final_name))
    
    return jsonify({"success": True, "message": f"File '{final_name}' uploaded successfully.", "filename": final_name})


@app.route("/api/delete-file", methods=["POST"])
@login_required
def api_delete_file():
    """Delete a file from the user's vault."""
    data = request.get_json()
    filename = data.get("filename", "")
    
    if not filename:
        return jsonify({"success": False, "message": "No filename provided."}), 400
    
    user_dir = get_user_upload_dir(session["username"])
    filepath = os.path.join(user_dir, secure_filename(filename))
    
    if not os.path.exists(filepath):
        return jsonify({"success": False, "message": "File not found."}), 404
    
    os.remove(filepath)
    return jsonify({"success": True, "message": f"File '{filename}' deleted."})


@app.route("/api/download/<filename>")
@login_required
def api_download(filename):
    """Download a file from the user's vault."""
    user_dir = get_user_upload_dir(session["username"])
    safe_name = secure_filename(filename)
    return send_from_directory(user_dir, safe_name, as_attachment=True)


@app.route("/api/users")
def api_users():
    """List registered users (for admin/debug purposes)."""
    users = get_registered_users()
    return jsonify({"users": users, "count": len(users)})


@app.route("/api/access-logs")
@login_required
def api_access_logs():
    """Return recent access logs as JSON."""
    return jsonify({"logs": list(reversed(access_logs))})


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n🔐 SecureVault — Face Recognition Document Vault")
    print("   Starting server at http://127.0.0.1:5050\n")
    app.run(debug=True, host="0.0.0.0", port=5050)
