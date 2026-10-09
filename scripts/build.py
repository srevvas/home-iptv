    successes = 0
    for url in EPG_URLS:
        try:
            data = fetch(url)
            if data.startswith(b'\x1f\x8b'):
                data = gzip.decompress(data)
            root = ET.fromstring(data)
            if root.tag != 'tv':
                raise ValueError('Not an XMLTV document')
            source_channels = {}
            for channel in root.findall('channel'):
                channel_id = channel.get('id')
                if channel_id:
                    source_channels.setdefault(channel_id, channel)
            source_programmes = defaultdict(list)
            for programme in root.findall('programme'):
                channel_id = programme.get('channel')
                if channel_id:
                    source_programmes[channel_id].append(programme)
            added = 0
            for channel_id, items in source_programmes.items():
                # Do not replace a working EPG ID from the first source.
                if channel_id in programmes:
                    continue
                if channel_id not in source_channels:
                    continue
                channels[channel_id] = source_channels[channel_id]
                programmes[channel_id] = items
                added += 1
            successes += 1
            print(f'EPG source OK: {url} | {len(source_channels)} channels, '
                  f'{sum(map(len, source_programmes.values()))} programmes, '
                  f'{added} new channel IDs')
        except Exception as exc:
            print(f'WARNING: EPG source unavailable: {url} ({exc})')

    if not successes:
        print('WARNING: No EPG sources available; keeping any previously built EPG file')
        return {}, None

    merged = ET.Element('tv', {'generator-info-name': 'Home IPTV EPG merger'})
    for channel_id, channel in channels.items():
        merged.append(channel)
    for channel_id, items in programmes.items():
        for programme in items:
            merged.append(programme)
    DOCS.mkdir(parents=True, exist_ok=True)
    with gzip.open(EPG_DEST, 'wb', compresslevel=6) as out:
        ET.ElementTree(merged).write(out, encoding='utf-8', xml_declaration=True)
    print(f'Merged EPG: {EPG_DEST} | {len(channels)} channels, '
          f'{sum(map(len, programmes.values()))} programmes')

    lookup = {}
    ambiguous = set()
    for channel_id, channel in channels.items():
        candidates = [channel_id]
        candidates.extend(n.text for n in channel.findall('display-name') if n.text)
        for candidate in candidates:
            key = normalize(candidate)
            if not key:
                continue
            if key in lookup and lookup[key] != channel_id:
                ambiguous.add(key)
            else:
                lookup[key] = channel_id
    for key in ambiguous:
        lookup.pop(key, None)
    print(f'EPG lookup keys: {len(lookup)}')
    return lookup, set(programmes)


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
    lookup, programme_ids = load_epg()
    output = [f'#EXTM3U url-tvg="{PUBLIC_EPG_URL}"']
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
                candidates = [normalize(old_id.split('@', 1)[0].split('.', 1)[0]), normalize(title)]
                new_id = EPG_IDS.get(old_id)
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
                extinf = re.sub(r'^(#EXTINF:[^,]*)(,)',
                                lambda m: m.group(1) + f' group-title="{label}"' + m.group(2),
                                extinf, count=1)
            output.extend([extinf, *metadata[1:], stream])
            count += 1
        if count == 0:
            raise RuntimeError(f'No channels found for {code}; refusing to overwrite playlist')
        counts[code] = count

    DOCS.mkdir(parents=True, exist_ok=True)
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
        suggestions = difflib.get_close_matches(channel_key, list(lookup), n=3, cutoff=0.55)
        for suggestion in suggestions:
            print('  POSSIBLE EPG:', lookup[suggestion], '| similarity:',
                  round(difflib.SequenceMatcher(None, channel_key, suggestion).ratio() * 100), '%')


if __name__ == '__main__':
    main()
