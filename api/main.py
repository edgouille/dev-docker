"""API HTTP exposant l'etat du serveur Minecraft."""
import json
import os
import queue
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from minecraft import query


def status():
    output = queue.Queue(maxsize=1)
    def probe():
        try:
            output.put(query(os.getenv('GAME_HOST', 'game'), int(os.getenv('GAME_PORT', '25565'))))
        except (OSError, ValueError, KeyError):
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


class Handler(BaseHTTPRequestHandler):
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
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer(('0.0.0.0', int(os.getenv('PORT', '5000'))), Handler)
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
