"""Local live view of ACE-Step's first model download and initialization."""
from __future__ import annotations

import json
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECKPOINTS = ROOT / "ACE-Step-1.5" / "checkpoints"
MODEL_URL = "http://127.0.0.1:8001"
FILES = {
    "Turbo music model": ("acestep-v15-turbo/model.safetensors", 4_790_000_000),
    "Text encoder": ("Qwen3-Embedding-0.6B/model.safetensors", 1_190_000_000),
    "Audio decoder (VAE)": ("vae/diffusion_pytorch_model.safetensors", 337_431_388),
}

PAGE = """<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>ACE-Step download progress</title><style>
body{font:16px system-ui,sans-serif;background:#171a1c;color:#eee;max-width:760px;margin:48px auto;padding:0 22px}
h1{font-size:25px}p{color:#b9c1c4}.card{background:#23282b;padding:18px 20px;border-radius:12px;margin:14px 0}
.row{display:flex;justify-content:space-between;gap:12px}.bar{height:10px;background:#3a4246;border-radius:9px;margin:12px 0 5px;overflow:hidden}
.fill{height:100%;background:#67c5a2;width:0;transition:width .4s}.small{font-size:13px;color:#aab4b8}.state{color:#8bd9b9;font-weight:600}
</style></head><body><h1>ACE-Step model setup</h1><p>Live status of the local model download. This page refreshes automatically.</p>
<div id=state class=card>Checking…</div><div id=files></div><p class=small>Only the Turbo generator, text encoder, and audio decoder are needed. Download speed depends on your internet connection.</p>
<script>
function size(n){if(n>=1e9)return (n/1e9).toFixed(2)+' GB';if(n>=1e6)return (n/1e6).toFixed(1)+' MB';return Math.round(n/1e3)+' KB'}
async function refresh(){try{let d=await(await fetch('/progress.json',{cache:'no-store'})).json();let s=d.model_ready?'Ready — model initialized':d.api_online?'Downloading / initializing model…':'Waiting for ACE-Step server…';document.querySelector('#state').innerHTML='<span class=state>'+s+'</span><div class=small>Model API: '+(d.api_online?'online':'offline')+' · Initialized: '+(d.model_ready?'yes':'not yet')+'</div>';document.querySelector('#files').innerHTML=d.files.map(f=>'<div class=card><div class=row><strong>'+f.name+'</strong><span>'+f.percent.toFixed(1)+'%</span></div><div class=bar><div class=fill style="width:'+f.percent+'%"></div></div><div class=small>'+size(f.bytes)+' of '+size(f.total)+(f.complete?' · downloaded':' · downloading')+'</div></div>').join('')}catch(e){document.querySelector('#state').textContent='Could not read progress: '+e} }
refresh();setInterval(refresh,3000);
</script></body></html>"""


def snapshot() -> dict:
    items = []
    for name, (relative, total) in FILES.items():
        final = CHECKPOINTS / relative
        partial = final.with_name(final.name + ".incomplete")
        path = final if final.exists() else partial
        size = path.stat().st_size if path.exists() else 0
        items.append({"name": name, "bytes": min(size, total), "total": total,
                      "percent": min(100.0, size * 100 / total), "complete": final.exists()})
    try:
        with urllib.request.urlopen(MODEL_URL + "/health", timeout=1.5) as response:
            health = json.load(response).get("data", {})
        online = True
        ready = bool(health.get("models_initialized"))
    except Exception:
        online = ready = False
    return {"api_online": online, "model_ready": ready, "files": items}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/progress.json":
            body = json.dumps(snapshot()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        elif self.path == "/":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            self.send_error(404)
            return
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    print("Live model progress: http://127.0.0.1:7861")
    ThreadingHTTPServer(("127.0.0.1", 7861), Handler).serve_forever()
