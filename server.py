#!/usr/bin/env python3
import html
import json
import os
import smtplib
from email.message import EmailMessage
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


def email_html(data):
    fields = [
        ("Customer", data["from_name"]),
        ("Phone", data["phone"]),
        ("Email", data.get("email") or "Not provided"),
        ("Service", data["service_type"]),
        ("Pickup", data["pickup"]),
        ("Destination", data["destination"]),
        ("Pickup date", data.get("pickup_date") or "Not specified"),
        ("Cargo details", data["cargo_details"]),
    ]
    rows = "".join(
        f'<tr><td style="padding:12px 16px;color:#677482;border-bottom:1px solid #e7ebee;width:34%;font-size:12px;text-transform:uppercase;letter-spacing:.08em">{html.escape(label)}</td>'
        f'<td style="padding:12px 16px;color:#10263a;border-bottom:1px solid #e7ebee;font-size:14px;font-weight:600;white-space:pre-wrap">{html.escape(value)}</td></tr>'
        for label, value in fields
    )
    return f'''<!doctype html><html><body style="margin:0;background:#f3f5f6;font-family:Arial,sans-serif">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:28px 12px"><tr><td align="center">
      <table role="presentation" width="620" cellspacing="0" cellpadding="0" style="max-width:620px;width:100%;background:#fff;border-collapse:collapse">
        <tr><td style="background:#081a2c;padding:26px 30px;border-top:5px solid #f47a20">
          <div style="color:#f47a20;font-size:11px;letter-spacing:.18em;font-weight:bold">SHRI KRISHNA TEMO CARGO</div>
          <h1 style="margin:8px 0 0;color:#fff;font-size:25px">New Transport Quote Request</h1>
        </td></tr>
        <tr><td style="padding:25px 30px 10px;color:#425466;font-size:14px;line-height:1.6">A customer submitted a new quote enquiry through the website.</td></tr>
        <tr><td style="padding:10px 30px 28px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #e7ebee;border-collapse:collapse">{rows}</table></td></tr>
        <tr><td style="background:#f47a20;padding:16px 30px;color:#fff;font-size:12px">Reply to this email or call <strong>{html.escape(data['phone'])}</strong> to follow up.</td></tr>
      </table>
    </td></tr></table></body></html>'''


def send_quote(data):
    required = ("from_name", "phone", "pickup", "destination", "cargo_details", "service_type")
    values = {key: clean(data.get(key)) for key in required}
    if any(not values[key] for key in required):
        raise ValueError("Please complete all required fields.")
    values["email"] = clean(data.get("email"), 254)
    values["pickup_date"] = clean(data.get("pickup_date"), 40)

    smtp_user = os.environ["SMTP_USER"]
    recipient = os.environ.get("QUOTE_RECIPIENT", smtp_user)
    cc = os.environ.get("QUOTE_CC", "").strip()
    message = EmailMessage()
    message["Subject"] = f"New Quote: {values['pickup']} to {values['destination']} — {values['from_name']}"
    message["From"] = f"Shri Krishna Temo Cargo Website <{smtp_user}>"
    message["To"] = recipient
    if cc:
        message["Cc"] = cc
    if values["email"]:
        message["Reply-To"] = values["email"]
    message.set_content("New transport quote request\n\n" + "\n".join(f"{k}: {v}" for k, v in values.items()))
    message.add_alternative(email_html(values), subtype="html")

    recipients = [recipient] + ([cc] if cc else [])
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    password = os.environ["SMTP_APP_PASSWORD"].replace(" ", "")
    smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    with smtp_class(host, port, timeout=20) as smtp:
        if port != 465:
            smtp.starttls()
        smtp.login(smtp_user, password)
        smtp.send_message(message, to_addrs=recipients)


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
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
