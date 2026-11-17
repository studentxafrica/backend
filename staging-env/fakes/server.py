"""
Stand-ins for the two outside services the API calls, so staging never
uploads to the real Cloudinary account or emails real people.

- Cloudinary uploads: answer like Cloudinary after UPLOAD_DELAY seconds
  (production logs show about 2 s per ID photo).
- Mailtrap sends: keep every message so tests can read it, e.g. to follow a
  password-reset link. GET /mail?to=<address> lists them; DELETE /mail clears.
"""
import json
import os
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

UPLOAD_DELAY = float(os.environ.get("UPLOAD_DELAY", "2"))
PORT = int(os.environ.get("PORT", "9000"))

mail: list[dict] = []
mail_lock = threading.Lock()
stats = {"uploads": 0, "upload_bytes": 0, "mails": 0}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/healthz":
            return self._json(200, {"status": "ok", **stats})
        if url.path == "/mail":
            to = parse_qs(url.query).get("to", [None])[0]
            with mail_lock:
                found = [m for m in mail if to is None or to in m["to"]]
            return self._json(200, found)
        return self._json(404, {"error": "not found"})

    def do_DELETE(self):
        if urlparse(self.path).path == "/mail":
            with mail_lock:
                mail.clear()
            return self._json(200, {"cleared": True})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._body()

        upload = re.fullmatch(r"/v1_1/([^/]+)/([^/]+)/(upload|destroy)", path)
        if upload:
            cloud, resource_type, action = upload.groups()
            if action == "destroy":
                return self._json(200, {"result": "ok"})
            time.sleep(UPLOAD_DELAY)
            public_id = uuid.uuid4().hex
            stats["uploads"] += 1
            stats["upload_bytes"] += len(body)
            url = f"https://staging-cdn.invalid/{cloud}/{public_id}.jpg"
            return self._json(200, {
                "public_id": public_id, "version": 1, "resource_type": resource_type,
                "format": "jpg", "bytes": len(body), "width": 800, "height": 600,
                "url": url, "secure_url": url,
            })

        if path == "/api/send":
            message = json.loads(body or b"{}")
            record = {
                "id": uuid.uuid4().hex,
                "to": [r.get("email") for r in message.get("to", [])],
                "subject": message.get("subject"),
                "html": message.get("html"),
                "text": message.get("text"),
                "received_at": time.time(),
            }
            with mail_lock:
                mail.append(record)
            stats["mails"] += 1
            return self._json(200, {"success": True, "message_ids": [record["id"]]})

        return self._json(404, {"error": "not found"})


if __name__ == "__main__":
    print(f"fakes listening on {PORT}, upload delay {UPLOAD_DELAY}s", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
