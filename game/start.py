"""Configure Minecraft et remplace ce processus par Java."""
import os
from pathlib import Path
import re
import sys

def main():
    if os.getenv('EULA', 'false').lower() != 'true':
        print('Lis https://www.minecraft.net/en-us/eula puis configure EULA=true si tu acceptes.', flush=True)
        return 1
    port = int(os.getenv('GAME_PORT', '25565'))
    players = int(os.getenv('MAX_PLAYERS', '10'))
    if not 1 <= port <= 65535 or players < 1:
        raise ValueError('Port ou nombre de joueurs invalide')
    xms, xmx = os.getenv('JAVA_XMS', '512M'), os.getenv('JAVA_XMX', '1536M')
    if not all(re.fullmatch(r'[1-9][0-9]*[mMgG]', value) for value in (xms, xmx)):
        raise ValueError('Tailles Java invalides : exemple 512M ou 2G')
    Path('eula.txt').write_text('eula=true\n')
    updates = {
        'server-port': str(port), 'max-players': str(players),
        'motd': os.getenv('SERVER_NAME', 'Minecraft - TP Docker'),
        'online-mode': 'true', 'enable-rcon': 'false', 'enable-status': 'true',
        'view-distance': '6', 'simulation-distance': '4',
    }
    properties = Path('server.properties')
    lines = properties.read_text().splitlines() if properties.exists() else []
    lines = [line for line in lines if line.split('=', 1)[0].strip() not in updates]
    def escape(value):
        encoded = value.encode('utf-16-be')
        return ''.join(f'\\u{int.from_bytes(encoded[i:i+2], "big"):04x}' for i in range(0, len(encoded), 2))
    lines += [f'{key}={escape(value)}' for key, value in updates.items()]
    properties.write_text('\n'.join(lines) + '\n')
    os.execvp('java', ['java', f'-Xms{xms}', f'-Xmx{xmx}', '-jar', '/app/server.jar', 'nogui'])

if __name__ == '__main__':
    sys.exit(main())
