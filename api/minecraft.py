"""Protocole Status de Minecraft Java, sans dependance."""
import io
import json
import socket
import struct
import sys

def varint(value):
    value &= 0xffffffff
    result = bytearray()
    while True:
        byte = value & 0x7f
        value >>= 7
        result.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(result)

def read_exact(stream, count):
    data = bytearray()
    while len(data) < count:
        chunk = stream.read(count - len(data))
        if not chunk:
            raise ValueError('Reponse Minecraft incomplete')
        data.extend(chunk)
    return bytes(data)

def read_varint(stream):
    result = 0
    for shift in range(0, 35, 7):
        byte = read_exact(stream, 1)[0]
        result |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return result
    raise ValueError('VarInt invalide')

def query(host, port):
    address = host.encode('utf-8')
    handshake = b'\x00' + varint(-1) + varint(len(address)) + address + struct.pack('>H', port) + b'\x01'
    with socket.create_connection((host, port), timeout=2) as connection:
        connection.settimeout(2)
        connection.sendall(varint(len(handshake)) + handshake + b'\x01\x00')
        with connection.makefile('rb') as stream:
            size = read_varint(stream)
            if not 1 <= size <= 1048576:
                raise ValueError('Taille de reponse invalide')
            packet = io.BytesIO(read_exact(stream, size))
            if read_varint(packet) != 0:
                raise ValueError('Paquet inattendu')
            length = read_varint(packet)
            if length > size:
                raise ValueError('JSON trop long')
            result = json.loads(read_exact(packet, length))
            if not isinstance(result, dict) or not isinstance(result.get('players'), dict) or not isinstance(result.get('version'), dict):
                raise ValueError('Etat Minecraft invalide')
            return result

if __name__ == '__main__':
    query(sys.argv[1], int(sys.argv[2]))
