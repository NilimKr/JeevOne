"""
api/websocket.py
================
Server-Sent Events (SSE) endpoint for real-time dashboard updates.

The dashboard polls this stream; when new data arrives the MQTT pipeline
pushes an update via a threading.Event.

SSE is simpler than WebSocket for unidirectional server→client push
and works natively in every browser without extra JS libraries.
"""

from __future__ import annotations

import json
import logging
import threading
import time

from flask import Blueprint, Response, stream_with_context

from app.pipeline_state import state_store

_log = logging.getLogger(__name__)

ws_bp = Blueprint("ws", __name__)

# Event fired by the pipeline each time new data is available
_update_event = threading.Event()


def notify_update() -> None:
    """Called by the pipeline thread when a new reading is processed."""
    _update_event.set()


@ws_bp.route("/stream")
def sse_stream() -> Response:
    """
    Server-Sent Events stream.
    Dashboard connects to this URL and receives JSON updates in real time.
    """

    def generate():
        _log.debug("SSE client connected")
        while True:
            # Wait for the pipeline to signal new data, or timeout after 15s
            fired = _update_event.wait(timeout=15.0)
            _update_event.clear()

            snap = state_store.snapshot()
            payload = snap.to_dict()
            payload["event_type"] = "update" if fired else "heartbeat"

            data = json.dumps(payload)
            yield f"data: {data}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
