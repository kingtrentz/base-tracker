# PC auto-update (copy of what runs on Trent's PC)

Lives on the PC at `Documents\2026\GitHubs\Clash of Clans\Base Tracker`. This folder is a backup copy so the scripts never get lost; edit on the PC and copy here.

- `base_pull.py`: every 10 min (Windows task "Base Tracker - auto-update", :x7). Pulls KingTrents and Khnum-Atum~ra from the Clash API into `data/api_<tag>.json`. Uploads only files whose levels changed, in one commit. (A clan pull existed briefly on Nov 23, 2026 and was removed when the site was locked to Trent; the PC keeps that version as base_pull.py.with_clan.)
- Clash API key: read from `..\Touch Grass Inc Tracker\config.json` (home-IP key).
- GitHub token: `github_token.txt` next to the script (base-tracker only, Contents read/write). Never committed.
- `setup.bat` creates the scheduled task after a first run; `run_now.bat` runs it once by hand. Log: `run_log.txt`.
