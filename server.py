"""Small local web app and ACE-Step 1.5 API bridge."""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
HOST = os.getenv("APP_HOST", "127.0.0.1")
PORT = int(os.getenv("APP_PORT", "7860"))
MODEL_URL = os.getenv("ACESTEP_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
MODEL_KEY = os.getenv("ACESTEP_API_KEY", "")
MAX_UPLOAD = 25 * 1024 * 1024
TASKS: dict[str, str] = {}
TASK_LOCK = threading.Lock()


def model_request(path: str, data: bytes | None = None, content_type: str = "application/json"):
    headers = {"Content-Type": content_type}
    if MODEL_KEY:
        headers["Authorization"] = f"Bearer {MODEL_KEY}"
    req = urllib.request.Request(MODEL_URL + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as response:
        return response.read(), response.headers.get("Content-Type", "application/json")


class Handler(BaseHTTPRequestHandler):
    server_version = "PoemToSong/1.0"

    def log_message(self, *_args):
        pass

    def send_json(self, status: int, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            try:
                body, _ = model_request("/health")
                payload = json.loads(body)
                self.send_json(200, {"app": "ok", "model": "online", "model_status": payload})
            except Exception as exc:
                self.send_json(200, {"app": "ok", "model": "offline", "model_url": MODEL_URL, "detail": str(exc)})
            return
        if parsed.path == "/api/audio":
            params = urllib.parse.parse_qs(parsed.query)
            source = params.get("path", [""])[0]
            if not source.startswith("/v1/audio?"):
                self.send_json(400, {"error": "Invalid audio reference"})
                return
            try:
                body, mime = model_request(source, content_type="application/octet-stream")
                self.send_response(200)
                self.send_header("Content-Type", mime if mime.startswith("audio/") else "audio/mpeg")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "private, max-age=3600")
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                self.send_json(502, {"error": f"Could not retrieve generated audio: {exc}"})
            return
        if parsed.path == "/":
            target = ROOT / "static" / "index.html"
            mime = "text/html; charset=utf-8"
        elif parsed.path.startswith("/static/"):
            name = parsed.path.removeprefix("/static/")
            if name not in {"app.js", "styles.css"}:
                self.send_error(404)
                return
            target = ROOT / "static" / name
            mime = "text/javascript; charset=utf-8" if name.endswith(".js") else "text/css; charset=utf-8"
        else:
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path == "/api/generate":
            self.generate()
        elif self.path == "/api/status":
            self.status()
        else:
            self.send_json(404, {"error": "Not found"})

    def generate(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > MAX_UPLOAD + 1024 * 1024:
            self.send_json(413, {"error": "Upload must be under 25 MB"})
            return
        raw = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        try:
            message = BytesParser(policy=default).parsebytes(
                b"MIME-Version: 1.0\r\nContent-Type: " + content_type.encode() + b"\r\n\r\n" + raw
            )
            fields = {}
            voice = None
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if name == "voice":
                    voice = (part.get_filename() or "voice.wav", part.get_content_type(), part.get_payload(decode=True))
                elif name:
                    value = part.get_payload(decode=True) or b""
                    fields[name] = value.decode("utf-8", errors="replace").strip()
            poem = fields.get("poem", "").strip()
            style = fields.get("style", "").strip()
            if not poem or not voice or not voice[2]:
                self.send_json(400, {"error": "Add poem lyrics and a voice sample to continue."})
                return
            if len(voice[2]) > MAX_UPLOAD:
                self.send_json(413, {"error": "Voice sample must be under 25 MB"})
                return
            # Forward only to the configured local ACE-Step server. The reference clip is
            # used as best-effort timbre guidance; it is not a guaranteed voice clone.
            boundary = "----PoemSongBoundary7MA4YWxkTrZu0gW"
            chunks = []
            params = {
                "prompt": style or "Warm, intimate acoustic pop song; expressive solo lead vocal.",
                "lyrics": poem,
                "task_type": "text2music",
                # Keep the optional language model disabled so this setup only
                # needs the locally installed Turbo, text encoder, and VAE.
                "thinking": "false",
                "audio_format": "mp3",
                "audio_duration": "45",
                "vocal_language": fields.get("language", "en"),
            }
            for key, value in params.items():
                chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()])
            filename = voice[0].replace('"', "")
            chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"reference_audio\"; filename=\"{filename}\"\r\nContent-Type: {voice[1]}\r\n\r\n".encode(), voice[2], b"\r\n", f"--{boundary}--\r\n".encode()])
            body, _ = model_request("/release_task", b"".join(chunks), f"multipart/form-data; boundary={boundary}")
            response = json.loads(body)
            data = response.get("data", {})
            task_id = data.get("task_id")
            if not task_id:
                self.send_json(502, {"error": response.get("error") or "Model did not return a task ID."})
                return
            with TASK_LOCK:
                TASKS[task_id] = style or "Poem to song"
            self.send_json(200, {"task_id": task_id, "queue_position": data.get("queue_position")})
        except urllib.error.URLError as exc:
            self.send_json(502, {"error": f"ACE-Step is not reachable at {MODEL_URL}. Start its API server, then try again."})
        except Exception as exc:
            self.send_json(500, {"error": f"Could not start generation: {exc}"})

    def status(self):
        try:
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            task_id = str(request.get("task_id", ""))
            if not task_id or len(task_id) > 100:
                self.send_json(400, {"error": "Missing task ID"})
                return
            body, _ = model_request("/query_result", json.dumps({"task_id_list": [task_id]}).encode())
            response = json.loads(body)
            records = response.get("data") or []
            if not records:
                self.send_json(200, {"status": "queued", "message": "Waiting for the model"})
                return
            record = records[0]
            state = record.get("status", 0)
            if state == 1:
                result = record.get("result", "[]")
                if isinstance(result, str):
                    result = json.loads(result)
                item = next((x for x in result if x.get("file")), {}) if isinstance(result, list) else {}
                file_path = item.get("file", "")
                if not file_path.startswith("/v1/audio?"):
                    self.send_json(502, {"error": "Model succeeded but returned no playable audio file."})
                    return
                self.send_json(200, {"status": "succeeded", "audio_url": "/api/audio?path=" + urllib.parse.quote(file_path, safe=""), "title": "Your song is ready"})
            elif state == 2:
                self.send_json(200, {"status": "failed", "error": record.get("error") or "ACE-Step could not generate this track."})
            else:
                self.send_json(200, {"status": "running", "message": "Writing the music and vocal…"})
        except Exception as exc:
            self.send_json(502, {"error": f"Could not check generation status: {exc}"})


if __name__ == "__main__":
    print(f"Poem to Song is running at http://{HOST}:{PORT}")
    print(f"ACE-Step API: {MODEL_URL}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
