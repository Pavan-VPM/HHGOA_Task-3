#!/usr/bin/env python3
"""
Lightweight HTTP Server and API for Face Scan -> Blockchain Verification Frontend.
Provides REST endpoints to run pipeline stages, upload scans, re-verify on-chain, and test tampering.
"""

import json
import mimetypes
import os
import sys
import base64
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any

from main import run_pipeline, DEFAULT_STATE_FILE
from blockchain.evm_client import EVMClient
from pipeline.verifier import Verifier
from pipeline.face_engine import FaceEngine

PORT = 3000
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")


class PipelineHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        # Serve sample images
        if self.path.startswith("/samples/"):
            filename = os.path.basename(self.path)
            file_path = os.path.join(SAMPLES_DIR, filename)
            if os.path.exists(file_path):
                self.send_response(200)
                content_type, _ = mimetypes.guess_type(file_path)
                self.send_header("Content-Type", content_type or "image/jpeg")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "Sample image not found")
                return

        # API: list samples
        if self.path == "/api/samples":
            samples = []
            if os.path.exists(SAMPLES_DIR):
                for f in sorted(os.listdir(SAMPLES_DIR)):
                    if f.endswith((".jpg", ".png", ".jpeg")):
                        samples.append({
                            "name": f,
                            "url": f"/samples/{f}",
                            "path": os.path.join(SAMPLES_DIR, f),
                        })
            self._send_json({"samples": samples})
            return

        # API: get latest blockchain state
        if self.path == "/api/state":
            if os.path.exists(DEFAULT_STATE_FILE):
                with open(DEFAULT_STATE_FILE, "r") as f:
                    state = json.load(f)
                self._send_json({"status": "success", "state": state})
            else:
                self._send_json({"status": "empty", "state": None})
            return

        # Fallback to serving web directory (index.html, style.css, app.js)
        return super().do_GET()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"

        try:
            payload = json.loads(post_body.decode("utf-8"))
        except Exception:
            payload = {}

        # API: Run pipeline
        if self.path == "/api/run":
            image_source = payload.get("image", "samples/test_face_1.jpg")
            query = payload.get("query", "Satya Nadella")
            mode = payload.get("mode", "local")

            # Handle base64 image upload if provided
            if image_source.startswith("data:image"):
                header, base64_data = image_source.split(",", 1)
                img_bytes = base64.b64decode(base64_data)
                upload_path = os.path.join(SAMPLES_DIR, "uploaded_scan.jpg")
                with open(upload_path, "wb") as f:
                    f.write(img_bytes)
                image_source = upload_path

            try:
                result = run_pipeline(
                    image_path=image_source,
                    search_query=query,
                    blockchain_mode=mode,
                )
                state = result["pipeline_state"]
                self._send_json({
                    "status": "success",
                    "state": state,
                })
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, code=500)
            return

        # API: Re-verify against blockchain
        if self.path == "/api/verify":
            if not os.path.exists(DEFAULT_STATE_FILE):
                self._send_json({"status": "error", "message": "No pipeline state found. Run pipeline first."}, code=400)
                return

            with open(DEFAULT_STATE_FILE, "r") as f:
                state = json.load(f)

            evm_client = EVMClient(
                mode=state.get("chain_mode", "local"),
                contract_address=state["contract_address"],
            )
            verifier = Verifier(evm_client)
            ver_res = verifier.verify_pipeline_result(
                face_hash=state["face_hash"],
                post_data=state["post_data"],
                saved_state=state,
            )
            self._send_json({"status": "success", "verification": ver_res})
            return

        # API: Run Tamper Demonstration
        if self.path == "/api/tamper":
            if not os.path.exists(DEFAULT_STATE_FILE):
                self._send_json({"status": "error", "message": "No pipeline state found. Run pipeline first."}, code=400)
                return

            with open(DEFAULT_STATE_FILE, "r") as f:
                state = json.load(f)

            evm_client = EVMClient(
                mode=state.get("chain_mode", "local"),
                contract_address=state["contract_address"],
            )
            verifier = Verifier(evm_client)
            tamper_report = verifier.run_tamper_demonstration(
                face_hash=state["face_hash"],
                post_data=state["post_data"],
            )
            self._send_json({"status": "success", "report": tamper_report})
            return

        self.send_error(404, "Endpoint not found")

    def _send_json(self, data: Dict[str, Any], code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def run_server(port: int = PORT):
    server = HTTPServer(("0.0.0.0", port), PipelineHandler)
    print(f"✨ Minimal UI Web Dashboard running at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(p)
