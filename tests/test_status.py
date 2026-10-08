import io
import json
from pathlib import Path
import socket
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'api'))
from minecraft import query, read_exact, read_varint, varint


class StatusTests(unittest.TestCase):
    def test_status_exchange(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        expected = {'version': {'name': '1.21.11'}, 'players': {'online': 2, 'max': 10}}
        errors = []
        def server():
            try:
                with listener.accept()[0] as connection:
                    connection.settimeout(3)
                    with connection.makefile('rb') as stream:
                        packet = io.BytesIO(read_exact(stream, read_varint(stream)))
                        self.assertEqual(read_varint(packet), 0)
                        self.assertEqual(read_varint(packet), 0xffffffff)
                        host = read_exact(packet, read_varint(packet)).decode()
                        self.assertEqual(host, '127.0.0.1')
                        self.assertEqual(int.from_bytes(read_exact(packet, 2), 'big'), port)
                        self.assertEqual(read_varint(packet), 1)
                        self.assertEqual(read_exact(stream, 2), b'\x01\x00')
                        data = json.dumps(expected).encode()
                        response = b'\x00' + varint(len(data)) + data
                        # Fractionner la reponse pour tester les lectures partielles.
                        wire = varint(len(response)) + response
                        for byte in wire:
                            connection.sendall(bytes([byte]))
            except BaseException as error:
                errors.append(error)
        worker = threading.Thread(target=server, daemon=True)
        worker.start()
        try:
            self.assertEqual(query('127.0.0.1', port), expected)
            worker.join(4)
            self.assertFalse(worker.is_alive())
            if errors:
                raise errors[0]
        finally:
            listener.close()

    def test_truncated_packet(self):
        with self.assertRaises(ValueError):
            read_exact(io.BytesIO(b'abc'), 4)

    def test_invalid_varint(self):
        with self.assertRaises(ValueError):
            read_varint(io.BytesIO(b'\x80' * 5))


if __name__ == '__main__':
    unittest.main()
