from __future__ import annotations

import cgi
import json
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from agent_app.service import AgentService
from agent_app.settings import SERVER_HOST, SERVER_PORT, now_iso


AGENT_SERVICE = AgentService()


class ApiHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, event: str, data: Any) -> None:
        if not isinstance(data, str):
            data = json.dumps(data, ensure_ascii=False)
        lines = data.splitlines() or [""]
        payload = [f"event: {event}\n".encode("utf-8")]
        for line in lines:
            payload.append(f"data: {line}\n".encode("utf-8"))
        payload.append(b"\n")
        self.wfile.write(b"".join(payload))
        self.wfile.flush()

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _handle_health(self) -> None:
        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": "agent-demo",
                "time": now_iso(),
                "knowledge_base": AGENT_SERVICE.kb.stats(),
                "mcp": AGENT_SERVICE.mcp_registry.status(),
            },
        )

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        try:
            if self.path in {"/", "/health", "/api/health"}:
                self._handle_health()
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
        except Exception as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": str(exc), "trace": traceback.format_exc()},
            )

    def do_POST(self) -> None:  # noqa: N802
        try:
            if self.path == "/api/chat":
                self._handle_chat()
                return
            if self.path == "/api/upload":
                self._handle_upload()
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
        except Exception as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": str(exc), "trace": traceback.format_exc()},
            )

    def _handle_chat(self) -> None:
        payload = self._read_json_body()
        message = str(payload.get("message", "")).strip()
        session_id = str(payload.get("session_id", "default")).strip() or "default"
        stream = bool(payload.get("stream", True))

        if not message:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "message is required"},
            )
            return

        if not stream:
            result = AGENT_SERVICE.invoke_chat(session_id=session_id, message=message)
            self._send_json(HTTPStatus.OK, {"ok": True, **result})
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        self._send_sse("meta", {"session_id": session_id, "time": now_iso()})
        for event in AGENT_SERVICE.stream_chat(session_id=session_id, message=message):
            self._send_sse(event["event"], event["data"])
        self._send_sse("close", {"ok": True})

    def _handle_upload(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "upload must use multipart/form-data"},
            )
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
            },
            keep_blank_values=True,
        )

        file_items: list[Any] = []
        if "file" in form:
            file_field = form["file"]
            file_items = file_field if isinstance(file_field, list) else [file_field]
        elif "files" in form:
            file_field = form["files"]
            file_items = file_field if isinstance(file_field, list) else [file_field]

        if not file_items:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "missing file field"},
            )
            return

        saved: list[dict[str, Any]] = []
        for item in file_items:
            if not getattr(item, "filename", None):
                continue
            raw_bytes = item.file.read()
            record = AGENT_SERVICE.add_upload(
                file_name=item.filename,
                raw_bytes=raw_bytes,
            )
            saved.append(
                {
                    "file_name": record.file_name,
                    "stored_path": record.stored_path,
                    "uploaded_at": record.uploaded_at,
                    "text_length": record.text_length,
                }
            )

        if not saved:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "no valid file uploaded"},
            )
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "saved": saved,
                "knowledge_base": AGENT_SERVICE.kb.stats(),
                "mcp": AGENT_SERVICE.mcp_registry.status(),
            },
        )


def run_server(host: str = SERVER_HOST, port: int = SERVER_PORT) -> None:
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"Agent demo server running at http://{host}:{port}")
    print("GET  /health")
    print("POST /api/chat")
    print("POST /api/upload")
    server.serve_forever()

