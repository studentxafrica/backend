"""
Stand-ins for the two outside services the API calls, so staging never
uploads to the real Cloudinary account or emails real people.

- Cloudinary uploads: answer like Cloudinary after UPLOAD_DELAY seconds
  (production logs show about 2 s per ID photo).
- Mailtrap sends: keep every message so tests can read it, e.g. to follow a
  password-reset link. GET /mail?to=<address> lists them; DELETE /mail clears.
- Brevo contacts API (/brevo/v3/...): the calls the member sync makes, kept
  in memory. GET /brevo/contacts shows every contact; POST
  /brevo/unsubscribe?email=<address> marks one as unsubscribed, as if they
  had used a campaign's unsubscribe link.
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
# email -> {"email", "attributes", "listIds", "emailBlacklisted"}
brevo_contacts: dict[str, dict] = {}
brevo_lock = threading.Lock()


def _brevo_upsert(email, attributes=None, list_ids=(), blacklisted=None):
    contact = brevo_contacts.setdefault(email.lower(), {
        "email": email.lower(), "attributes": {}, "listIds": [], "emailBlacklisted": False})
    contact["attributes"].update(attributes or {})
    contact["listIds"] = sorted(set(contact["listIds"]) | set(list_ids))
    if blacklisted is not None:
        contact["emailBlacklisted"] = blacklisted


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
        if url.path == "/brevo/contacts":
            with brevo_lock:
                return self._json(200, sorted(brevo_contacts.values(), key=lambda c: c["email"]))
        members = re.fullmatch(r"/brevo/v3/contacts/lists/(\d+)/contacts", url.path)
        if members:
            query = parse_qs(url.query)
            limit, offset = int(query.get("limit", ["50"])[0]), int(query.get("offset", ["0"])[0])
            with brevo_lock:
                on_list = [c for c in brevo_contacts.values() if int(members.group(1)) in c["listIds"]]
            return self._json(200, {"contacts": on_list[offset:offset + limit], "count": len(on_list)})
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

    def do_PUT(self):
        path = urlparse(self.path).path
        found = re.fullmatch(r"/brevo/v3/contacts/(.+)", path)
        if not found:
            return self._json(404, {"error": "not found"})
        from urllib.parse import unquote
        old, data = unquote(found.group(1)).lower(), json.loads(self._body() or b"{}")
        with brevo_lock:
            contact = brevo_contacts.pop(old, None)
            if not contact:
                return self._json(404, {"code": "document_not_found"})
            new = (data.get("attributes") or {}).pop("EMAIL", None)
            if new:
                contact["email"] = new.lower()
            contact["attributes"].update(data.get("attributes") or {})
            brevo_contacts[contact["email"]] = contact
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path
        body = self._body()

        if path.startswith("/brevo/"):
            data = json.loads(body or b"{}")
            with brevo_lock:
                if path == "/brevo/v3/contacts":
                    _brevo_upsert(data["email"], data.get("attributes"), data.get("listIds", []),
                                  data.get("emailBlacklisted"))
                    return self._json(201, {"id": len(brevo_contacts)})
                if path == "/brevo/v3/contacts/import":
                    for row in data.get("jsonBody", []):
                        _brevo_upsert(row["email"], row.get("attributes"), data.get("listIds", []))
                    return self._json(202, {"processId": 1})
                removing = re.fullmatch(r"/brevo/v3/contacts/lists/(\d+)/contacts/remove", path)
                if removing:
                    list_id, gone = int(removing.group(1)), []
                    for email in data.get("emails", []):
                        contact = brevo_contacts.get(email.lower())
                        if contact and list_id in contact["listIds"]:
                            contact["listIds"].remove(list_id)
                            gone.append(email)
                    if not gone:
                        return self._json(400, {"code": "invalid_parameter", "message": "Contact not in list"})
                    return self._json(201, {"contacts": {"success": gone}})
                if path == "/brevo/unsubscribe":
                    email = parse_qs(url.query).get("email", [""])[0].lower()
                    if email not in brevo_contacts:
                        return self._json(404, {"error": "no such contact"})
                    brevo_contacts[email]["emailBlacklisted"] = True
                    return self._json(200, brevo_contacts[email])
            return self._json(404, {"error": "not found"})

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
