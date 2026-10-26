"""Echanges binaires Minecraft et refus des reponses invalides."""
from contextlib import contextmanager
import io
import json
import socket
import struct
import threading
import unittest

from minecraft import query, read_exact, read_varint, varint


def status_packet(data):
    body = json.dumps(data).encode('utf-8')
    packet = b'\x00' + varint(len(body)) + body
    return varint(len(packet)) + packet


@contextmanager
def status_server(response):
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(4)
    port = listener.getsockname()[1]
    received = {}
    errors = []

    def serve():
        try:
            with listener.accept()[0] as connection:
                connection.settimeout(4)
                with connection.makefile('rb') as stream:
                    handshake = io.BytesIO(read_exact(stream, read_varint(stream)))
                    received['packet_id'] = read_varint(handshake)
                    received['protocol'] = read_varint(handshake)
                    received['host'] = read_exact(handshake, read_varint(handshake)).decode()
                    received['port'] = struct.unpack('>H', read_exact(handshake, 2))[0]
                    received['next_state'] = read_varint(handshake)
                    received['request'] = read_exact(stream, 2)
                    # Plusieurs envois pour ne pas supposer qu'un paquet arrive d'un bloc.
                    midpoint = len(response) // 2
                    connection.sendall(response[:midpoint])
                    connection.sendall(response[midpoint:])
        except Exception as error:
            errors.append(error)

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        yield port, received
    finally:
        worker.join(timeout=5)
        listener.close()
        if worker.is_alive():
            raise AssertionError('Le serveur simule ne termine pas')
        if errors:
            raise errors[0]


class MinecraftTests(unittest.TestCase):
    def test_varint_boundaries(self):
        for value in (0, 127, 128, 25565, 0xffffffff):
            with self.subTest(value=value):
                self.assertEqual(read_varint(io.BytesIO(varint(value))), value)

    def test_invalid_or_truncated_varint(self):
        for data in (b'', b'\x80', b'\x80' * 5, b'\xff' * 4 + b'\x7f'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                read_varint(io.BytesIO(data))

    def test_truncated_data(self):
        with self.assertRaises(ValueError):
            read_exact(io.BytesIO(b'ab'), 3)

    def test_status_and_handshake(self):
        expected = {'players': {'online': 3, 'max': 10}, 'version': {'name': 'test'}}
        with status_server(status_packet(expected)) as (port, received):
            self.assertEqual(query('127.0.0.1', port), expected)
        self.assertEqual(received, {
            'packet_id': 0, 'protocol': 0xffffffff, 'host': '127.0.0.1',
            'port': port, 'next_state': 1, 'request': b'\x01\x00',
        })

    def test_invalid_player_count(self):
        for count in (-1, True, '2'):
            data = {'players': {'online': count, 'max': 10}, 'version': {'name': 'test'}}
            with self.subTest(count=count), status_server(status_packet(data)) as (port, _):
                with self.assertRaises(ValueError):
                    query('127.0.0.1', port)

    def test_missing_version(self):
        data = {'players': {'online': 0, 'max': 10}, 'version': {}}
        with status_server(status_packet(data)) as (port, _), self.assertRaises(ValueError):
            query('127.0.0.1', port)

    def test_oversized_or_incomplete_response(self):
        for response in (varint(1048577), b'\x05\x00'):
            with self.subTest(response=response), status_server(response) as (port, _):
                with self.assertRaises(ValueError):
                    query('127.0.0.1', port)


if __name__ == '__main__':
    unittest.main()
