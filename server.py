#!/usr/bin/env python3
import json
import os
import requests
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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


def send_quote(data, site_url):
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
    try:
        response = requests.post(
            f"https://formsubmit.co/ajax/{recipient}",
            json=payload,
            headers={
                "Accept": "application/json",
                "Origin": site_url,
                "Referer": f"{site_url}/",
                "User-Agent": "Shri-Krishna-Temo-Cargo/1.0",
            },
            timeout=20,
        )
        result = response.json()
        success = str(result.get("success", "false")).lower() == "true"
        if not response.ok or not success:
            raise RuntimeError(result.get("message", "Email service rejected the request."))
    except requests.RequestException as error:
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
            protocol = self.headers.get("X-Forwarded-Proto", "http").split(",")[0].strip()
            host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "localhost")
            site_url = f"{protocol}://{host}"
            send_quote(data, site_url)
            self.respond(200, {"success": True, "message": "Quote request sent."})
        except ValueError as error:
            self.respond(400, {"success": False, "message": str(error)})
        except RuntimeError as error:
            print(f"Email service: {error}")
            self.respond(502, {"success": False, "message": str(error)})
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
