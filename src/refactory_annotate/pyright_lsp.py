"""Pyright Language Server Protocol client for type inference queries."""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any


class PyrightClient:
    """Minimal Pyright LSP client.

    Launches ``pyright-langserver`` as a subprocess, communicates via
    JSON-RPC over stdio (Content-Length framed), and supports hover
    queries for inferring type annotations.

    Usage::

        with PyrightClient(root=Path(".")) as client:
            client.open_file(Path("src/module.py"))
            hover_text = client.hover(Path("src/module.py"), line=0, col=4)
    """

    #: Seconds to wait for ``textDocument/publishDiagnostics`` after opening.
    ANALYSIS_WAIT: float = 8.0
    #: Seconds to wait for a hover response.
    REQUEST_TIMEOUT: float = 10.0

    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or Path.cwd()).resolve()
        self._proc: subprocess.Popen[bytes] | None = None
        self._req_id = 0
        self._lock = threading.Lock()
        self._responses: dict[int, dict[str, Any]] = {}
        self._response_events: dict[int, threading.Event] = {}
        self._diag_events: dict[str, threading.Event] = {}
        self._running = False
        self._reader_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Context-manager interface
    # ------------------------------------------------------------------

    def __enter__(self) -> PyrightClient:
        self._start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_file(self, path: Path, wait_for_analysis: bool = True) -> None:
        """Open a file in the language server and wait for analysis.

        Args:
            path: Absolute path to the Python file.
            wait_for_analysis: Whether to block until pyright emits
                ``textDocument/publishDiagnostics`` for this file.
        """
        uri = _path_to_uri(path)
        content = path.read_text(encoding="utf-8")

        diag_event = threading.Event()
        with self._lock:
            self._diag_events[uri] = diag_event

        self._notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                    "text": content,
                }
            },
        )

        if wait_for_analysis:
            diag_event.wait(timeout=self.ANALYSIS_WAIT)

    def hover(self, path: Path, line: int, col: int) -> str | None:
        """Return hover text at *line*, *col* (both 0-indexed).

        Returns ``None`` if pyright has no information at that position.
        """
        uri = _path_to_uri(path)
        rid = self._request(
            "textDocument/hover",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": col},
            },
        )

        with self._lock:
            event = self._response_events.get(rid)
        if event is None or not event.wait(timeout=self.REQUEST_TIMEOUT):
            return None

        with self._lock:
            resp = self._responses.get(rid)
        if not resp or not resp.get("result"):
            return None

        contents = resp["result"].get("contents", {})
        if isinstance(contents, dict):
            return contents.get("value")
        if isinstance(contents, str):
            return contents
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start(self) -> None:
        self._proc = subprocess.Popen(
            ["pyright-langserver", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._running = True
        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True, name="pyright-lsp-reader"
        )
        self._reader_thread.start()

        # LSP handshake
        self._request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": _path_to_uri(self._root),
                "capabilities": {},
            },
        )
        # Wait briefly for the initialize response so the server is ready.
        with self._lock:
            event = self._response_events.get(self._req_id)
        if event:
            event.wait(timeout=5.0)
        self._notify("initialized", {})

    def _stop(self) -> None:
        if not self._running:
            return
        self._running = False
        try:
            rid = self._request("shutdown", {})
            with self._lock:
                event = self._response_events.get(rid)
            if event:
                event.wait(timeout=3.0)
            self._notify("exit", {})
        except Exception:
            pass
        if self._proc:
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.terminate()

    def _request(self, method: str, params: dict[str, Any]) -> int:
        with self._lock:
            self._req_id += 1
            rid = self._req_id
            self._response_events[rid] = threading.Event()
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return rid

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _send(self, msg: dict[str, Any]) -> None:
        if self._proc and self._proc.stdin:
            body = json.dumps(msg)
            frame = f"Content-Length: {len(body)}\r\n\r\n{body}".encode()
            self._proc.stdin.write(frame)
            self._proc.stdin.flush()

    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        while self._running:
            try:
                # Read headers
                headers = b""
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        return
                    headers += line
                    if line == b"\r\n":
                        break

                content_length = 0
                for header_line in headers.split(b"\r\n"):
                    if header_line.lower().startswith(b"content-length:"):
                        content_length = int(header_line.split(b":", 1)[1].strip())

                body = proc.stdout.read(content_length)
                msg: dict[str, Any] = json.loads(body)

                if "id" in msg and ("result" in msg or "error" in msg):
                    # Response to a request
                    with self._lock:
                        self._responses[msg["id"]] = msg
                        event = self._response_events.get(msg["id"])
                    if event:
                        event.set()
                elif msg.get("method") == "textDocument/publishDiagnostics":
                    uri = msg.get("params", {}).get("uri", "")
                    with self._lock:
                        event = self._diag_events.get(uri)
                    if event:
                        event.set()
            except Exception:
                if self._running:
                    continue
                break


# ---------------------------------------------------------------------------
# Type-string parsing helpers
# ---------------------------------------------------------------------------

def parse_hover_return_type(hover_text: str) -> str | None:
    """Extract the return type from a function/method hover text.

    Pyright hover for functions looks like::

        (function) def add(
            x: int,
            y: int
        ) -> int

    or on one line::

        (function) def add(x: int, y: int) -> int

    Returns the return type string, or ``None`` if it cannot be determined
    or the type is ``Unknown`` (not inferrable).
    """
    if not hover_text.startswith(("(function)", "(method)")):
        return None

    # Find the last "-> " in the hover text
    idx = hover_text.rfind("-> ")
    if idx == -1:
        return None

    ret_type = hover_text[idx + 3 :].strip().rstrip("`").strip()
    if not ret_type:
        return None

    return None if _contains_unknown(ret_type) else ret_type


def parse_hover_param_type(hover_text: str) -> str | None:
    """Extract the type from a parameter hover text.

    Pyright hover for parameters looks like::

        (parameter) x: int

    Returns the type string, or ``None`` if it cannot be determined
    or the type is ``Unknown``.
    """
    if not hover_text.startswith("(parameter)"):
        return None

    # "(parameter) name: type"
    colon_idx = hover_text.find(": ")
    if colon_idx == -1:
        return None

    type_str = hover_text[colon_idx + 2 :].strip().rstrip("`").strip()
    if not type_str:
        return None

    return None if _contains_unknown(type_str) else type_str


def _contains_unknown(type_str: str) -> bool:
    """Return True if *type_str* contains an uninferrable type marker."""
    # Match "Unknown" as a whole word so we don't reject e.g. "UnknownError"
    return bool(re.search(r"\bUnknown\b", type_str))


def collect_required_imports(type_strings: list[str]) -> list[str]:
    """Return typing module names that must be imported for *type_strings*.

    Examples::

        ["int | None", "list[str]"]  ->  []
        ["Any", "Callable[[int], str]"]  ->  ["Any", "Callable"]
    """
    # Names exported by typing that pyright uses in hover output.
    # Built-in generics (list, dict, tuple, set, type) and union syntax
    # (X | Y) do not require imports for Python 3.11+.
    _TYPING_NAMES = {
        "Any",
        "Callable",
        "ClassVar",
        "Final",
        "Generator",
        "Iterable",
        "Iterator",
        "Literal",
        "LiteralString",
        "Never",
        "Optional",
        "Protocol",
        "Self",
        "Sequence",
        "TypeVar",
        "TypeAlias",
        "Union",
        "overload",
        "cast",
    }

    needed: set[str] = set()
    for ts in type_strings:
        for name in _TYPING_NAMES:
            if re.search(rf"\b{re.escape(name)}\b", ts):
                needed.add(name)
    return sorted(needed)


def _path_to_uri(path: Path) -> str:
    """Convert an absolute Path to a ``file://`` URI."""
    return path.as_uri()
