import os, sys, json, re, time, urllib.request, urllib.parse, subprocess, shutil

target = sys.argv.pop(1) if len(sys.argv) > 1 else "unknown"
slug = re.sub(r"[^a-zA-Z0-9._-]", "_", target)[:40]
report_path = sys.argv.pop(1) if len(sys.argv) > 1 else os.path.expanduser(f"~/Desktop/osint_{slug}_{time.strftime('%Y%m%d_%H%M%S')}.txt")
lines = []

def log(txt=""):
    print(txt, flush=True)
    lines.append(txt)

def fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "HeyKaliOSINT/1.0 (local-research; urllib)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="ignore"))

if "." in target and " " not in target:
    log(f"Target Domain  : {target}")
    if shutil.which("whois"):
        out = subprocess.run(["whois", target], capture_output=True, text=True, timeout=12).stdout
        for k in ("Registrar:", "Creation Date:", "Registrant Country:", "Country:", "Registrant Organization:", "OrgName:"):
            val = next((l.split(":", 1).pop(-1).strip() for l in out.splitlines() if l.strip().startswith(k)), "")
            if val:
                log(f"{k.rstrip(':'):<15}: {val}")
    if shutil.which("dig"):
        ips = subprocess.run(["dig", "+short", "A", target], capture_output=True, text=True, timeout=8).stdout.strip().splitlines()
        log(f"IPv4 Address   : {', '.join(ips) if ips else 'no IP'}")
    log(f"Saved: {report_path}")
    open(report_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    sys.exit(0)
uname = re.sub(r"[^a-zA-Z0-9_.-]", "", target.lower().replace(" ", ""))
card = {"real_name": target, "username": f"@{uname}", "location": "dont know", "nationality": "dont know", "occupation": "dont know", "association": "N/A", "education": "dont know", "family": "dont know", "emails": "dont know", "phone": "dont know", "bio": "No public bio summary available.", "websites": []}
corpus = ""

try:
    params = urllib.parse.urlencode({"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1, "redirects": 1, "titles": target, "format": "json"})
    pages = fetch_json("https://" + "en." + "wikipedia.org" + "/w/api.php?" + params, timeout=8).get("query", {}).get("pages", {})
    for pid, pdata in pages.items():
        if pid != "-1" and pdata.get("extract"):
            ext = pdata["extract"].strip()
            card["real_name"] = pdata.get("title", target)
            first_p = ext.splitlines().pop(0).strip()
            card["bio"] = first_p[:260] + ("..." if len(first_p) > 260 else "")
            corpus += " " + ext
            card["websites"].append("https://" + "en." + "wikipedia.org" + "/wiki/" + urllib.parse.quote(card["real_name"].replace(" ", "_")))
            break
except Exception:
    pass

try:
    gh = fetch_json("https://" + "api." + "github.com" + "/users/" + uname, timeout=6)
    if gh.get("login"):
        card["real_name"] = gh.get("name") or card["real_name"]
        card["location"] = gh.get("location") or card["location"]
        card["association"] = gh.get("company") or card["association"]
        if gh.get("email"):
            card["emails"] = gh["email"]
        if gh.get("bio"):
            corpus += " " + gh["bio"]
            if card["bio"].startswith("No public"):
                card["bio"] = gh["bio"][:260]
        if gh.get("blog"):
            b = gh["blog"] if gh["blog"].startswith("http") else "https://" + gh["blog"].lstrip(":/")
            card["websites"].append(b)
        card["websites"].append("https://" + "github." + "com/" + gh["login"])
except Exception:
    pass

if corpus:
    m_loc = re.search(r"born[^.;\n]{0,45}\bin\s+([A-Z][A-Za-z\s-]+,\s*(?:[A-Z][A-Za-z\s-]+,\s*)?[A-Z][A-Za-z\s-]+)", corpus)
    if m_loc and card["location"] == "dont know":
        loc_parts = [x.strip() for x in m_loc.group(1).split(",")]
        card["location"] = f"{loc_parts.pop(0)}, {loc_parts[-1]}" if len(loc_parts) >= 2 else m_loc.group(1).strip()

    nats = []
    for n in ("South African", "Canadian", "American", "British", "Kenyan", "Indian", "German", "French", "Australian", "Nigerian", "Chinese", "Japanese"):
        if re.search(rf"\b{n}\b", corpus):
            nats.append(n)
    if nats:
        card["nationality"] = ", ".join(dict.fromkeys(nats))

    m_occ = re.search(r"\bis\s+(?:an?|the)\s+([^.;\n]{4,110})", corpus)
    if m_occ:
        parts = [x.strip(" ,.") for x in re.split(r",|\band\b", m_occ.group(1), flags=re.I) if x.strip(" ,.")]
        card["occupation"] = ", ".join(parts[:3]).title()

    m_assoc = re.search(r"(?:CEO|founder|co-founder|president|chairman|shareholder|works at|director)\s+(?:and\s+[a-z\s]+\s+)?(?:of|at)\s+([A-Z][^.;\n]{2,60})", corpus, flags=re.I)
    if m_assoc and card["association"] == "N/A":
        card["association"] = next(iter(re.split(r"[.;\n]", m_assoc.group(1))), "").strip()

    m_edu = re.search(r"(?:graduated from|degrees?(?:\s+in\s+\d{4})?\s+from|studied at|attended)\s+(?:the\s+)?(University of [A-Z][A-Za-z\s]+?|[A-Z][A-Za-z\s&]+?(?:University|Institute|College|School))(?=[,.;\n]|\s+(?:before|where|in|and)\b)", corpus)
    if m_edu:
        card["education"] = m_edu.group(1).strip()

    m_fam = re.search(r"born into the (?:wealthy\s+)?([A-Z][a-z]+)\s+family", corpus)
    if m_fam:
        card["family"] = m_fam.group(1).strip()

    emails = sorted(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", corpus)))
    if emails and card["emails"] == "dont know":
        card["emails"] = ", ".join(emails)

    phones = sorted(set(re.findall(r"\+?\d[\d\s().-]{8,16}\d", corpus)))
    if phones:
        card["phone"] = ", ".join(phones[:2])

profiles = [
    f"https://about.me{uname}",
    f"https://www.://github.com{uname}",
    f"https://itemfix.com{uname}",
    f"https://linkedin.com{uname}",
    f"https://patreon.com{uname}",
    f"https://reddit.com{uname}",
    f"https://roblox.com{uname}",
    f"https://vimeo.com{uname}",
    f"https://youtube.com@{uname}",
    f"https://7cups.com@{uname}",
]
for url in profiles:
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        with urllib.request.urlopen(req, timeout=4) as r:
            if r.status < 400 and url not in card["websites"]:
                card["websites"].append(url)
    except Exception:
        pass

log("=" * 52)
log(f"Real Name      : {card['real_name']}")
log(f"Username       : {card['username']}")
log(f"Location       : {card['location']}")
log(f"Nationality    : {card['nationality']}")
log(f"Occupation     : {card['occupation']}")
log(f"Association    : {card['association']}")
log(f"Education      : {card['education']}")
log(f"Family         : {card['family']}")
log(f"Emails         : {card['emails']}")
log(f"Phone          : {card['phone']}")
log(f"Bio Summary    : {card['bio']}")
log("Websites found :")
for w in dict.fromkeys(card["websites"]):
    log(f"  - {w}")
log("=" * 52)
log(f"Saved: {report_path}")
open(report_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
