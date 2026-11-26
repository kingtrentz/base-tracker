# base-tracker

Clash of Clans base progress tracker for two accounts (KingTrents and Khnum-Atum~ra), on GitHub Pages.

## How it works
- Edit `build/template.html`, then run `python3 build/build.py` to write `index.html`. Don't edit `index.html` by hand.
- Game data comes from the in-game export you paste, plus ClashKing static data (in `data/`).
- Plans (next picks, goblin timers) save per account and sync through the repo.
- `pc/push_alerts.py` runs on Trent's PC (Documents\2026\GitHubs\Clash of Clans\Base Tracker) and sends the push alerts. After changing it here, copy it to that folder by hand.

## What's on the page
- Builders pill (top right): dropdown of every busy builder, lab, squad and pet with countdowns. Starts closed. Header shows when the next builder frees up, with date and time.
- Progress: Overall bar, tap it to open the other six. Ring around the town hall.
- Category tabs, then a Next section at the bottom of each tab. Next folds behind one header and starts closed.
  - One line per builder, the lab (troops, spells, sieges and squads together) and the pet house: what it's on, a "next" dropdown and a "stays on" lane.
  - Next never auto-picks. The suggestion is only listed first.
  - "⚠ N need a next" shows when a busy builder or lab has nothing picked.
  - Small "+ goblin builder" and "+ goblin researcher" links add a countdown for the goblin helpers.
  - No queues in Next for any slot (builders, lab, pets, goblins). Each slot only has its next and lane dropdowns (Nov 26, 2026).
- Push alerts: when a builder or lab frees up, and when an upgrade finishes ("X upgraded to level N. Next upgrade: Lvl M Y").

## TH19 rules in the code
- Only 150 walls can reach level 20, the rest top out at 19 (`WALL_CAP`).
- The extra air defense and the 10th spring trap are counted.
- The next dropdown lists every level the copies of a building sit at (e.g. "Air Defense 16 → 17 ×4").

## History
- PR #1 builder dropdown opens on load (since changed: starts closed in #5)
- PR #2 Next section on every tab, folded tabs, maxed items hidden
- PR #3 Next condensed to one line per slot, never auto-fills
- PR #4 progress bars fold to Overall, % above town hall removed
- PR #5 TH19 fixes, folded Next with warnings, squads in the lab slot, goblin timers, date on next builder, completion pings
- PR #6 lab and pet queues removed from Next, so no slot has a queue
