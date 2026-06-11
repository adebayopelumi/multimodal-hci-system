# assemblyai_client.py
import time
import requests
from pathlib import Path


# Load API key from assemblyai_key.txt in root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
KEY_PATH = PROJECT_ROOT / "assemblyai_key.txt"

with KEY_PATH.open("r", encoding="utf-8") as f:
    ASSEMBLYAI_API_KEY = f.read().strip()

BASE_URL = "https://api.assemblyai.com/v2"


def upload_audio(audio_bytes: bytes) -> str:
    """
    Upload raw audio bytes to AssemblyAI and return the audio_url.
    """
    headers = {
        "authorization": ASSEMBLYAI_API_KEY
    }

    response = requests.post(f"{BASE_URL}/upload", headers=headers, data=audio_bytes)

    if not response.ok:
        print("[AssemblyAI upload error]", response.status_code, response.text)
        response.raise_for_status()

    upload_url = response.json().get("upload_url")
    if not upload_url:
        raise RuntimeError("No upload_url returned from AssemblyAI.")
    return upload_url

def transcribe_audio_bytes(audio_bytes: bytes, timeout_sec: int = 30) -> str:
    """
    High-level helper:
    - uploads audio bytes
    - creates a transcript
    - polls until completed or error
    - returns the transcribed text
    """
    audio_url = upload_audio(audio_bytes)

    headers = {
        "authorization": ASSEMBLYAI_API_KEY,
        "content-type": "application/json"
    }

    # 1) Create transcript job
    body = {
        "audio_url": audio_url,
        "language_code": "en",   # generic English, supports many accents
        "punctuate": True
    }

    resp = requests.post(f"{BASE_URL}/transcript", json=body, headers=headers)
    resp.raise_for_status()
    transcript_id = resp.json()["id"]

    # 2) Poll for completion
    start = time.time()
    while True:
        poll = requests.get(f"{BASE_URL}/transcript/{transcript_id}", headers=headers)
        poll.raise_for_status()
        status = poll.json()["status"]

        if status == "completed":
            return poll.json().get("text", "").strip() or ""
        elif status == "error":
            raise RuntimeError(f"AssemblyAI error: {poll.json().get('error')}")

        if time.time() - start > timeout_sec:
            raise TimeoutError("AssemblyAI transcription timed out")

        time.sleep(1)
        


if __name__ == "__main__":
    print("assemblyai_client imported successfully.")
    print("This module is ready to transcribe audio bytes.")