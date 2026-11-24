"""Build data.json (game data for the page) from ClashKing static data.

Usage:  python build/gen_data.py <path to ClashKingAssets/assets/static_data> [out=build/data.json]
Get the data: git clone --depth 1 https://github.com/ClashKingInc/ClashKingAssets

Item format (one per building / trap / troop / spell / siege / hero / pet / equipment / guardian):
  i id, n name, g page group, k kind (b building, h hero, l lab, p pet, e equipment),
  r resource (g gold, e elixir, d dark, o ore), m[th] max level at that TH, c[th] how many you have at that TH,
  t[L-1] seconds to reach level L, co[L-1] cost to reach level L (equipment: [shiny, glowy, starry]),
  h hero (equipment), ra rarity (equipment), opt guardian flag,
  tg air/ground: "a", "g" or "ag" (defenses and guardians: what they hit; traps: what sets them off;
  troops, heroes, pets: "a" flying, "g" ground). Left out when it doesn't apply.
Arrays m and c run TH0..TOP_TH (index = Town Hall level).
"""
import json, os, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "ClashKingAssets/assets/static_data"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
load = lambda f: json.load(open(os.path.join(SRC, f), encoding="utf-8"))["items"]

BUILD = {x["_id"]: x for x in load("buildings.json")}
TRAPS = {x["_id"]: x for x in load("traps.json")}
TH = BUILD[1000001]
TOP_TH = max(l["level"] for l in TH["levels"])
THS = range(TOP_TH + 1)
RES = {"Gold": "g", "Elixir": "e", "Dark Elixir": "d"}

# Skipped on purpose: Town Hall itself, Crafting Station (modules not tracked), Sour Elixir Cauldron,
# Guardian Shrine (holds guardians, no upgrades of its own), anything not in the home village.
SKIP_BUILD = {1000001, 1000097, 1000105}
SKIP_NAMES = {"Sour Elixir Cauldron"}
GROUP_BY_TYPE = {"Army": "Army", "Resource": "Resources", "Defense": "Defenses", "Wall": "Walls",
                 "Worker": "Army", "Worker2": "Army", "Helper": "Army"}
# Kept for counting (builders) but their upgrades are not tracked.
NO_UPGRADES = {"Worker2", "Helper"}

# --- how many of each building/trap you have at each TH: cumulative Town Hall unlocks -----------------
unl = {}
for L in sorted(TH["levels"], key=lambda l: l["level"]):
    for u in L.get("unlocks") or []:
        unl.setdefault(u["_id"], {})[L["level"]] = unl.get(u["_id"], {}).get(L["level"], 0) + u["quantity"]
def counts(bid):
    out, run = [], 0
    for t in THS:
        run += unl.get(bid, {}).get(t, 0); out.append(run)
    return out
# Buildings the Town Hall swallows on upgrade (Eagle Artillery merges into the TH17 Inferno Artillery):
# from that TH on you own none of them.
GONE_FROM = {}
for L in TH["levels"]:
    for mr in L.get("merge_requirement") or []:
        GONE_FROM[mr["_id"]] = min(GONE_FROM.get(mr["_id"], 99), L["level"])
_counts = counts
def counts(bid):
    c = _counts(bid)
    return [0 if t >= GONE_FROM.get(bid, 99) else c[t] for t in THS]

def tg_hits(x):
    a, g = x.get("is_air_targeting"), x.get("is_ground_targeting")
    if a is None and g is None:
        a, g = x.get("air_trigger"), x.get("ground_trigger")
    v = ("a" if a else "") + ("g" if g else "")
    return v or None
def tg_unit(x):
    f = x.get("is_flying")
    return None if f is None else ("a" if f else "g")

def rt(l, unlock_th):
    r = l.get("required_townhall")
    return unlock_th if r is None else r

def bmax(b, unlock_th=None):
    """max level of a building/trap at each TH"""
    return [max([l["level"] for l in b["levels"] if rt(l, unlock_th or 99) <= t] or [0]) for t in THS]

items = []
for src, is_trap in ((BUILD, False), (TRAPS, True)):
    for bid, b in src.items():
        if bid in SKIP_BUILD or b["name"] in SKIP_NAMES or b.get("village", "home") != "home": continue
        c = counts(bid)
        first = next((t for t in THS if c[t] > 0), None)
        if first is None: continue
        g = "Traps" if is_trap else GROUP_BY_TYPE.get(b.get("type"))
        if not g: continue
        lv = sorted(b["levels"], key=lambda l: l["level"])
        m = bmax(b, first)
        m = [m[t] if c[t] > 0 and b.get("type") not in NO_UPGRADES else 0 for t in THS]
        items.append({"i": bid, "n": b["name"], "g": g, "k": "b", "r": RES.get(b.get("upgrade_resource"), "g"),
                      "m": m, "c": c,
                      "t": [0 if g == "Walls" else (l.get("build_time") or 0) for l in lv],
                      "co": [l.get("build_cost") or 0 for l in lv]})
        if g in ("Defenses", "Traps") and tg_hits(b): items[-1]["tg"] = tg_hits(b)

bm = lambda name: bmax(next(b for b in BUILD.values() if b["name"] == name))
LAB, HALL, PETH, SMITH = bm("Laboratory"), bm("Hero Hall"), bm("Pet House"), bm("Blacksmith")
PROD = {}
def prodmax(name):
    if name not in PROD:
        b = next((b for b in BUILD.values() if b["name"] == name), None)
        PROD[name] = bmax(b) if b else [0] * len(THS)
    return PROD[name]

def shifted(lv, key):
    """ClashKing stores the cost of going FROM a level; the page wants cost to REACH it."""
    return [0] + [lv[i - 1].get(key) or 0 for i in range(1, len(lv))]

def unit_items(fname, group_of, kind, gate_key, gate_max):
    for x in load(fname):
        if x.get("village", "home") != "home" or x.get("super_troop") or x.get("is_seasonal"): continue
        g = group_of(x)
        if not g: continue
        lv = sorted(x["levels"], key=lambda l: l["level"])
        pb, pbl = x.get("production_building"), x.get("production_building_level") or 1
        pm = prodmax(pb) if pb else [99] * len(THS)
        m = []
        for t in THS:
            if pm[t] < pbl: m.append(0); continue
            ok = [l["level"] for l in lv if (l.get("required_townhall") or 0) <= t
                  and (gate_key is None or (l.get(gate_key) or 0) <= gate_max[t])
                  and (gate_key is None or gate_max[t] > 0)]
            # level 1 of a newly unlocked unit can carry a bogus low required_townhall in ClashKing;
            # it only counts once level 2's TH is reachable or the production building allows it.
            m.append(max(ok or [0]))
        it = {"i": x["_id"], "n": x["name"], "g": g, "k": kind, "m": m, "c": [1 if v else 0 for v in m]}
        if kind == "e":
            it["r"] = "o"
            it["t"] = [0] * len(lv)
            ore = lambda l: [(l.get("upgrade_cost") or {}).get(k, 0) for k in ("shiny_ore", "glowy_ore", "starry_ore")]
            it["co"] = [[0, 0, 0]] + [ore(lv[i - 1]) for i in range(1, len(lv))]
            it["h"] = x.get("hero"); it["ra"] = x.get("rarity")
        else:
            it["r"] = RES.get(x.get("upgrade_resource"), "e")
            it["t"] = shifted(lv, "upgrade_time"); it["co"] = shifted(lv, "upgrade_cost")
        if kind in ("l", "h", "p") and tg_unit(x): it["tg"] = tg_unit(x)
        items.append(it)

def troop_group(x):
    pb = x.get("production_building")
    if pb in ("Barracks", "Dark Barracks"): return "Troops"
    if pb == "Workshop": return "Sieges"
    if pb == "Squad Barracks": return "Squads"
    return None
unit_items("troops.json", troop_group, "l", "required_lab_level", LAB)
unit_items("spells.json", lambda x: "Spells", "l", "required_lab_level", LAB)
unit_items("heroes.json", lambda x: "Heroes", "h", "required_hero_tavern_level", HALL)
unit_items("pets.json", lambda x: "Pets", "p", "required_pet_house_level", PETH)
unit_items("equipment.json", lambda x: "Equipment", "e", "required_blacksmith_level", SMITH)

for x in load("guardians.json"):
    lv = sorted(x["levels"], key=lambda l: l["level"])
    m = [max([l["level"] for l in lv if (l.get("required_townhall") or 99) <= t] or [0]) for t in THS]
    items.append({"i": x["_id"], "n": x["name"], "g": "Guardians", "k": "b", "r": RES.get(x.get("upgrade_resource"), "e"),
                  "m": m, "c": [1 if v else 0 for v in m], "t": shifted(lv, "upgrade_time"), "co": shifted(lv, "upgrade_cost"), "opt": 1})
    if tg_hits(x): items[-1]["tg"] = tg_hits(x)

# --- merged defenses: building X uses up N of building Y (Ricochet Cannon = 2 cannons, etc.) -------
merges = {}
for b in BUILD.values():
    for l in b["levels"][:1]:
        for mr in l.get("merge_requirement") or []:
            if b["_id"] == 1000001: continue
            merges.setdefault(str(b["_id"]), {})
            merges[str(b["_id"])][str(mr["_id"])] = merges[str(b["_id"])].get(str(mr["_id"]), 0) + mr.get("quantity", 1)

# --- Town Hall weapon (TH12 to TH17). ClashKing has no TH weapon table, kept as data from clash-of-clans-data.
WEAPON = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "th_weapon.json"), encoding="utf-8"))

data = {"items": items, "weapon": WEAPON, "merges": merges, "top": TOP_TH}
json.dump(data, open(OUT, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
print(f"{len(items)} items, Town Hall 1 to {TOP_TH}, {os.path.getsize(OUT) // 1024} KB -> {OUT}")
