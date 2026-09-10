"""Loopback-only web entry point. Never serves the repository or local configuration."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from multi_agent.application.rwe_service import ROOT, RWEJobService


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, body, content_type="application/json; charset=utf-8", filename=None):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def allowed(self):
            hosts = {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"}
            if self.headers.get("Host") not in hosts:
                self.respond(403, {"error": "仅允许本机访问"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + h for h in hosts}:
                self.respond(403, {"error": "不允许跨站请求"})
                return False
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.respond(403, {"error": "不允许跨站请求"})
                return False
            return True

        def do_GET(self):
            if not self.allowed():
                return
            path = urlsplit(self.path).path
            if path in {"/", "/ui/multi_agent_dashboard.html"}:
                return self.respond(200, (ROOT / "ui/multi_agent_dashboard.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/ui/dashboard.js":
                return self.respond(200, (ROOT / "ui/dashboard.js").read_bytes(), "text/javascript; charset=utf-8")
            if path == "/api/health":
                return self.respond(200, {"status": "ok", "engine": "v2", "goal": "rwe_patient_summary"})
            parts = path.strip("/").split("/")
            if len(parts) in {3, 4} and parts[:2] == ["api", "runs"]:
                try:
                    if len(parts) == 3:
                        return self.respond(200, service.get(parts[2]))
                    files = {"report": "report.json", "source": "patient.json"}
                    if parts[3] not in files:
                        raise KeyError("文件不存在")
                    file = service.directory(parts[2]) / files[parts[3]]
                    return self.respond(200, file.read_bytes(), filename=files[parts[3]])
                except (KeyError, FileNotFoundError):
                    return self.respond(404, {"error": "任务或文件不存在"})
            self.respond(404, {"error": "页面不存在"})

        def do_POST(self):
            if not self.allowed():
                return
            if self.path != "/api/runs":
                return self.respond(404, {"error": "接口不存在"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024:
                    raise ValueError("请求大小不正确")
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("请求必须为 JSON")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or set(body) != {"patient_number"}:
                    raise ValueError("只需提供 patient_number")
                job = service.create(body["patient_number"])
                return self.respond(202, job)
            except (ValueError, UnicodeError) as exc:
                self.respond(400, {"error": str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    service = RWEJobService()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(service))
    print(f"RWE workspace: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        service.close()


if __name__ == "__main__":
    main()
