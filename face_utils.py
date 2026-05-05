"""
Face recognition utility module.
Uses DeepFace for face encoding and comparison in SecureVault.
"""

import os
import json
import shutil
import numpy as np
from datetime import datetime

from deepface import DeepFace

# Directory where registered face images and encodings are stored
FACES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registered_faces")
ENCODINGS_FILE = os.path.join(FACES_DIR, "encodings.json")

# Similarity threshold — used for cosine distance (lower = stricter)
DISTANCE_THRESHOLD = 0.40
MODEL_NAME = "Facenet"
DETECTOR_BACKEND = "opencv"


def _ensure_dirs():
    """Create the faces directory if it doesn't exist."""
    os.makedirs(FACES_DIR, exist_ok=True)


def _load_encodings():
    """Load all saved face encodings from disk."""
    _ensure_dirs()
    if not os.path.exists(ENCODINGS_FILE):
        return {}
    with open(ENCODINGS_FILE, "r") as f:
        data = json.load(f)
    return data


def _save_encodings(encodings_dict):
    """Persist face encodings to disk."""
    _ensure_dirs()
    # Ensure numpy arrays are converted to lists for JSON
    serialisable = {}
    for uid, info in encodings_dict.items():
        info_copy = dict(info)
        if isinstance(info_copy.get("encoding"), np.ndarray):
            info_copy["encoding"] = info_copy["encoding"].tolist()
        serialisable[uid] = info_copy
    with open(ENCODINGS_FILE, "w") as f:
        json.dump(serialisable, f)


def _get_embedding(image_path):
    """
    Extract face embedding from an image using DeepFace.
    Returns (embedding_list, error_message).
    """
    try:
        results = DeepFace.represent(
            img_path=image_path,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR_BACKEND,
            enforce_detection=True,
        )
        if not results or len(results) == 0:
            return None, "No face detected in the image."
        if len(results) > 1:
            return None, "Multiple faces detected. Please ensure only your face is in the frame."
        return results[0]["embedding"], None
    except ValueError as e:
        err = str(e)
        if "could not find any face" in err.lower() or "no face" in err.lower():
            return None, "No face detected. Please ensure your face is clearly visible and well-lit."
        return None, f"Face detection error: {err}"
    except Exception as e:
        return None, f"Processing error: {str(e)}"


def _cosine_distance(a, b):
    """Compute cosine distance between two vectors."""
    a = np.array(a)
    b = np.array(b)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))


def register_face(image_path, username, full_name):
    """
    Register a new face from an image file.
    Returns dict with 'success' (bool) and 'message' (str).
    """
    embedding, error = _get_embedding(image_path)
    if error:
        return {"success": False, "message": error}

    existing = _load_encodings()

    # Check if this face is already registered
    for uid, info in existing.items():
        dist = _cosine_distance(embedding, info["encoding"])
        if dist < DISTANCE_THRESHOLD:
            return {
                "success": False,
                "message": f"This face is already registered under username '{info['username']}'.",
            }

    # Check if username is taken
    if username in existing:
        return {"success": False, "message": f"Username '{username}' is already taken."}

    # Store the encoding and reference image
    existing[username] = {
        "username": username,
        "full_name": full_name,
        "encoding": embedding if isinstance(embedding, list) else list(embedding),
        "registered_at": datetime.now().isoformat(),
    }
    _save_encodings(existing)

    # Save reference photo
    ref_path = os.path.join(FACES_DIR, f"{username}.jpg")
    shutil.copy2(image_path, ref_path)

    return {"success": True, "message": f"Face registered successfully for {full_name}!"}


def authenticate_face(image_path):
    """
    Authenticate a user by comparing face against all registered faces.
    Returns dict with 'authenticated', 'username', 'full_name', 'confidence', 'message'.
    """
    embedding, error = _get_embedding(image_path)
    if error:
        return {
            "authenticated": False,
            "username": None,
            "full_name": None,
            "confidence": 0.0,
            "message": error,
        }

    existing = _load_encodings()
    if not existing:
        return {
            "authenticated": False,
            "username": None,
            "full_name": None,
            "confidence": 0.0,
            "message": "No registered users found. Please register first.",
        }

    # Compare against all registered faces
    best_match = None
    best_distance = float("inf")

    for uid, info in existing.items():
        dist = _cosine_distance(embedding, info["encoding"])
        if dist < best_distance:
            best_distance = dist
            best_match = uid

    # Convert distance to confidence (0 distance = 100%)
    confidence = round(max(0, (1.0 - best_distance)) * 100, 2)

    if best_distance < DISTANCE_THRESHOLD and best_match:
        user_info = existing[best_match]
        return {
            "authenticated": True,
            "username": best_match,
            "full_name": user_info["full_name"],
            "confidence": confidence,
            "message": f"Access granted. Welcome back, {user_info['full_name']}!",
        }
    else:
        return {
            "authenticated": False,
            "username": None,
            "full_name": None,
            "confidence": confidence,
            "message": "Face not recognised. Access denied.",
        }


def get_registered_users():
    """Return a list of registered users (without encodings)."""
    existing = _load_encodings()
    users = []
    for uid, info in existing.items():
        users.append({
            "username": info["username"],
            "full_name": info["full_name"],
            "registered_at": info.get("registered_at", "Unknown"),
            "has_photo": os.path.exists(os.path.join(FACES_DIR, f"{uid}.jpg")),
        })
    return users


def delete_user(username):
    """Remove a registered user."""
    existing = _load_encodings()
    if username not in existing:
        return {"success": False, "message": "User not found."}

    del existing[username]
    _save_encodings(existing)

    ref_path = os.path.join(FACES_DIR, f"{username}.jpg")
    if os.path.exists(ref_path):
        os.remove(ref_path)

    return {"success": True, "message": f"User '{username}' has been removed."}
