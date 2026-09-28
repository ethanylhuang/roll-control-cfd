"""Read only small diagnostic members from a cloud ZIP using HTTP ranges."""
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from cloud_study import API, PID, HERE


class Remote(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos, self.received = url, 0, 0
        with urllib.request.urlopen(urllib.request.Request(url, headers={'X-API-KEY': API.key, 'Range': 'bytes=0-0'}), timeout=30) as r:
            if r.status != 206:
                raise RuntimeError('Server does not support partial downloads; no full download attempted')
            self.size = int(r.headers['Content-Range'].split('/')[-1])
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos+offset if whence == 1 else self.size+offset
        return self.pos
    def read(self, n=-1):
        n = min(self.size-self.pos, n if n >= 0 else self.size-self.pos)
        if n <= 0: return b''
        if self.received+n > 16*1024**2: raise RuntimeError('Diagnostic download exceeds 16 MiB guard')
        req = urllib.request.Request(self.url, headers={'X-API-KEY': API.key, 'Range': f'bytes={self.pos}-{self.pos+n-1}'})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 206: raise RuntimeError('Range not honored')
            data = r.read(n)
        self.pos += len(data); self.received += len(data)
        return data


def main(tag):
    folder = HERE/f'cloud/{tag}'
    sid = json.loads((HERE/f'ss_{tag}_copy.json').read_text())['simulationId']
    rid = json.loads((folder/'run.json').read_text())['runId']
    items = API.run_results(PID, sid, rid)
    url = next(i for i in items if i.get('category') == 'SOLUTION')['download']['url']
    stream = Remote(url)
    with zipfile.ZipFile(stream) as archive:
        index = [dict(name=i.filename, size=i.file_size) for i in archive.infolist()]
        (folder/'archive_index.json').write_text(json.dumps(index, indent=2))
        wanted = [i for i in archive.infolist() if i.file_size < 8*1024**2 and
                  ('log' in Path(i.filename).name.lower() or i.filename.endswith('/0/U') or 'inlet' in i.filename.lower())]
        print('Selected', [(i.filename, i.file_size) for i in wanted])
        dest = folder/'diagnostic_files'; dest.mkdir(exist_ok=True)
        for item in wanted:
            (dest/item.filename.replace('/', '__')).write_bytes(archive.read(item))
    print('Downloaded bytes', stream.received)


if __name__ == '__main__':
    main(sys.argv[1])
