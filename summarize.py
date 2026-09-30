"""Print every headline number used in README.md, computed from data/profiles.csv only.

Usage: python summarize.py
Licence: MIT (see LICENSE-CODE).
"""
import csv
import pathlib
import statistics as st

HERE = pathlib.Path(__file__).resolve().parent
rows = list(csv.DictReader(open(HERE / "data" / "profiles.csv", encoding="utf-8")))
has = [r for r in rows if r["has_profile_readme"] == "true"]
no = [r for r in rows if r["has_profile_readme"] == "false"]
n = len(has)


def t(r, k):
    return r[k] == "true"


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)"


def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            out[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den


print("fetched_utc range:", min(r["fetched_utc"] for r in rows), "to", max(r["fetched_utc"] for r in rows))
print("checked:", len(rows), " with README:", pct(n, len(rows)), " without:", pct(len(no), len(rows)))
print("  without, no profile repo:", sum(r["profile_repo_exists"] == "false" for r in no),
      " repo but no README:", [r["login"] for r in no if r["profile_repo_exists"] == "true"])
print("\nby source list (checked / with README):")
for s in ("top-followed", "design-peer", "seo-peer"):
    g = [r for r in rows if r["source_list"] == s]
    print(" ", s, len(g), sum(t(r, "has_profile_readme") for r in g))

ln = [int(r["lines"]) for r in has]
by = [int(r["readme_bytes"]) for r in has]
print("\nlines: median", st.median(ln), " min", min(ln), " max", max(ln), " quartiles", st.quantiles(ln, n=4))
print("bytes: median", st.median(by), " min", min(by), " max", max(by))
print("30 lines or fewer:", pct(sum(x <= 30 for x in ln), n))
print("20 lines or fewer:", pct(sum(x <= 20 for x in ln), n))
print("under 1,000 bytes:", pct(sum(x < 1000 for x in by), n))
print("50 lines or more:", pct(sum(x >= 50 for x in ln), n), [r["login"] for r in has if int(r["lines"]) >= 50])
fol = [int(r["followers"]) for r in has]
print("Spearman followers vs lines (n=%d): %.2f" % (n, spearman(fol, ln)))
tf = [r for r in has if r["source_list"] == "top-followed"]
print("Spearman followers vs lines, top-followed only (n=%d): %.2f" % (
    len(tf), spearman([int(r["followers"]) for r in tf], [int(r["lines"]) for r in tf])))

print("\nfeatures (of %d READMEs):" % n)
for k in ("has_stats_widget", "has_typing_svg", "has_badges_wall", "has_shields", "has_greeting", "has_headers"):
    who = [r["login"] for r in has if t(r, k)]
    print(" ", k, pct(len(who), n), who if len(who) <= 9 else "")
print("  stats widget among top-followed:", pct(sum(t(r, "has_stats_widget") for r in tf), len(tf)),
      " among peers:", pct(sum(t(r, "has_stats_widget") for r in has if r["source_list"] != "top-followed"), n - len(tf)))
print("  any widget, typing svg or badge wall:", pct(sum(t(r, "has_stats_widget") or t(r, "has_typing_svg") or t(r, "has_badges_wall") for r in has), n))
print("  first_line_type:", {k: sum(r["first_line_type"] == k for r in has) for k in sorted({r["first_line_type"] for r in has})})
lk = [int(r["links_count"]) for r in has]
print("  links_count: median", st.median(lk), " 0-2 links:", pct(sum(x <= 2 for x in lk), n), " 5 or fewer:", pct(sum(x <= 5 for x in lk), n))
print("  1-line or 2-line-ish (<=9 lines):", pct(sum(x <= 9 for x in ln), n))

print("\npinned items (of the 62 checked):")
pc = [int(r["pinned_count"]) for r in rows]
print("  6 pinned:", pct(sum(x == 6 for x in pc), len(pc)), " 0 pinned:", pct(sum(x == 0 for x in pc), len(pc)))
print("  with README, 6 pinned:", pct(sum(int(r["pinned_count"]) == 6 for r in has), n),
      " without README, 6 pinned:", pct(sum(int(r["pinned_count"]) == 6 for r in no), len(no)))
print("  with README, 0 pinned:", pct(sum(int(r["pinned_count"]) == 0 for r in has), n),
      " without README, 0 pinned:", pct(sum(int(r["pinned_count"]) == 0 for r in no), len(no)))
print("\nsmall-follower end of the README set (followers < 10,000):",
      [(r["login"], r["lines"], r["links_count"]) for r in has if int(r["followers"]) < 10000])

ks = [int(r["known_for_stars"]) for r in has if r["known_for_stars"]]
print("\nmost-starred owned non-fork repo, the 30 READMEs: median stars", st.median(ks), " min", min(ks),
      " max", max(ks), " under 1,000 stars:", pct(sum(x < 1000 for x in ks), len(ks)))
ksn = [int(r["known_for_stars"]) for r in no if r["known_for_stars"]]
print("  same for the 32 without a README: median", st.median(ksn), " n", len(ksn))

small = [r for r in has if int(r["known_for_stars"]) < 1000]
big = [r for r in has if int(r["known_for_stars"]) >= 1000]
print("\nREADMEs whose owner's best repo has under 1,000 stars: n =", len(small),
      " stats widget:", sum(t(r, "has_stats_widget") for r in small),
      " badge wall:", sum(t(r, "has_badges_wall") for r in small))
print("READMEs whose owner's best repo has 1,000+ stars: n =", len(big),
      " stats widget:", sum(t(r, "has_stats_widget") for r in big),
      " badge wall:", sum(t(r, "has_badges_wall") for r in big))
print("  lines median, small-repo owners:", st.median(int(r["lines"]) for r in small),
      " big-repo owners:", st.median(int(r["lines"]) for r in big))
