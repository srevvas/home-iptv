from pathlib import Path
from urllib.request import Request, urlopen
import gzip
import difflib
import re
import unicodedata
import xml.etree.ElementTree as ET

BASE = 'https://iptv-org.github.io/iptv/countries/'
EPG_URL = 'https://ext.greektv.app/epg/epg.xml.gz'
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

# Verified mapping; automatic matches supplement these rules.
EPG_IDS = {
    'AlphaTV.gr@SD': 'alpha',
    'AcheloosTV.gr@SD': 'axelwostv',
    'AeolosTV.gr@SD': 'aeolos',
    'AlertTV.gr@SD': 'alert',
    'BlueSkyTV.gr@SD': 'bluesky',
    'EgnatiaTV.gr@SD': 'egnatia',
    'EpilogesTV.gr@SD': 'tileepiloges',
    'IonianTV.gr@SD': 'ionian',
    'LepantoTV.gr@SD': 'lepanto',
    'SkaiTV.gr@SD': 'skai',
    'Telekriti.gr@SD': 'thlekriti',
    'ThrakiNetTV.gr@SD': 'thrakinet',
    'TVCreta.gr@SD': 'creta',
    'VerginaTV.gr@SD': 'berginatv',
    'ANT1Cyprus.cy@SD': 'ant1cy',
    'SigmaTV.cy@SD': 'sigma',
    'VouliTV.cy@SD': 'vouli',
}


def fetch(url):
    req = Request(url, headers={'User-Agent': 'HomeIPTVPlaylist/1.0'})
    with urlopen(req, timeout=60) as response:
        return response.read()


def normalize(value):
    value = unicodedata.normalize('NFKD', value)
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', value.casefold())


def epg_index():
    data = fetch(EPG_URL)
    if data.startswith(b'\x1f\x8b'):
        data = gzip.decompress(data)
    root = ET.fromstring(data)
    index = {}
    ambiguous = set()
    programme_ids = {node.get('channel') for node in root.findall('programme')}
    for channel in root.findall('channel'):
        channel_id = channel.get('id')
        if not channel_id or channel_id not in programme_ids:
            continue
        candidates = [channel_id]
        candidates.extend(node.text for node in channel.findall('display-name') if node.text)
        for candidate in candidates:
            key = normalize(candidate)
            if not key:
                continue
            if key in index and index[key] != channel_id:
                ambiguous.add(key)
            else:
                index[key] = channel_id
    for key in ambiguous:
        index.pop(key, None)
    print(f'EPG channel entries: {len(root.findall("channel"))}; unique lookup keys: {len(index)}')
    return index, programme_ids


def entries(text):
    pending = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#EXTM3U'):
            continue
        if line.startswith('#EXTINF:'):
            pending = [line]
        elif pending and line.startswith('#'):
            pending.append(line)
        elif pending and not line.startswith('#'):
            yield pending, line
            pending = []


def main():
    # If EPG is temporarily unreachable, keep the playlist build working.
    try:
        lookup, programme_ids = epg_index()
    except Exception as exc:
        print(f'WARNING: EPG unavailable ({exc}); using verified mappings only')
        lookup = {}
        programme_ids = None

    output = ['#EXTM3U']
    counts = {}
    matched = 0
    unmatched = []
    for code, label in COUNTRIES:
        source = fetch(BASE + code + '.m3u').decode('utf-8-sig')
        count = 0
        for metadata, stream in entries(source):
            extinf = metadata[0]
            if code in ('gr', 'cy'):
                id_match = re.search(r'tvg-id="([^"]*)"', extinf)
                old_id = id_match.group(1) if id_match else ''
                title = extinf.split(',', 1)[-1]
                title = re.sub(r'\s*\([^)]*\)|\s*\[[^]]*\]', '', title).strip()
                # Avoid guessing from a generic word in a longer channel name.
                candidates = [normalize(old_id.split('@', 1)[0].split('.', 1)[0]), normalize(title)]
                new_id = EPG_IDS.get(old_id)
                # When EPG is available, require actual programme entries.
                if new_id and programme_ids is not None and new_id not in programme_ids:
                    print(f'WARNING: no programmes for mapping {old_id} -> {new_id}')
                    new_id = None
                if not new_id:
                    matches = {lookup[key] for key in candidates if key in lookup}
                    if len(matches) == 1:
                        new_id = matches.pop()
                if new_id:
                    if id_match:
                        extinf = extinf.replace(f'tvg-id="{old_id}"', f'tvg-id="{new_id}"', 1)
                    else:
                        extinf = extinf.replace('#EXTINF:', f'#EXTINF: tvg-id="{new_id}"', 1)
                    matched += 1
                else:
                    unmatched.append(f'{code}: {title} [{old_id}]')
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
    print('Greek/Cypriot EPG matches:', matched)
    print('Greek/Cypriot unmatched:', len(unmatched))
    for item in unmatched:
        print('UNMATCHED:', item)
        channel_name = item.split(': ', 1)[-1].rsplit(' [', 1)[0]
        channel_key = normalize(channel_name)
        suggestions = difflib.get_close_matches(
            channel_key, list(lookup.keys()), n=3, cutoff=0.55
        )
        for suggestion in suggestions:
            print('  POSSIBLE EPG:', lookup[suggestion], '| similarity:',
                  round(difflib.SequenceMatcher(None, channel_key, suggestion).ratio() * 100), '%')


if __name__ == '__main__':
    main()
