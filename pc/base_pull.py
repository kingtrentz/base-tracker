"""Base Tracker auto-update: runs every 10 minutes on Trent's PC.
1) pulls KingTrents and Khnum-Atum~ra from the Clash API (uses the API key already in the Touch Grass config.json)
2) saves hero, troop, spell, siege, pet and equipment levels to data/api_<tag>.json
3) uploads only files whose levels changed to kingtrentz/base-tracker (needs github_token.txt in this folder)
Buildings, walls and traps aren't in the API, so those still come from a pasted in-game export.
Log: run_log.txt (last 400 lines). Run by hand: double-click run_now.bat"""
import json, os, sys, time, base64, hashlib, datetime, urllib.request, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *f: os.path.join(HERE, *f)
KEY_CONFIG = os.path.join(HERE, "..", "Touch Grass Inc Tracker", "config.json")
ACCOUNTS = ["#R0RRV0VQ", "#QUV9Q8Q2"]   # KingTrents, Khnum-Atum~ra
CLAN_CONFIG = os.path.join(HERE, "..", "Den of Thieves Tracker", "config.json")   # only clanTag is read from it
CLAN_FILE = "data/clan_levels.json"   # everyone else in Den of Thieves, one file, kept apart from Trent's own files
USER, REPO = "kingtrentz", "base-tracker"

def log(msg):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    try: print(line)
    except Exception: pass
    try:
        old = open(P("run_log.txt"), encoding="utf-8").read().splitlines()[-399:] if os.path.exists(P("run_log.txt")) else []
        open(P("run_log.txt"), "w", encoding="utf-8").write("\n".join(old + [line]) + "\n")
    except Exception: pass

def clash(key, tag):
    url = "https://api.clashofclans.com/v1/players/" + urllib.parse.quote(tag)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def levels(p):
    lv = {}
    for k in ("heroes", "troops", "spells", "heroEquipment"):
        for e in p.get(k) or []:
            if e.get("village", "home") == "home" and e.get("name"):
                lv[e["name"]] = e.get("level", 0)
    return lv

def main():
    try: key = json.load(open(KEY_CONFIG, encoding="utf-8"))["apiKey"]
    except Exception as e:
        log(f"ERROR couldn't read the API key from Touch Grass config.json ({e})"); return 1
    os.makedirs(P("data"), exist_ok=True)
    changed, hashes = {}, {}
    try: st = json.load(open(P("push_state.json"), encoding="utf-8"))
    except Exception: st = {}
    for tag in ACCOUNTS:
        try: p = clash(key, tag)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            log(f"ERROR Clash API {tag} ({e.code}): {body}"); continue
        except Exception as e:
            log(f"ERROR Clash API {tag}: {e}"); continue
        path = f"data/api_{tag[1:]}.json"
        lv = levels(p)
        h = hashlib.sha256(json.dumps([lv, p.get("townHallLevel")], sort_keys=True).encode()).hexdigest()
        if st.get(path) == h:
            continue   # nothing upgraded since the last upload
        hashes[path] = h
        out = {"tag": tag, "name": p.get("name", ""), "th": p.get("townHallLevel", 0), "ts": int(time.time()), "levels": lv}
        content = json.dumps(out, ensure_ascii=False, indent=1).encode("utf-8")
        open(P(path), "wb").write(content)
        changed[path] = content
        log(f"{p.get('name', tag)}: levels changed, queued for upload")
    # clan members: separate step, separate file. Anything going wrong here is logged and skipped,
    # so it can never stop Trent's own two accounts from updating.
    try:
        ctag = json.load(open(CLAN_CONFIG, encoding="utf-8")).get("clanTag", "")
        if ctag:
            req = urllib.request.Request("https://api.clashofclans.com/v1/clans/" + urllib.parse.quote(ctag) + "/members",
                                         headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r: members = json.loads(r.read()).get("items", [])
            try: prev = json.load(open(P(CLAN_FILE), encoding="utf-8"))
            except Exception: prev = {}
            out = {}
            for m in members:
                t = m.get("tag")
                if not t or t in ACCOUNTS: continue
                try: p = clash(key, t)
                except Exception as e:
                    if t in prev: out[t] = prev[t]
                    continue
                lv = levels(p)
                old = prev.get(t) or {}
                same = old.get("levels") == lv and old.get("th") == p.get("townHallLevel")
                out[t] = {"tag": t, "name": p.get("name", ""), "th": p.get("townHallLevel", 0), "ts": old.get("ts") if same and old.get("ts") else int(time.time()), "levels": lv}
            h = hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()
            if out and st.get(CLAN_FILE) != h:
                content = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                open(P(CLAN_FILE), "wb").write(content)
                changed[CLAN_FILE] = content; hashes[CLAN_FILE] = h
                log(f"Clan: {len(out)} members, levels changed, queued for upload")
    except Exception as e:
        log(f"Clan pull skipped ({type(e).__name__}: {e})")
    if not changed:
        log("OK no level changes"); return 0
    if "--no-upload" in sys.argv:
        log("Test mode (--no-upload): saved locally only."); return 0
    try: token = open(P("github_token.txt"), encoding="utf-8").read().strip()
    except Exception: token = ""
    if not token or "PASTE" in token:
        log("GitHub token not set yet (github_token.txt). Saved locally only."); return 0
    api = f"https://api.github.com/repos/{USER}/{REPO}"
    H = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "base-tracker"}
    def gh(method, url, body=None):
        req = urllib.request.Request(url, method=method, headers=H, data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try: return e.code, json.loads(e.read() or b"{}")
            except Exception: return e.code, {}
        except Exception as e:
            return 0, {"message": str(e)}
    code, ref = gh("GET", f"{api}/git/ref/heads/main")
    if code != 200: log(f"ERROR reading GitHub branch ({code}): {ref.get('message','')}. Check github_token.txt."); return 1
    head = ref["object"]["sha"]
    code, cm = gh("GET", f"{api}/git/commits/{head}")
    if code != 200: log(f"ERROR reading latest commit ({code})"); return 1
    tree = []
    for path, content in changed.items():
        code, blob = gh("POST", f"{api}/git/blobs", {"content": base64.b64encode(content).decode(), "encoding": "base64"})
        if code != 201: log(f"ERROR uploading {path} ({code}): {blob.get('message','')}"); return 1
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    code, t = gh("POST", f"{api}/git/trees", {"base_tree": cm["tree"]["sha"], "tree": tree})
    if code != 201: log(f"ERROR building tree ({code}): {t.get('message','')}"); return 1
    code, c = gh("POST", f"{api}/git/commits", {"message": f"Auto-update levels {datetime.datetime.now():%b %d %H:%M}", "tree": t["sha"], "parents": [head]})
    if code != 201: log(f"ERROR creating commit ({code}): {c.get('message','')}"); return 1
    code, r = gh("PATCH", f"{api}/git/refs/heads/main", {"sha": c["sha"]})
    if code != 200: log(f"ERROR updating branch ({code}): {r.get('message','')}"); return 1
    st.update(hashes); json.dump(st, open(P("push_state.json"), "w", encoding="utf-8"))
    log(f"OK uploaded {len(changed)} file(s). Site: https://{USER}.github.io/{REPO}/")
    return 0

if __name__ == "__main__":
    try: rc = main()
    except Exception as e:
        log(f"ERROR {type(e).__name__}: {e}"); rc = 1
    sys.exit(rc)
