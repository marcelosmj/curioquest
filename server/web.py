"""HTTP stand-in for 5th Planet's content CDN (content.5thplanetgames.com/pets_live/).

Serves, under /pets_live/:
  - files from server/content/web/ (Servers.xml, Version.xml, LandingScreen.xml, ...)
  - Server.xml generated per request, pointing the client at the ElectroServer port on
    whatever host name the client used to reach us (10.0.2.2 on the emulator, a LAN IP
    on a phone)
  - any game asset bundled in the original APK (assets/... paths), read from the APK,
    plus aliases (server/content/asset_aliases.json) that stand in for CDN-only art
Also answers "/" so the client's internet check (patched from www.google.com) passes.
Every request is logged; 404s show which lost CDN files the client still asks for.
"""
import json
import logging
import mimetypes
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

log = logging.getLogger("web")

CONTENT_PREFIX = "/pets_live/"

SERVER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<settings>
\t<connection host="{host}" port="{port}" transport="BinaryTCP" serverId="server1" />
</settings>
"""

CROSSDOMAIN_XML = """<?xml version="1.0"?>
<!DOCTYPE cross-domain-policy SYSTEM "http://www.adobe.com/xml/dtds/cross-domain-policy.dtd">
<cross-domain-policy>
\t<allow-access-from domain="*" />
\t<site-control permitted-cross-domain-policies="all"/>
\t<allow-http-request-headers-from domain="*" headers="*"/>
</cross-domain-policy>
"""


class ContentStore:
    def __init__(self, web_root, apk_path=None, aliases_path=None):
        self.web_root = Path(web_root)
        self._lock = threading.Lock()
        self.aliases = {}
        if aliases_path and Path(aliases_path).is_file():
            self.aliases = json.loads(Path(aliases_path).read_text(encoding="utf-8"))
        self._apk = None
        self._apk_names = set()
        if apk_path and Path(apk_path).is_file():
            self._apk = zipfile.ZipFile(apk_path)
            self._apk_names = set(self._apk.namelist())
        else:
            log.warning("APK original nao encontrado (%s): assets do jogo nao serao servidos", apk_path)

    def load(self, rel_path):
        rel = rel_path.lstrip("/")
        if not rel or ".." in rel.split("/"):
            return None
        local = self.web_root / rel
        if local.is_file():
            return local.read_bytes()
        source = self.aliases.get(rel, rel)
        apk_name = "assets/" + source
        if source.startswith("assets/") and apk_name in self._apk_names:
            with self._lock:
                return self._apk.read(apk_name)
        return None


def _make_handler(store, es_port):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CurioQuestOffline/1.0"

        def log_message(self, fmt, *args):
            pass

        def do_HEAD(self):
            self._respond(send_body=False)

        def do_GET(self):
            self._respond()

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            self._respond()

        def _respond(self, send_body=True):
            path = unquote(urlsplit(self.path).path)
            body, content_type = self._resolve(path)
            if body is None:
                log.warning("404 %s %s", self.command, path)
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            log.info("200 %s %s (%d bytes)", self.command, path, len(body))
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if send_body:
                self.wfile.write(body)

        def _resolve(self, path):
            if path in ("/crossdomain.xml", "/pets_live/crossdomain.xml"):
                return CROSSDOMAIN_XML.encode("utf-8"), "text/xml"
            if path in ("/CurioQuest.apk", "/curioquest.apk", "/app.apk"):
                apk = Path(__file__).resolve().parent.parent / "build" / "CurioQuest-offline-192.168.1.69.apk"
                if apk.is_file():
                    return apk.read_bytes(), "application/vnd.android.package-archive"
            # anything outside the game content (internet check, analytics the client still
            # calls) just gets an OK, so nothing fails for being offline
            if not path.startswith(CONTENT_PREFIX):
                return b"OK", "text/plain"
            rel = path[len(CONTENT_PREFIX):]
            if rel == "Server.xml":
                host = (self.headers.get("Host") or "127.0.0.1").rsplit(":", 1)[0]
                return SERVER_XML.format(host=host, port=es_port).encode("utf-8"), "text/xml"
            data = store.load(rel)
            if data is None:
                return None, None
            return data, mimetypes.guess_type(rel)[0] or "application/octet-stream"

    return Handler


def start_web_server(bind, port, store, es_port):
    httpd = ThreadingHTTPServer((bind, port), _make_handler(store, es_port))
    threading.Thread(target=httpd.serve_forever, name="web", daemon=True).start()
    log.info("conteudo HTTP em http://%s:%d%s", bind, port, CONTENT_PREFIX)
    return httpd
