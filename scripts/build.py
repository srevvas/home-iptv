from pathlib import Path
from urllib.request import Request, urlopen
import re

BASE = 'https://iptv-org.github.io/iptv/countries/'

COUNTRIES = [
    ('gr', 'Ελληνικά'),
    ('cy', 'Κυπριακά'),
    ('fr', 'Γαλλικά'),
    ('uk', 'Βρετανικά'),
    ('de', 'Γερμανικά'),
    ('it', 'Ιταλικά'),
    ('es', 'Ισπανικά'),
    ('us', 'Αμερικανικά'),
    ('al', 'Αλβανικά'),
]

DEST = Path(__file__).resolve().parents[1] / 'docs' / 'home.m3u'

EPG_IDS = {
    'AlphaTV.gr@SD': 'alpha',
}

def download(code):
    req = Request(BASE + code + '.m3u', headers={'User-Agent':'HomeIPTVPlaylist/1.0'})
    with urlopen(req, timeout=40) as response:
        return response.read().decode('utf-8-sig')

def entries(text):
    lines = text.splitlines()
    pending = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#EXTM3U'):
            continue
        if line.startswith('#EXTINF:'):
            pending = [line]
        elif pending and line.startswith('#'):
            pending.append(line)
        elif pending and line and not line.startswith('#'):
            yield pending, line
            pending = []


def main():
    output = ['#EXTM3U']
    counts = {}
    for code, label in COUNTRIES:
        source = download(code)
        count = 0
        for metadata, stream in entries(source):
            extinf = metadata[0]
                for old_id, new_id in EPG_IDS.items():
                extinf = extinf.replace(
                    f'tvg-id="{old_id}"',
                    f'tvg-id="{new_id}"'
                )
            if 'group-title="' in extinf:
                extinf = re.sub(r'group-title="[^"]*"', f'group-title="{label}"', extinf, count=1)
            else:
                extinf = re.sub(r'^(#EXTINF:[^,]*)(,)', lambda m: m.group(1) + f' group-title="{label}"' + m.group(2), extinf, count=1)
            output.extend([extinf, *metadata[1:], stream])
            count += 1
        if count == 0:
            raise RuntimeError(f'No channels found for {code}; refusing to overwrite playlist')
        counts[code] = count
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text('\n'.join(output) + '\n', encoding='utf-8')
    print('Created:', DEST)
    print('Channels by country:', counts)
    print('Total:', sum(counts.values()))

if __name__ == '__main__':
    main()
