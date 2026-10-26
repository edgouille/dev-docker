"""API HTTP exposant l'etat du serveur Minecraft."""
import json
import os
import queue
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from minecraft import query


def query_status():
    output = queue.Queue(maxsize=1)
    def probe():
        try:
            output.put(query(os.getenv('GAME_HOST', 'game'), int(os.getenv('GAME_PORT', '25565'))))
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            output.put(None)
    threading.Thread(target=probe, daemon=True).start()
    try:
        result = output.get(timeout=3)
    except queue.Empty:
        result = None
    return {
        'name': os.getenv('SERVER_NAME', 'Minecraft - TP Docker'),
        'address': os.getenv('PUBLIC_GAME_ADDRESS', 'localhost:25565'),
        'online': result is not None,
        'players': result['players'].get('online', 0) if result else None,
        'max_players': result['players'].get('max', 0) if result else None,
        'version': result['version'].get('name') if result else None,
    }


status_lock = threading.Lock()
cached_status = None
cache_deadline = 0


def status():
    global cached_status, cache_deadline
    # Un seul controle du jeu a la fois ; les appels rapproches partagent le resultat.
    with status_lock:
        if time.monotonic() >= cache_deadline:
            cached_status = query_status()
            cache_deadline = time.monotonic() + 1
        return cached_status


class BoundedHTTPServer(ThreadingHTTPServer):
    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    # Eviter de divulguer la version Python via l'en-tete Server.
    server_version = 'TP-API'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/health':
            code, data = 200, {'status': 'ok'}
        elif path in ('/', '/api/status'):
            code, data = 200, status()
        else:
            code, data = 404, {'error': 'Route inconnue'}
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    server = BoundedHTTPServer(('0.0.0.0', int(os.getenv('PORT', '5000'))), Handler)
    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
