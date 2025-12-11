"""
uvicorn security_implementation:app --reload
Invoke-WebRequest -Uri "http://127.0.0.1:8000/ai/process" `
  -Method POST `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{ "prompt": "hello" }'
                                                            --Test Rate Limiting (10 requests/min)--
curl.exe -X POST "http://127.0.0.1:8000/ai/process" -H "Content-Type: application/json" -d "{`"prompt`": `"Explain machine learning in simple terms`"}"
                                                            --Test Prompt Injection Blocking--
curl http://127.0.0.1:8000/rotate-key - manually rotate API keys
curl http://127.0.0.1:8000/export/123 - exports data for user 123
python data_retention_script.py - deletes old user data files
"""



import os
import re
import json
import time
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Dict
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

app = FastAPI(title="AI Security Layer")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.middleware("http")
async def rate_limit(request: Request, call_next):
    response = await limiter.limit("10/minute")(call_next)(request)
    return response

KEY_FILE = "api_keys.json"

def load_keys():
    if not os.path.exists(KEY_FILE):
        save_keys({"current": generate_key(), "previous": None, "last_rotated": str(datetime.now())})
    with open(KEY_FILE, "r") as f:
        return json.load(f)

def save_keys(data):
    with open(KEY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def generate_key():
    return hashlib.sha256(os.urandom(32)).hexdigest()

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

@app.post("/ai/process")
async def process_ai(request: Request):
    body = await request.json()
    prompt = sanitize_input(body.get("prompt", ""))

    return {
        "message": "AI request sanitized and processed.",
        "prompt": prompt,
        "timestamp": str(datetime.now())
    }

USER_DATA_DIR = "user_data"

@app.get("/export/{user_id}")
def export_user_data(user_id: str):
    user_file = f"{USER_DATA_DIR}/{user_id}.json"
    if not os.path.exists(user_file):
        raise HTTPException(status_code=404, detail="No data found")

    with open(user_file, "r") as f:
        data = json.load(f)

    return {"user_id": user_id, "exported_data": data}
