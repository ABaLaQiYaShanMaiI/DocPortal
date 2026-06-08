"""Local HTTP server manager for serving generated portals."""

import threading
import webbrowser
import http.server
import socketserver
from functools import partial


class ServerManager:
    """Manages a background HTTP server for serving generated portal files."""

    def __init__(self, on_status_change=None):
        self._httpd = None
        self._thread = None
        self._port = 8080
        self._root = None
        self._on_status_change = on_status_change

    @property
    def is_running(self) -> bool:
        return self._httpd is not None

    @property
    def port(self) -> int:
        return self._port  # type: ignore[no-any-return]

    @port.setter
    def port(self, value: int):
        self._port = value

    @property
    def root(self):
        return self._root

    @property
    def url(self) -> str:
        return f"http://localhost:{self._port}"

    def start(self, directory, port=None, max_attempts=10):
        """Start HTTP server in a daemon thread. Returns True on success."""
        if self._httpd is not None:
            return True

        if port is not None:
            self._port = port

        actual_port = self._port
        socketserver.TCPServer.allow_reuse_address = True

        for _ in range(max_attempts):
            try:
                handler = partial(http.server.SimpleHTTPRequestHandler, directory=directory)
                self._httpd = socketserver.TCPServer(("", actual_port), handler)
                break
            except OSError:
                actual_port += 1
                continue
        else:
            return False

        self._port = actual_port
        self._root = directory
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True, name="HTTPServer"
        )
        self._thread.start()

        if self._on_status_change:
            self._on_status_change(True)

        webbrowser.open(f"http://localhost:{actual_port}/index.html")
        return True

    def stop(self):
        """Stop the HTTP server if running."""
        if self._httpd:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
            self._httpd = None
            self._thread = None
            self._root = None
        if self._on_status_change:
            self._on_status_change(False)

    def copy_url_to_clipboard(self, root):
        """Copy server URL to tkinter root's clipboard."""
        root.clipboard_clear()
        root.clipboard_append(self.url)