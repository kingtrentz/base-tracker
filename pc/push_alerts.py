"""Base Tracker Web Push alerts (runs on Trent's PC inside base_pull.py every 5 minutes).
- Reads sealed subscriptions from kingtrentz/base-tracker data/push_subs.json
- Decrypts them locally using push_keys.json (private keys never leave this PC)
- Checks active Builder, Lab/Squad, and Pet timers for KingTrents and Khnum-Atum~ra
- ~20 min (configurable) before an upgrade finishes, sends an iPhone/Apple Watch push
  saying what's finishing, what's next on the Plan (queue or pinned slot), and the exact
  Gold / Elixir / Dark Elixir needed so Trent can raid if short on loot.
Uses only Python stdlib + cryptography (RFC 8291 aes128gcm + RFC 8292 VAPID ES256).
"""
import base64, hashlib, json, os, struct, subprocess, time, urllib.error, urllib.parse, urllib.request
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *f: os.path.join(HERE, *f)
USER, REPO = "kingtrentz", "base-tracker"
ACCOUNTS = [("#R0RRV0VQ", "KingTrents"), ("#QUV9Q8Q2", "Khnum-Atum~ra")]
RES_NAME = {"g": "Gold", "e": "Elixir", "d": "Dark Elixir"}
RES_SHORT = {"g": "Gold", "e": "Elixir", "d": "Dark"}


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _unb64u(s: str) -> bytes:
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * ((4 - len(s) % 4) % 4))


def _num(x: int) -> str:
    if x >= 1_000_000_000:
        return f"{x / 1e9:.1f}".rstrip("0").rstrip(".") + "B"
    if x >= 1_000_000:
        return (f"{x / 1e6:.0f}" if x >= 100_000_000 else f"{x / 1e6:.1f}".rstrip("0").rstrip(".")) + "M"
    if x >= 1_000:
        return f"{round(x / 1e3)}K"
    return str(x)


def _dur_short(secs: float) -> str:
    m = max(1, int(round(secs / 60)))
    if m >= 60:
        h, rm = divmod(m, 60)
        return f"{h}h {rm}m" if rm else f"{h}h"
    return f"{m}m"


def _unseal(entry: dict, rsa_priv) -> dict:
    ek = base64.b64decode(entry["ek"])
    iv = base64.b64decode(entry["iv"])
    ct = base64.b64decode(entry["ct"])
    aes_key = rsa_priv.decrypt(
        ek,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    plain = AESGCM(aes_key).decrypt(iv, ct, None)
    return json.loads(plain.decode("utf-8"))


def _vapid_header(endpoint: str, vapid_priv, vapid_pub_b64u: str, subject: str) -> str:
    u = urllib.parse.urlsplit(endpoint)
    aud = f"{u.scheme}://{u.netloc}"
    hdr = _b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    body = _b64u(json.dumps({"aud": aud, "exp": int(time.time()) + 43200, "sub": subject}, separators=(",", ":")).encode())
    signing_input = f"{hdr}.{body}".encode("ascii")
    der_sig = vapid_priv.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der_sig)
    raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    jwt = f"{hdr}.{body}.{_b64u(raw_sig)}"
    return f"vapid t={jwt}, k={vapid_pub_b64u}"


def _encrypt_aes128gcm(payload_bytes: bytes, sub_keys: dict) -> bytes:
    """RFC 8291 / RFC 8188 aes128gcm Web Push payload encryption."""
    ua_pub_bytes = _unb64u(sub_keys["p256dh"])
    auth_secret = _unb64u(sub_keys["auth"])
    ua_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub_bytes)

    as_priv = ec.generate_private_key(ec.SECP256R1())
    as_pub_bytes = as_priv.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    shared = as_priv.exchange(ec.ECDH(), ua_pub)

    # IKM = HKDF-Expand(HKDF-Extract(auth_secret, shared), "WebPush: info\0" || ua_pub || as_pub, 32)
    ikm = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=auth_secret,
        info=b"WebPush: info\x00" + ua_pub_bytes + as_pub_bytes,
    ).derive(shared)

    salt = os.urandom(16)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt, info=b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt, info=b"Content-Encoding: nonce\x00").derive(ikm)

    # Delimiter 0x02 marks final record
    ct = AESGCM(cek).encrypt(nonce, payload_bytes + b"\x02", None)
    # Header: salt(16) || rs(4, big-endian) || idlen(1) || keyid(65)
    header = salt + struct.pack("!IB", 4096, len(as_pub_bytes)) + as_pub_bytes
    return header + ct


def send_web_push(sub: dict, payload: dict, vapid_priv, vapid_pub_b64u: str, subject: str) -> int:
    endpoint = sub["endpoint"]
    body = _encrypt_aes128gcm(json.dumps(payload, ensure_ascii=False).encode("utf-8"), sub["keys"])
    headers = {
        "Authorization": _vapid_header(endpoint, vapid_priv, vapid_pub_b64u, subject),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": "3600",
        "Urgency": "high",
        "User-Agent": "base-tracker-push/1.0",
    }
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError:
        # Windows OpenSSL may lack Apple Push root CA; Windows curl uses native Schannel TLS with full verification
        cmd = ["curl.exe", "-sS", "-o", os.devnull, "-w", "%{http_code}", "-X", "POST", "--data-binary", "@-"]
        for k, v in headers.items():
            cmd.extend(["-H", f"{k}: {v}"])
        cmd.append(endpoint)
        p = subprocess.run(cmd, input=body, capture_output=True, timeout=25)
        try:
            return int(p.stdout.decode("ascii", "ignore").strip() or "0")
        except ValueError:
            return 0


def _gh_get_file(path: str, token: str):
    url = f"https://api.github.com/repos/{USER}/{REPO}/contents/{path}?ref=main"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "base-tracker-push",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read())
            return base64.b64decode(j["content"]), j.get("sha", "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, ""
        raise


def _load_game_data(token: str) -> dict:
    cache_path = P("data", "game_data_cache.json")
    os.makedirs(P("data"), exist_ok=True)
    # Refresh cached build/data.json once every 12 hours
    if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < 43200:
        try:
            return json.load(open(cache_path, encoding="utf-8"))
        except Exception:
            pass
    raw, _ = _gh_get_file("build/data.json", token)
    if raw:
        open(cache_path, "wb").write(raw)
        return json.loads(raw.decode("utf-8"))
    if os.path.exists(cache_path):
        return json.load(open(cache_path, encoding="utf-8"))
    return {"items": [], "merges": {}, "top": 19}


def _parse_export(raw_json: dict, by_id: dict, now: float):
    inst = {}
    th = 0
    for k, v in raw_json.items():
        if not isinstance(v, list) or k.endswith("2"):
            continue
        for e in v:
            if not isinstance(e, dict) or not isinstance(e.get("data"), int):
                continue
            if e["data"] == 1000001:
                th = e.get("lvl", 0) or 0
                continue
            if e["data"] not in by_id:
                continue
            cnt = max(1, e.get("cnt", 1) or 1)
            arr = inst.setdefault(e["data"], [])
            for _ in range(cnt):
                arr.append({"l": e.get("lvl", 0) or 0, "t": e.get("timer", 0) or 0})
    ts = raw_json.get("timestamp") or int(now)
    age = now - ts
    # Settle already-finished upgrades
    for arr in inst.values():
        for h in arr:
            if h["t"] > 0 and h["t"] <= age:
                h["l"] += 1
                h["t"] = 0
    return {"th": th, "ts": ts, "age": age, "inst": inst}


def _pin_match(pin: str, item: dict) -> bool:
    if not pin:
        return False
    if pin.startswith("g:"):
        return pin[2:] == item.get("g")
    if pin.startswith("i:"):
        return pin[2:] == str(item.get("i"))
    return False


def _pick_next_for_slot(kind: str, is_squad: bool, fin_item: dict, v: dict, plan: dict, gdata: dict, by_id: dict):
    """Find the next planned or pinned upgrade for a finishing slot, returning (item, from_lvl) or None."""
    th = min(max(v["th"], 1), gdata.get("top", 19))
    merges = gdata.get("merges", {})
    owned = lambda iid: len(v["inst"].get(iid, []))

    # Build virtual post-active levels (counting running upgrades as +1)
    virt = {}
    max_lv = {}
    for o in gdata["items"]:
        M = o["m"][th] if th < len(o["m"]) else 0
        if not M:
            continue
        need = (1 if owned(o["i"]) else 0) if o["k"] == "e" else (o["c"][th] if th < len(o["c"]) else 0)
        for mid, src in merges.items():
            if str(o["i"]) in src:
                need -= src[str(o["i"])] * owned(int(mid))
        need = max(0, need)
        have = v["inst"].get(o["i"], [])
        n = max(need, len(have))
        if not n:
            continue
        lvls = []
        for i in range(n):
            if i < len(have):
                h = have[i]
                up = h["t"] > 0 and (h["t"] - v["age"]) > 0 and h["l"] < M
                lvls.append(min(M, h["l"] + (1 if up else 0)))
            else:
                lvls.append(0)
        virt[o["i"]] = lvls
        max_lv[o["i"]] = M

    def valid_q(q):
        iid, lv = q.get("i"), q.get("l")
        if iid not in virt or lv is None or lv >= max_lv.get(iid, 0):
            return False
        return lv in virt[iid]

    def auto_from_pin(pin: str, pred):
        best = None
        for o in gdata["items"]:
            iid = o["i"]
            if iid not in virt or not pred(o) or not _pin_match(pin, o):
                continue
            M = max_lv[iid]
            for lv in virt[iid]:
                if lv >= M:
                    continue
                t = (o.get("t") or [])[lv] if lv < len(o.get("t") or []) else 0
                k = lv / M
                if best is None or k < best[0] or (k == best[0] and t < best[1]):
                    best = (k, t, o, lv)
        return (best[2], best[3]) if best else None

    if kind == "b":
        pins = plan.get("pins") or []
        bq = [q for q in (plan.get("b") or []) if valid_q(q)]
        # If this finishing building matches a pinned slot, prefer queued item matching that pin, else auto-suggest for pin
        matched_pin = next((p for p in pins if _pin_match(p, fin_item)), "")
        if matched_pin:
            for q in bq:
                if _pin_match(matched_pin, by_id[q["i"]]):
                    return by_id[q["i"]], q["l"]
            auto = auto_from_pin(matched_pin, lambda o: (o["k"] == "b" and o["g"] != "Walls") or o["k"] == "h")
            if auto:
                return auto
        if bq:
            return by_id[bq[0]["i"]], bq[0]["l"]
        return None

    if kind == "l":
        lpins = plan.get("lpins") or []
        pin = lpins[1] if is_squad and len(lpins) > 1 else (lpins[0] if not is_squad and len(lpins) > 0 else "")
        lq = [q for q in (plan.get("l") or []) if valid_q(q)]
        slot_q = [q for q in lq if (by_id[q["i"]]["g"] == "Squads") == is_squad]
        if pin:
            for q in slot_q:
                if _pin_match(pin, by_id[q["i"]]):
                    return by_id[q["i"]], q["l"]
            auto = auto_from_pin(pin, lambda o: o["k"] == "l" and (o["g"] == "Squads") == is_squad)
            if auto:
                return auto
        if slot_q:
            return by_id[slot_q[0]["i"]], slot_q[0]["l"]
        return None

    if kind == "p":
        ppin = plan.get("ppin") or ""
        pq = [q for q in (plan.get("p") or []) if valid_q(q)]
        if ppin:
            for q in pq:
                if _pin_match(ppin, by_id[q["i"]]):
                    return by_id[q["i"]], q["l"]
            auto = auto_from_pin(ppin, lambda o: o["k"] == "p")
            if auto:
                return auto
        if pq:
            return by_id[pq[0]["i"]], pq[0]["l"]
        return None

    return None


def _cost_text(item: dict, from_lvl: int):
    co = item.get("co") or []
    cost = co[from_lvl] if from_lvl < len(co) else 0
    r = item.get("r", "g")
    if isinstance(cost, (int, float)) and cost > 0:
        return f"{_num(int(cost))} {RES_SHORT.get(r, 'Loot')}", RES_NAME.get(r, "loot")
    return "", ""


def check_and_send(log=print) -> int:
    key_file = P("push_keys.json")
    tok_file = P("github_token.txt")
    if not os.path.exists(key_file) or not os.path.exists(tok_file):
        return 0
    token = open(tok_file, encoding="utf-8").read().strip()
    if not token or "PASTE" in token:
        return 0

    keys = json.load(open(key_file, encoding="utf-8"))
    vapid_priv = serialization.load_pem_private_key(keys["vapid_private_pem"].encode("ascii"), password=None)
    rsa_priv = serialization.load_pem_private_key(keys["seal_private_pem"].encode("ascii"), password=None)

    subs_raw, _ = _gh_get_file("data/push_subs.json", token)
    if not subs_raw:
        return 0
    try:
        subs_doc = json.loads(subs_raw.decode("utf-8"))
    except Exception:
        return 0
    entries = subs_doc.get("subs") or {}
    if not entries:
        return 0

    subs = []
    for sid, enc in entries.items():
        try:
            d = _unseal(enc, rsa_priv)
            if d.get("sub") and d["sub"].get("endpoint"):
                d["id"] = sid
                subs.append(d)
        except Exception as e:
            log(f"PUSH skip bad sub {sid[:8]}: {e}")
    if not subs:
        return 0

    sent_path = P("push_sent.json")
    try:
        sent = json.load(open(sent_path, encoding="utf-8"))
    except Exception:
        sent = {}
    now = time.time()
    # Prune records older than 14 days
    sent = {k: v for k, v in sent.items() if isinstance(v, (int, float)) and (now - v) < 14 * 86400}

    gdata = _load_game_data(token)
    by_id = {o["i"]: o for o in gdata.get("items", [])}
    sent_count = 0

    # 1. Send one-time welcome test notification for newly subscribed devices
    for s in subs:
        wts = s.get("welcomeTs") or 0
        if wts and (now - wts) < 900:
            wk = f"welcome|{s['id']}|{int(wts)}"
            if wk not in sent:
                lead = int(s.get("lead") or 20)
                code = send_web_push(
                    s["sub"],
                    {
                        "title": "Base Tracker alerts are on",
                        "body": f"You'll get a heads-up {lead}m before upgrades finish with your next planned upgrade and loot needed.",
                        "tag": "bt-welcome",
                        "url": "index.html",
                    },
                    vapid_priv,
                    keys["vapid_public"],
                    keys["vapid_subject"],
                )
                if 200 <= code < 300:
                    sent[wk] = now
                    sent_count += 1
                    log(f"PUSH welcome sent to {s['id'][:8]} (HTTP {code})")
                else:
                    log(f"PUSH welcome failed for {s['id'][:8]} (HTTP {code})")

    # 2. Check active timers on each account
    for tag, acc_name in ACCOUNTS:
        raw_b, _ = _gh_get_file(f"data/{tag[1:]}.json", token)
        if not raw_b:
            continue
        v = _parse_export(json.loads(raw_b.decode("utf-8")), by_id, now)
        plan_b, _ = _gh_get_file(f"data/plan_{tag[1:]}.json", token)
        plan = json.loads(plan_b.decode("utf-8")) if plan_b else {}

        for iid, arr in v["inst"].items():
            o = by_id.get(iid)
            if not o:
                continue
            kind = "b" if ((o["k"] == "b" and o["g"] != "Walls") or o["k"] == "h") else ("l" if o["k"] == "l" else ("p" if o["k"] == "p" else ""))
            if not kind:
                continue
            is_squad = (o["g"] == "Squads")
            for h in arr:
                if not h["t"]:
                    continue
                left = h["t"] - v["age"]
                if left <= 0:
                    continue
                end_ts = now + left
                end_bucket = int(end_ts // 600)
                for s in subs:
                    types = s.get("types") or {"b": True, "l": True, "p": True}
                    if not types.get(kind, True):
                        continue
                    lead_min = int(s.get("lead") or 20)
                    # Trigger once when remaining time enters [1s .. lead_min + 3m]
                    if left > lead_min * 60 + 180:
                        continue
                    dk = f"{s['id']}|{tag}|{iid}|{h['l']}|{end_bucket}"
                    if dk in sent:
                        continue

                    nxt = _pick_next_for_slot(kind, is_squad, o, v, plan, gdata, by_id)
                    slot_label = "Squad" if is_squad else ("Lab" if kind == "l" else ("Pet House" if kind == "p" else "Builder"))
                    title = f"{acc_name}: {o['n']} →{h['l'] + 1} done in {_dur_short(left)}"
                    if nxt:
                        no, nl = nxt
                        ct, rname = _cost_text(no, nl)
                        if ct:
                            body = f"Next ({slot_label}): {no['n']} →{nl + 1} ({ct}). Raid if you need {rname}!"
                        else:
                            body = f"Next ({slot_label}): {no['n']} →{nl + 1}"
                    else:
                        body = f"{slot_label} free in {_dur_short(left)}. Open Plan to assign what's next."

                    code = send_web_push(
                        s["sub"],
                        {"title": title, "body": body, "tag": f"bt-{tag[1:]}-{iid}-{h['l']}", "url": "index.html"},
                        vapid_priv,
                        keys["vapid_public"],
                        keys["vapid_subject"],
                    )
                    if 200 <= code < 300:
                        sent[dk] = now
                        sent_count += 1
                        log(f"PUSH sent ({code}): {title} | {body}")
                    else:
                        log(f"PUSH failed ({code}) for {s['id'][:8]}: {title}")

    json.dump(sent, open(sent_path, "w", encoding="utf-8"))
    return sent_count


if __name__ == "__main__":
    check_and_send(print)
