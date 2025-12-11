"""
uvicorn security_implementation:app --reload
Invoke-WebRequest -Uri "http://127.0.0.1:8000/ai/process" `
  -Method POST `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{ "prompt": "hello" }'
                                                            --Test Rate Limiting (10 requests/min)--
curl http://127.0.0.1:8000/rotate-key - manually rotate API keys
curl http://127.0.0.1:8000/export/123 - exports data for user 123
python data_retention_script.py - deletes old user data files
"""

# security_implementation_fixed.py
import os
import re
import json
import hashlib
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])

app = FastAPI(title="AI Security Layer (fixed)")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

#API KEY ROTATION
KEY_FILE = "api_keys.json"

def generate_key():
    return hashlib.sha256(os.urandom(32)).hexdigest()

def save_keys(data):
    with open(KEY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_keys():
    if not os.path.exists(KEY_FILE):
        save_keys({"current": generate_key(), "previous": None, "last_rotated": str(datetime.now())})
    with open(KEY_FILE, "r") as f:
        return json.load(f)

def rotate_keys():
    keys = load_keys()
    last_rotated = datetime.fromisoformat(keys["last_rotated"])
    if datetime.now() - last_rotated > timedelta(days=7):
        new_key = generate_key()
        keys["previous"] = keys["current"]
        keys["current"] = new_key
        keys["last_rotated"] = str(datetime.now())
        save_keys(keys)
        return True
    return False

@app.get("/rotate-key")
def manual_rotate():
    rotated = rotate_keys()
    return {"rotated": rotated}

#PROMPT SANITIZATION
PROMPT_INJECTION_PATTERNS = [
    r"(?:ignore|bypass|disable).*?(?:instructions|rules)",
    r"(?:pretend|act as).*?(?:system|developer)",
    r"(?:reveal).*?(?:prompt|instructions)",
    r"system:|developer:|assistant:"
]

def sanitize_input(user_input: str) -> str:
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, user_input, re.IGNORECASE):
            raise HTTPException(status_code=400, detail="Blocked: Potential prompt injection detected.")
    return user_input

#AI PROCESS ENDPOINT (rate-limited)
@app.post("/ai/process")
@limiter.limit("10/minute")
async def process_ai(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON payload. Ensure you send application/json with proper double-quoted keys."})

    prompt = body.get("prompt", "")
    # sanitize input
    try:
        prompt = sanitize_input(prompt)
    except HTTPException as e:
        # forward the sanitized error as JSON
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

    return {
        "message": "AI request sanitized and processed.",
        "prompt": prompt,
        "timestamp": str(datetime.now())
    }

#USER DATA EXPORT
USER_DATA_DIR = "user_data"
os.makedirs(USER_DATA_DIR, exist_ok=True)

@app.get("/export/{user_id}")
def export_user_data(user_id: str):
    user_file = os.path.join(USER_DATA_DIR, f"{user_id}.json")
    if not os.path.exists(user_file):
        raise HTTPException(status_code=404, detail="No data found")
    with open(user_file, "r") as f:
        data = json.load(f)
    return {"user_id": user_id, "exported_data": data}
