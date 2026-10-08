"""Telecharge les fichiers officiels necessaires aux builds."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent / '.docker'
FILES = [
    ('alpine.tar.gz', 'https://dl-cdn.alpinelinux.org/alpine/v3.23/releases/x86_64/alpine-minirootfs-3.23.6-x86_64.tar.gz', 'sha256', '6fc0e3639a1c01f156970d7626aab90bc90697117069dbc39ad880b84efa319a'),
    ('server.jar', 'https://piston-data.mojang.com/v1/objects/64bb6d763bed0a9f1d632ec347938594144943ed/server.jar', 'sha1', '64bb6d763bed0a9f1d632ec347938594144943ed'),
]

def prepare():
    ROOT.mkdir(exist_ok=True)
    for name, url, algorithm, expected in FILES:
        path = ROOT / name
        if not path.exists():
            print(f'Telechargement : {name}', flush=True)
            temporary = ROOT / (name + '.part')
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if hashlib.new(algorithm, temporary.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f'Empreinte incorrecte : {temporary}')
            temporary.replace(path)
        if hashlib.new(algorithm, path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Empreinte incorrecte : {path}')
        print(f'{name} : empreinte verifiee', flush=True)

if __name__ == '__main__':
    prepare()
