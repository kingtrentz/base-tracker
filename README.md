# base-tracker

Clash of Clans base progress tracker for two accounts (KingTrents and Khnum-Atum~ra), on GitHub Pages.

## How it works
- Edit `build/template.html`, then run `python3 build/build.py` to write `index.html`. Don't edit `index.html` by hand.
- Game data comes from the in-game export you paste, plus ClashKing static data (in `data/`).
- Plans (next picks, goblin timers) save per account and sync through the repo.
- `pc/push_alerts.py` runs on Trent's PC (Documents\2026\GitHubs\Clash of Clans\Base Tracker) and sends the push alerts. After changing it here, copy it to that folder by hand.

## What's on the page
- Builders pill (top right): dropdown of every busy builder, lab, squad and pet with countdowns. Starts open on page load; tap the pill to close it. Lab rows read "Lab" and "Goblin lab" (squads are lab work, no separate squad row). Header shows when the next builder frees up, with date and time.
- Progress: Overall bar, tap it to open the other six. Ring around the town hall.
- Next section right under the overall card, then the category tabs and the open tab below it (Nov 26, 2026: Next is the main place to set builders and pick what's next). Next folds behind one header and starts closed; it hides on Up Next and while editing levels.
  - Defenses, Traps, Collectors and Storages show one dropdown per building (copies left, next upgrade); tap it to see each copy. Short tabs (Army, Guardians, Walls and the rest) stay as plain lists (`DROPDOWN_TABS`).
  - Troops splits into two dropdowns, Elixir troops and Dark elixir troops (by each troop's resource), each with troops left, how many are upgrading and the soonest upgrade time; each troop is a named row inside. Sort still works inside each.
- KingTrents only: a ⚡ watermark sits fixed behind the page (same approach as the McGrath Masters crest: fixed layer, GPU-locked, low opacity, see-through cards on that account). Khnum-Atum~ra has none.
- KingTrents only: small gold lightning bolts flicker near the bottom of the screen in place of the floating ember dots (`.bolts`, opacity-only animation, off with reduced motion). Khnum-Atum~ra keeps the ember dots.
- Account header: the name is the big line and "Town Hall 19 · updated …" sits under it (both accounts). KingTrents shows as his in-game name, KingTrents⚡ (`INGAME`); its account pill reads KingTrents⚡ too.
  - One line per builder, the lab (troops, spells, sieges and squads together) and the pet house: what it's on, a "next" dropdown and a "stays on" lane.
  - Next never auto-picks. The suggestion is only listed first.
  - "⚠ N need a next" shows when a busy builder or lab has nothing picked.
  - Small "+ goblin builder" and "+ goblin researcher" links add a countdown for the goblin helpers.
  - No queues in Next for any slot (builders, lab, pets, goblins). Each slot only has its next and lane dropdowns (Nov 26, 2026).
- Look: gold and black. Black page (#0d0b08), dark cards (#17140e), gold accent (#f5a524). One gradient (#fde68a > #f5a524 > #c2410c) on every progress bar, the town hall ring, Paste, the active tab and the account pill. The town hall picture in the ring is unchanged. Light mode (☀/☾) has a matching cream and gold version. TH16 to TH18 still get their own tints; both accounts are TH19 (Nov 26, 2026).
- Push alerts: when a builder or lab frees up, and when an upgrade finishes ("X upgraded to level N. Next upgrade: Lvl M Y").

## TH19 rules in the code
- Only 150 walls can reach level 20, the rest top out at 19 (`WALL_CAP`).
- The extra air defense and the 10th spring trap are counted.
- The next dropdown lists every level the copies of a building sit at (e.g. "Air Defense 16 → 17 ×4").

## History
- PR #1 builder dropdown opens on load (closed in #5, open again in #8)
- PR #2 Next section on every tab, folded tabs, maxed items hidden
- PR #3 Next condensed to one line per slot, never auto-fills
- PR #4 progress bars fold to Overall, % above town hall removed
- PR #5 TH19 fixes, folded Next with warnings, squads in the lab slot, goblin timers, date on next builder, completion pings
- PR #6 lab and pet queues removed from Next, so no slot has a queue
- PR #7 Traps tab gets the same per-building dropdown as Defenses
- PR #8 builder dropdown starts open again; its lab rows read Lab and Goblin lab (no separate squad row)
- PR #9 gold and black theme across the site, light mode matched, TH picture unchanged
- PR #10 troops tab split into elixir and dark elixir dropdowns; ⚡ watermark behind the KingTrents page
- PR #11 header shows the account name on top (KingTrents⚡) with Town Hall under it
- PR #12 KingTrents account pill reads KingTrents⚡
- PR #13 Next moved above the tabs, right under the overall card; flickering lightning bolts replace the ember dots on KingTrents
