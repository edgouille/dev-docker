"""Reponses HTTP de l'API, sans Minecraft et sans acces reseau externe."""
from contextlib import contextmanager
import json
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

import main as api


@contextmanager
def running_api():
    server = api.BoundedHTTPServer(('127.0.0.1', 0), api.Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def get_json(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as response:
        return response.status, json.load(response), response.headers


class APITests(unittest.TestCase):
    def setUp(self):
        api.cached_status = None
        api.cache_deadline = 0

    def test_health_does_not_contact_minecraft(self):
        with patch.object(api, 'query') as probe, running_api() as base:
            code, data, _ = get_json(base, '/health')
        self.assertEqual(code, 200)
        self.assertEqual(data, {'status': 'ok'})
        probe.assert_not_called()

    def test_status_online_and_cached(self):
        reply = {'players': {'online': 2, 'max': 10}, 'version': {'name': 'test-version'}}
        with patch.object(api, 'query', return_value=reply) as probe, running_api() as base:
            code, data, headers = get_json(base, '/api/status')
            _, second, _ = get_json(base, '/api/status')
        self.assertEqual(code, 200)
        self.assertTrue(data['online'])
        self.assertEqual(data['players'], 2)
        self.assertEqual(data['max_players'], 10)
        self.assertEqual(data['version'], 'test-version')
        self.assertEqual(data, second)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertNotIn('Python/', headers['Server'])
        probe.assert_called_once()

    def test_unavailable_game_returns_offline_instead_of_http_error(self):
        with patch.object(api, 'query', side_effect=ConnectionRefusedError), running_api() as base:
            code, data, _ = get_json(base, '/api/status')
        self.assertEqual(code, 200)
        self.assertFalse(data['online'])
        self.assertIsNone(data['players'])
        self.assertIsNone(data['version'])

    def test_invalid_game_response_returns_offline(self):
        with patch.object(api, 'query', side_effect=ValueError('Paquet invalide')), running_api() as base:
            _, data, _ = get_json(base, '/api/status')
        self.assertFalse(data['online'])

    def test_unknown_route_returns_404(self):
        with running_api() as base:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                get_json(base, '/inconnu')
            self.assertEqual(caught.exception.code, 404)
            self.assertEqual(json.load(caught.exception), {'error': 'Route inconnue'})


if __name__ == '__main__':
    unittest.main()
