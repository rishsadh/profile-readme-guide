"""Regenerate data/profiles.csv from the GitHub API.

Reads data/selection.csv (the 62 accounts checked on 2026-09-29, frozen), then for each
login calls:

  GET  /users/{login}                     -> followers
  GET  /repos/{login}/{login}/readme      -> the profile README (raw), or 404 if none
  GET  /repos/{login}/{login}             -> only when the README call was 404, to tell
                                             "no profile repo" from "repo without README"
  POST /graphql                           -> pinned item count, most-starred owned non-fork repo

and codes the README with the fixed rules below. No README text is written to disk, only
its size, a SHA-256 of the raw bytes, and the coded features.

Usage:
  python code_profiles.py                 # writes data/profiles.csv
  python code_profiles.py --out other.csv

Auth: set GITHUB_TOKEN, or have the `gh` CLI logged in (its token is read with
`gh auth token`, used in memory, never printed or stored). The GraphQL call needs a token.
Read-only: nothing is starred, followed, forked or posted.

Licence: MIT (see LICENSE-CODE).
"""
import argparse
import csv
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
API = "https://api.github.com"

# ---- coding rules (also written out in method.md) --------------------------------------
STATS_RX = re.compile(
    r"github-readme-stats|github-readme-streak-stats|streak-stats|wakatime\.com|"
    r"github-profile-summary-cards|profile-summary-cards|github-readme-activity-graph|"
    r"activity-graph|metrics\.lecoq\.io|github-profile-trophy|github-stats", re.I)
TYPING_RX = re.compile(r"readme-typing-svg|typing-svg", re.I)
BADGE_RX = re.compile(
    r"img\.shields\.io|shields\.io/badge|badgen\.net|skillicons\.dev|forthebadge\.com|"
    r"cdn\.simpleicons\.org|devicon", re.I)
SHIELDS_RX = re.compile(r"shields\.io", re.I)
BADGE_WALL_MIN = 5  # this many badge or icon images = "a wall"
GREETING_RX = re.compile(
    r"\b(hi|hello|hey|hola|ola|olá|welcome|salut|bonjour|hallo)\b|👋", re.I)
IMG_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")
IMG_SRC = re.compile(r"""!\[[^\]]*\]\(\s*<?([^)\s>]+)|<(?:img|source)\s[^>]*?(?:src|srcset)\s*=\s*["']([^"']+)""", re.I)
MD_LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)")
HTML_HREF = re.compile(r"""<a\s[^>]*href\s*=\s*["']([^"']+)["']""", re.I)
AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")
HEADER_RX = re.compile(r"^\s*#{1,6}\s+\S|<h[1-6][\s>]", re.I | re.M)
COMMENT_RX = re.compile(r"<!--.*?-->", re.S)

FIELDS = ["login", "followers", "has_profile_readme", "lines", "has_stats_widget",
          "has_typing_svg", "has_badges_wall", "links_count", "first_line_type",
          "pinned_count", "known_for",
          # extras
          "source_list", "rank_in_source_list", "profile_repo_exists", "readme_bytes",
          "badge_images", "has_shields", "has_greeting", "has_headers",
          "known_for_stars", "readme_sha256", "fetched_utc"]


def token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t:
        return t.strip()
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        sys.exit("No token: set GITHUB_TOKEN or log in with the gh CLI.")


TOKEN = None


def call(path, accept="application/vnd.github+json", body=None):
    """Return (status, bytes). Retries on 5xx and secondary rate limits."""
    url = path if path.startswith("http") else API + path
    for attempt in range(4):
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {TOKEN}", "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "profile-readme-guide/1"})
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, b""
            if e.code in (403, 429) or e.code >= 500:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"giving up on {url}")


def code_readme(text):
    """Feature-code one README. Pure function of the text."""
    body = COMMENT_RX.sub("", text.lstrip(chr(0xFEFF)))
    lines = text.splitlines()
    # Widgets and badges are images. A plain link to a widget's docs does not count.
    srcs = [a or b for a, b in IMG_SRC.findall(text)]
    src_blob = " ".join(srcs)
    badge_n = sum(1 for u in srcs if BADGE_RX.search(u))
    imgless = IMG_MD.sub("IMG", body)
    targets = set()
    for rx in (MD_LINK, HTML_HREF, AUTOLINK):
        for m in rx.finditer(imgless):
            u = m.group(1).strip()
            if u and not u.startswith("#") and not u.lower().startswith("mailto:"):
                targets.add(u)
    first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
    if first.startswith("#"):
        ftype = "heading"
    elif first.startswith("!["):
        ftype = "image"
    elif first.startswith("<"):
        ftype = "html"
    elif first.startswith("["):
        ftype = "link"
    else:
        ftype = "text" if first else "empty"
    plain = re.sub(r"<[^>]+>|[#*_`>\[\]()!]", " ", body).strip()
    return {
        "lines": len(lines),
        "has_stats_widget": bool(STATS_RX.search(src_blob)),
        "has_typing_svg": bool(TYPING_RX.search(src_blob)),
        "badge_images": badge_n,
        "has_badges_wall": badge_n >= BADGE_WALL_MIN,
        "has_shields": bool(SHIELDS_RX.search(src_blob)),
        "links_count": len(targets),
        "first_line_type": ftype,
        "has_greeting": bool(GREETING_RX.search(plain[:60])),
        "has_headers": bool(HEADER_RX.search(body)),
    }


GQL = """query($l:String!){user(login:$l){
  pinnedItems(first:6){totalCount}
  repositories(first:1, ownerAffiliations:OWNER, isFork:false,
               orderBy:{field:STARGAZERS, direction:DESC}){nodes{name stargazerCount}}}}"""


def main():
    global TOKEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--selection", default=str(HERE / "data" / "selection.csv"))
    ap.add_argument("--out", default=str(HERE / "data" / "profiles.csv"))
    ap.add_argument("--logins", help="optional CSV mapping pseudonym to login (not published)")
    a = ap.parse_args()
    real = {}
    if a.logins:
        real = {r["pseudonym"]: r["login"] for r in csv.DictReader(open(a.logins, encoding="utf-8"))}
    TOKEN = token()
    sel = list(csv.DictReader(open(a.selection, encoding="utf-8")))
    out = []
    for s in sel:
        shown = s["login"]
        login = real.get(shown, shown)
        if shown.startswith(("design-peer-", "seo-peer-")) and shown not in real:
            print(shown, "pseudonym: pass --logins to re-fetch, or re-run the bio searches in method.md")
            continue
        row = {k: "" for k in FIELDS}
        row.update(login=shown, source_list=s["source_list"],
                   rank_in_source_list=s["rank_in_source_list"],
                   fetched_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        st, b = call(f"/users/{login}")
        if st == 404:
            row["has_profile_readme"] = "account_not_found"
            out.append(row)
            print(login, "account not found")
            continue
        row["followers"] = json.loads(b)["followers"]
        st, raw = call(f"/repos/{login}/{login}/readme", accept="application/vnd.github.raw")
        if st == 404:
            st2, _ = call(f"/repos/{login}/{login}")
            row["has_profile_readme"] = "false"
            row["profile_repo_exists"] = "true" if st2 == 200 else "false"
        else:
            text = raw.decode("utf-8", errors="replace")
            f = code_readme(text)
            row["has_profile_readme"] = "true"
            row["profile_repo_exists"] = "true"
            row["readme_bytes"] = len(raw)
            row["readme_sha256"] = hashlib.sha256(raw).hexdigest()
            for k, v in f.items():
                row[k] = str(v).lower() if isinstance(v, bool) else v
        st, b = call(f"{API}/graphql", body=json.dumps({"query": GQL, "variables": {"l": login}}).encode())
        u = (json.loads(b).get("data") or {}).get("user") or {}
        row["pinned_count"] = (u.get("pinnedItems") or {}).get("totalCount", "")
        nodes = (u.get("repositories") or {}).get("nodes") or []
        if nodes:
            row["known_for"] = nodes[0]["name"]
            row["known_for_stars"] = nodes[0]["stargazerCount"]
        out.append(row)
        print(login, row["has_profile_readme"])
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print("wrote", a.out, len(out), "rows")


if __name__ == "__main__":
    main()
