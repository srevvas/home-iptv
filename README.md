# Home IPTV Master Playlist

Combines the public IPTV-org country playlists for Greece, France, Albania, UK and USA into a single M3U with country groups. All channels in each source are included; duplicate streams across countries are retained intentionally.

## Installation
1. Create a **public** GitHub repository named `home-iptv` (no README during creation).
2. Upload the **contents** of this folder, preserving `.github/workflows/update-playlist.yml` and `scripts/build.py`. GitHub web upload may not preserve empty folders; this is fine.
3. Open **Actions** > **Update Home IPTV playlist** > **Run workflow** (on the `main` branch). This creates `docs/home.m3u`.
4. In **Settings > Pages**, choose **Deploy from a branch**, branch `main`, folder `/docs`, and Save.
5. When Pages is deployed, your playlist URL is `https://YOUR-USERNAME.github.io/home-iptv/home.m3u`.
6. Add this URL to Televizo and SS IPTV as an external M3U playlist; enable periodic playlist refresh in the player if available.

The GitHub Action checks for changes every Sunday at 04:17 UTC. Scheduled GitHub Actions can be delayed or disabled after prolonged inactivity; use **Run workflow** to trigger manually. If any country source fails or returns no channels, the previous playlist is preserved. IPTV-org does not guarantee availability or commercial rebroadcast rights for streams. Public playlist means everyone can read the URLs: do not add secrets, private tokens or credentials.

## Customize
Edit `COUNTRIES` in `scripts/build.py`. Country groups are applied to `group-title` in EXTINF metadata. The script preserves other IPTV metadata and stream URLs. The project is free with standard GitHub public-repository/Pages limits.
