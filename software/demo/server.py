#!/usr/bin/env python3
"""MetroMap Live - kleine lokale server.

Serveert metromap-live.html en stuurt /ovapi/... door naar https://v0.ovapi.nl/...
zodat de browser geen last heeft van CORS. Alleen de Python standaardbibliotheek.

    python3 server.py            # poort 8000
    python3 server.py 8080       # andere poort

Open daarna http://localhost:8000 op je pc, of http://<ip-van-je-pc>:8000
op je telefoon (zelfde wifi).
"""
import http.server
import socket
import sys
import time
import urllib.request
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
HERE = Path(__file__).resolve().parent
PAGE = HERE / "metromap-live.html"
UPSTREAM = "http://v0.ovapi.nl"   # https-certificaat van OVapi klopt niet
CACHE_SECONDS = 10          # meerdere schermen tegelijk = één aanvraag naar OVapi
_cache = {}


def fetch_upstream(path):
    """Returns (body, content_encoding). OVapi gzips about 20x; passed through as is."""
    hit = _cache.get(path)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1], hit[2]
    req = urllib.request.Request(UPSTREAM + path, headers={
        "User-Agent": "MetroMap-Live/0.1 (hobby project)",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read()
        enc = r.headers.get("Content-Encoding")
    _cache[path] = (time.time(), body, enc)
    return body, enc


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype, encoding=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if encoding:
            self.send_header("Content-Encoding", encoding)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/ovapi/"):
            try:
                body, enc = fetch_upstream(self.path[len("/ovapi"):])
                self._send(200, body, "application/json", enc)
            except Exception as e:  # noqa: BLE001 - doorgeven aan de pagina
                self._send(502, f"OVapi niet bereikbaar: {e}".encode(), "text/plain; charset=utf-8")
            return
        if self.path in ("/", "/index.html", "/metromap-live.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            return
        self._send(404, b"niet gevonden", "text/plain")

    def log_message(self, fmt, *args):
        pass


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "jouw-pc-ip"


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"MetroMap Live draait op:\n  pc:       http://localhost:{PORT}\n  telefoon: http://{lan_ip()}:{PORT}\nStoppen met Ctrl+C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
