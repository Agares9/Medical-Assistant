from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import http.client
import os

ROOT = Path(__file__).parent / "web"
BACKEND_URL = os.getenv("MEDIX_BACKEND_URL", "http://127.0.0.1:7864")
BACKEND = urlsplit(BACKEND_URL)


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        if path in ("/", ""):
            return str(ROOT / "index.html")
        if path == "/icon.png":
            return str(ROOT.parent / "icon.png")
        if path.startswith("/static/"):
            return str(ROOT / path[len("/static/") :])
        return str(ROOT / path.lstrip("/"))

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.proxy_to_backend()
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self.proxy_to_backend()
            return
        self.send_error(404)

    def proxy_to_backend(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        path = self.path
        backend_path = path if path.startswith("/") else f"/{path}"

        connection_cls = http.client.HTTPSConnection if BACKEND.scheme == "https" else http.client.HTTPConnection
        port = BACKEND.port or (443 if BACKEND.scheme == "https" else 80)
        conn = connection_cls(BACKEND.hostname, port, timeout=190)

        headers = {
            "Content-Type": self.headers.get("Content-Type", "application/json"),
            "Accept": self.headers.get("Accept", "application/json"),
        }

        try:
            conn.request(self.command, backend_path, body=body, headers=headers)
            response = conn.getresponse()
            response_body = response.read()

            self.send_response(response.status)
            content_type = response.getheader("Content-Type", "application/json")
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
        except Exception as e:
            payload = f'{{"error":"backend_unavailable","detail":"{str(e)}"}}'.encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        finally:
            conn.close()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    os.chdir(ROOT)
    print(f"Static preview: http://127.0.0.1:8080")
    print(f"Proxy /api/* -> {BACKEND_URL}")
    ThreadingHTTPServer(("127.0.0.1", 8080), Handler).serve_forever()
