"""Pack a static Pages preview. Password is read from stdin, never persisted."""
import argparse
import base64
import getpass
import hashlib
import json
import mimetypes
import os
import re
import shutil
import stat
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TEMPLATES = Path(__file__).resolve().parent
ALLOWED = {'.html', '.htm', '.css', '.js', '.mjs', '.webp', '.jpg', '.jpeg', '.avif', '.png', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.txt', '.pdf', '.mp4', '.webm', '.json'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--base', default='/czarter1/')
    parser.add_argument('--login', default='admin')
    args = parser.parse_args()
    src, dst = args.source.resolve(), args.output.resolve()
    if not re.fullmatch(r'/(?:[a-zA-Z0-9_-]+/)*', args.base):
        parser.error('Invalid project path')
    if src == dst or dst.is_relative_to(src) or src.is_relative_to(dst) or not (src/'index.html').is_file():
        parser.error('Choose a separate input folder containing index.html')
    if dst.exists() and (not dst.is_dir() or any(dst.iterdir())):
        parser.error('Output directory must be new or empty')
    password = getpass.getpass() if sys.stdin.isatty() else sys.stdin.readline().rstrip('\r\n')
    if not password:
        parser.error('Empty password')
    salt = os.urandom(16)
    iterations = 600000
    key = hashlib.pbkdf2_hmac('sha256', (args.login+'\0'+password).encode(), salt, iterations, 32)
    cipher = AESGCM(key)
    def seal(path, data):
        iv = os.urandom(12)
        return iv + cipher.encrypt(iv, data, path.encode())
    out = dst/'_gate'
    blobs = out/'data'
    blobs.mkdir(parents=True)
    gate = (TEMPLATES/'gate.html').read_text().replace('__BASE__',args.base)
    (out/'locked.html').write_text(gate)
    (dst/'404.html').write_text(gate)
    (dst/'.nojekyll').touch()
    (dst/'robots.txt').write_text('User-agent: *\nDisallow: '+args.base+'\n')
    entries = []
    for f in sorted(src.rglob('*')):
        path = f.relative_to(src).as_posix()
        if f.is_symlink() or any(seg.startswith('.') for seg in f.relative_to(src).parts):
            raise ValueError('Unexpected hidden path or symlink: '+path)
        if f.is_dir():
            continue
        if not stat.S_ISREG(f.stat().st_mode) or f.suffix.lower() not in ALLOWED or path.split('/')[0] in {'_gate','preview-sw.js'}:
            raise ValueError('Unexpected input type or reserved path: '+path)
        data = f.read_bytes()
        mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        if f.suffix.lower() in {'.html','.htm'}:
            html, count = re.subn(r'<head([^>]*)>', lambda m: m.group()+'<script src="'+args.base+'_gate/session.js"></script>', data.decode(), count=1, flags=re.I)
            if not count:
                raise ValueError('Missing head in '+path)
            data = html.encode()
            dest = dst/path
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(gate)
        if mime.startswith('text/'):
            mime += '; charset=utf-8'
        encrypted = seal(path, data)
        blob_name = hashlib.sha256(encrypted).hexdigest()+'.bin'
        (blobs/blob_name).write_bytes(encrypted)
        entries.append([path, [blob_name,mime,len(data)]])
    index = seal('@preview-index', json.dumps(entries, ensure_ascii=False, separators=(',',':')).encode())
    name = 'index-'+hashlib.sha256(index).hexdigest()+'.bin'
    (out/name).write_bytes(index)
    (out/'settings.json').write_text(json.dumps({'salt':base64.b64encode(salt).decode(),'iterations':iterations}))
    (dst/'preview-sw.js').write_text((TEMPLATES/'worker.js').read_text().replace('__INDEX__',name))
    for public in ['login.css','login.js','session.js']:
        shutil.copyfile(TEMPLATES/public, out/public)
    print(f'Packed {len(entries)} encrypted files into {dst}')

if __name__ == '__main__':
    main()
