#!/usr/bin/env python3
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent


def load_env(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env(ROOT / ".env")


def clean(value, limit=1000):
    return str(value or "").strip()[:limit]


def send_quote(data):
    required = ("from_name", "phone", "pickup", "destination", "cargo_details", "service_type")
    values = {key: clean(data.get(key)) for key in required}
    if any(not values[key] for key in required):
        raise ValueError("Please complete all required fields.")
    values["email"] = clean(data.get("email"), 254)
    values["pickup_date"] = clean(data.get("pickup_date"), 40)

    recipient = os.environ.get("QUOTE_RECIPIENT", "krishnatemo931@gmail.com").strip()
    payload = {
        "Name": values["from_name"],
        "Phone": values["phone"],
        "Customer Email": values["email"] or "Not provided",
        "Service Type": values["service_type"],
        "Pickup Location": values["pickup"],
        "Delivery Location": values["destination"],
        "Preferred Pickup Date": values["pickup_date"] or "Not specified",
        "Cargo Details": values["cargo_details"],
        "_subject": f"New Quote: {values['pickup']} to {values['destination']} — {values['from_name']}",
        "_template": "table",
        "_replyto": values["email"],
    }
    request = Request(
        f"https://formsubmit.co/ajax/{recipient}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
            if not result.get("success"):
                raise RuntimeError(result.get("message", "Email service rejected the request."))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Email service returned HTTP {error.code}: {detail[:200]}") from error
    except URLError as error:
        raise RuntimeError("Could not connect to the email service.") from error


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/quote":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 100_000:
                raise ValueError("Request is too large.")
            data = json.loads(self.rfile.read(length) or b"{}")
            send_quote(data)
            self.respond(200, {"success": True, "message": "Quote request sent."})
        except ValueError as error:
            self.respond(400, {"success": False, "message": str(error)})
        except Exception as error:
            print(f"Email error: {type(error).__name__}: {error}")
            self.respond(500, {"success": False, "message": "Email could not be sent."})

    def respond(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    os.chdir(ROOT)
    port = int(os.environ.get("PORT", "8000"))
    print(f"Website running at http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
