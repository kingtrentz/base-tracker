# Build files (keep these in the repo)

- `gen_data.py`: turns ClashKing static data into `data.json` (max levels, counts, times, costs per Town Hall).
- `th_weapon.json`: Town Hall weapon table (TH12 to TH17); ClashKing doesn't have it.
- `template.html`: the page source. Edit this, not `index.html`.
- `build.py`: puts `data.json` into `template.html` and writes `index.html`.

Refresh game data (new Town Hall or balance update):

    git clone --depth 1 https://github.com/ClashKingInc/ClashKingAssets /tmp/ck
    python build/gen_data.py /tmp/ck/assets/static_data
    python build/build.py

Then check both accounts at 390px before pushing.
