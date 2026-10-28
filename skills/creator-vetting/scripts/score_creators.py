#!/usr/bin/env python3
"""Score a creator longlist for the consumer-brand creator programme and write the dated shortlist.

Scoring run:
  python3 -I score_creators.py <workspace> <longlist.csv> <scores.csv> [--posts posts.csv] --as-of YYYY-MM-DD [--replace]
Rates run (before scoring; writes nothing):
  python3 -I score_creators.py <workspace> <longlist.csv> --rates-only [--posts posts.csv] --as-of YYYY-MM-DD

The scoring run reads program/program.md (sections 2, 3 and 9), the longlist, the confirmed scores,
the optional recent-posts file and, when present, data/creators.csv (to fill creator_ref). It computes
tier, engagement rate, total, confidence, verdict and reasons, writes data/shortlist-<as-of>.csv in the
shape of schemas.md section 8, and prints a summary that ends with the coverage line.

Every threshold comes from the settings block in ../references/scoring.md (section 8). Change a number
there, never here.

Exit codes: 0 complete; 1 bad input (one sentence says what to fix; nothing written);
2 partial (written, but a creator lacks posts data, a line was not judged, or a longlist row was not
scored; the summary's first line says partial and why).

Standard library only. No network. Reads nothing outside the workspace except this skill's reference.
"""
import argparse
import csv
import datetime as dt
import pathlib
import re
import statistics
import sys

# File shapes. Longlist and shortlist: the pack's schemas.md sections 7 and 8. Scores and posts: this
# skill's references/scoring.md section 9.
LONGLIST_HEADER = ["display_name", "platform", "handle", "profile_url", "followers", "followers_source",
                   "niche_tags", "found_via", "already_talks_about_category", "contact_path", "notes"]
LINES = ["audience_fit", "engagement_quality", "authenticity", "brand_safety",
         "sponsored_track_record", "contactability"]
SCORES_HEADER = ["handle", "platform"] + LINES + ["evidence"]
POSTS_HEADER = ["handle", "platform", "post_url", "posted_at", "likes", "comments", "shares", "views"]
POSTS_OPTIONAL = "sponsored"
SHORTLIST_HEADER = LONGLIST_HEADER + LINES + ["total", "confidence", "verdict", "reasons",
                                              "scored_as_of", "creator_ref", "tier", "engagement_rate_pct",
                                              "brand_safety_flag"]
# brand_safety_flag is appended for creator-roster's add to copy into the roster's column of the same
# name (schemas.md section 4: none, review, exclude); the rule is references/scoring.md section 6.
ROSTER_NEEDS = ["creator_ref", "primary_platform", "primary_handle", "profile_url", "other_platforms", "status",
                "notes"]
MERGED = re.compile(r"merged into c-[a-z0-9]{6}")   # schemas.md section 4: a merged-away row is never counted
OWNER_QUESTION = "owner to rule"   # scoring.md section 1, brand_safety: an open section 9 question
SCORE_MIN, SCORE_MAX = 0, 5          # schemas.md section 8: each line an integer 0 to 5
FOLLOWERS_SOURCES = {"profile", "search_result", "media_kit", "estimate"}   # schemas.md section 7
PLATFORMS = ["instagram", "tiktok", "youtube", "x", "onlyfans", "reddit", "podcast", "newsletter",
             "bluesky", "threads", "other"]   # schemas.md section 4, primary_platform
FOLLOWER_LABELS = {"profile": "Measured, profile", "search_result": "Estimated, search result",
                   "media_kit": "User-provided, media kit", "estimate": "Estimated"}  # schemas.md section 7
DECIDED_MARKS = ("[owner]", "[observed]", "[default]")   # program template: source marks
OPEN_MARK = "[open]"
# Longlist platform -> row of programme section 3 (program template). Platforms without a row use "other".
PLATFORM_ROW = {"instagram": "instagram", "tiktok": "tiktok", "youtube": "youtube", "x": "x",
                "onlyfans": "onlyfans", "reddit": "reddit", "podcast": "podcasts", "newsletter": "podcasts",
                "bluesky": "other", "threads": "other", "other": "other"}
RULING = re.compile(r"^(yes|no|with conditions|unknown)\b(.*)$")
SETTINGS_KEYS = ["followers_max_age_days", "posts_window_days", "min_posts_high", "views_basis_platforms",
                 "tier_floor_micro", "tier_floor_mid", "tier_floor_macro",
                 "norm_followers_nano", "norm_followers_micro", "norm_followers_mid", "norm_followers_macro",
                 "norm_views_nano", "norm_views_micro", "norm_views_mid", "norm_views_macro",
                 "far_below_fraction", "far_above_multiple", "exclude_brand_safety_max", "engage_min_total",
                 "engage_min_brand_safety", "negotiate_min_total", "negotiate_min_brand_safety",
                 "min_authenticity", "review_brand_safety_max"]


class InputError(Exception):
    """Bad input: the message is one sentence saying what to fix."""


def norm_handle(h):
    return (h or "").strip().lstrip("@").strip().lower()


def norm_url(u):
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u.rstrip("/")


def parse_date(text, what):
    t = (text or "").strip()
    try:
        return dt.date.fromisoformat(t[:10])
    except ValueError:
        raise InputError(f"{what} reads '{t}'; write it as an ISO date, YYYY-MM-DD.")


def fmt(x):
    return f"{x:.2f}"


# ---------- settings ----------

def load_settings():
    path = pathlib.Path(__file__).resolve().parent.parent / "references" / "scoring.md"
    if not path.exists():
        raise InputError(f"the settings file {path} is missing; reinstall the skill folder.")
    text = path.read_text(encoding="utf-8")
    m = re.search(r"```settings\n(.*?)```", text, re.S)
    if not m:
        raise InputError("references/scoring.md has no settings block; restore section 8 of that file.")
    raw = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise InputError(f"references/scoring.md settings line '{line}' has no '='; write key = value.")
        k, v = line.split("=", 1)
        raw[k.strip()] = v.strip()
    missing = [k for k in SETTINGS_KEYS if k not in raw]
    if missing:
        raise InputError(f"references/scoring.md settings lack {', '.join(missing)}; add them to section 8.")
    s = {}
    try:
        for k in SETTINGS_KEYS:
            v = raw[k]
            if k == "views_basis_platforms":
                s[k] = {p.strip().lower() for p in v.split(",") if p.strip()}
            elif k.startswith("norm_"):
                mm = re.match(r"^([\d.]+)\s+to\s+([\d.]+)$", v)
                if not mm:
                    raise ValueError
                s[k] = (float(mm.group(1)), float(mm.group(2)))
            elif k in ("far_below_fraction", "far_above_multiple"):
                s[k] = float(v)
            else:
                s[k] = int(v)
    except ValueError:
        raise InputError(f"references/scoring.md setting {k} reads '{raw[k]}', which is not a valid value.")
    return s


# ---------- programme file ----------

def read_sections(program_text):
    sections, current, buf = {}, None, []
    for line in program_text.splitlines():
        m = re.match(r"^## (\d+)\.", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf)
            current, buf = int(m.group(1)), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf)
    return sections


def item_block(section_text, label):
    """Return the text of the '- <label>...' item and its indented continuation lines, or None."""
    lines = section_text.splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("- " + label):
            block = [line]
            for nxt in lines[i + 1:]:
                if nxt.startswith("- ") or nxt.startswith("#") or (nxt and not nxt[0].isspace()):
                    break
                block.append(nxt)
            return "\n".join(block)
    return None


def line_decided(block):
    """Template 0.1.2: the field's own line rules; an indented line stands in only when that line is blank,
    and an indented line with no mark is template guidance."""
    lines = block.lower().splitlines()
    first, detail = lines[0], [ln for ln in lines[1:] if ln.strip()]
    if OPEN_MARK in first:
        return False
    if any(mk in first for mk in DECIDED_MARKS):
        return True
    marked = [ln for ln in detail if OPEN_MARK in ln or any(mk in ln for mk in DECIDED_MARKS)]
    return bool(marked) and not any(OPEN_MARK in ln for ln in marked)


def check_program(ws):
    path = ws / "program" / "program.md"
    if not path.exists():
        raise InputError(f"{path} is missing; run program-setup with the owner first.")
    sections = read_sections(path.read_text(encoding="utf-8"))
    needed = [(2, "who the brand is for"), (9, "content suitability policy"), (9, "audience age"), (9, "redlines")]
    for num, label in needed:
        if num not in sections:
            raise InputError(f"program.md has no section {num}; restore its numbered headings with program-setup.")
        block = item_block(sections[num], label)
        if block is None:
            raise InputError(f"program.md section {num} has no '{label}' line; restore it with program-setup.")
        if not line_decided(block):
            raise InputError(f"program.md section {num} '{label}' is not decided yet; ask the owner to rule on it "
                             f"(mark it [owner]) before vetting, because the scores are judged against it.")
    if 3 not in sections:
        raise InputError("program.md has no section 3; restore its numbered headings with program-setup.")
    rulings = {}
    for line in sections[3].splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0].lower() in ("platform", "") or set(cells[0]) <= set("-: "):
            continue
        key = cells[0].lower().split()[0]
        value = re.sub(r"\[[^\]]*\]", "", cells[1]).strip()
        rulings[key] = "" if OPEN_MARK in line.lower() else value
    return rulings, path


def platform_ruling(rulings, platform):
    row = PLATFORM_ROW.get(platform, "other")
    if row not in rulings:
        raise InputError(f"program.md section 3 has no '{row}' row for platform {platform}; add it with program-setup.")
    value = rulings[row]
    if not value:
        raise InputError(f"program.md section 3 has no decided ruling on organic creator posts for '{row}' "
                         f"(blank or marked [open]); ask the owner to rule: yes, no, with conditions or unknown.")
    m = RULING.match(value.lower())
    if not m:
        raise InputError(f"program.md section 3 reads '{value}' for '{row}'; "
                         f"use yes, no, with conditions or unknown.")
    return row, m.group(1), value[len(m.group(1)):].strip(" :;-()")


# ---------- CSV inputs ----------

def read_csv(path, header, what, optional=None):
    if not path.exists():
        raise InputError(f"{what} file {path} was not found; check the path.")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            got = next(reader)
        except StopIteration:
            raise InputError(f"{what} file {path} is empty; it needs its header row.")
        got = [g.strip() for g in got]
        allowed = [header] + ([header + [optional]] if optional else [])
        if got not in allowed:
            missing = [c for c in header if c not in got]
            extra = [c for c in got if c not in header and c != optional]
            parts = []
            if missing:
                parts.append("missing " + ", ".join(missing))
            if extra:
                parts.append("extra " + ", ".join(extra))
            if not parts:
                parts.append("columns out of order")
            raise InputError(f"{what} file {path.name} has the wrong header ({'; '.join(parts)}); "
                             f"use exactly: {', '.join(header)}.")
        rows = []
        for n, r in enumerate(reader, start=2):
            if not any(c.strip() for c in r):
                continue
            if len(r) != len(got):
                raise InputError(f"{what} file {path.name} line {n} has {len(r)} cells, not {len(got)}; fix that line.")
            rows.append((n, dict(zip(got, [c.strip() for c in r]))))
    return rows


def int_cell(value, what, allow_empty=True):
    if value == "":
        if allow_empty:
            return None
        raise InputError(f"{what} is empty; it needs a whole number.")
    if not re.fullmatch(r"\d+", value):
        raise InputError(f"{what} reads '{value}'; write a whole number with no commas or symbols.")
    return int(value)


def load_longlist(path):
    rows = read_csv(path, LONGLIST_HEADER, "longlist")
    out, order = {}, []
    for n, r in rows:
        key = (r["platform"].lower(), norm_handle(r["handle"]))
        if not key[1]:
            raise InputError(f"longlist line {n} has no handle; fill it or remove the row.")
        if key in out:
            raise InputError(f"longlist has {r['handle']} on {r['platform']} twice (line {n}); "
                             f"run creator-discovery's check and keep one row.")
        if key[0] not in PLATFORMS:
            raise InputError(f"longlist line {n} platform reads '{r['platform']}'; use one of {', '.join(PLATFORMS)}.")
        r["_followers"] = int_cell(r["followers"], f"longlist line {n} followers")
        if r["followers_source"] and r["followers_source"] not in FOLLOWERS_SOURCES:
            raise InputError(f"longlist line {n} followers_source reads '{r['followers_source']}'; "
                             f"use profile, search_result, media_kit or estimate.")
        out[key] = r
        order.append(key)
    m = re.search(r"longlist-(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    observed = dt.date.fromisoformat(m.group(1)) if m else None
    return out, order, observed


def parse_evidence(text):
    entries, last = {}, None
    for part in text.split(";"):
        m = re.match(r"^\s*([a-z_]+)\s*:\s*(.*)$", part, re.S)
        if m and m.group(1) in LINES:
            last = m.group(1)
            entries[last] = m.group(2).strip()
        elif last is not None:
            entries[last] += ";" + part
    return entries


def load_scores(path, longlist):
    rows = read_csv(path, SCORES_HEADER, "scores")
    out = {}
    for n, r in rows:
        key = (r["platform"].lower(), norm_handle(r["handle"]))
        who = f"scores line {n} ({r['handle']} on {r['platform']})"
        if key not in longlist:
            raise InputError(f"{who} matches no longlist row; check the handle and platform.")
        if key in out:
            raise InputError(f"{who} scores the same creator twice; keep one row.")
        scores = {}
        for line in LINES:
            v = r[line]
            if v == "":
                scores[line] = None
                continue
            if not re.fullmatch(r"-?\d+", v):
                raise InputError(f"{who}: {line} reads '{v}'; scores are whole numbers {SCORE_MIN} to {SCORE_MAX}, "
                                 f"or empty when the line could not be judged.")
            iv = int(v)
            if iv < SCORE_MIN or iv > SCORE_MAX:
                raise InputError(f"{who}: {line} is {iv}, outside {SCORE_MIN} to {SCORE_MAX}; correct the score.")
            scores[line] = iv
        ev = parse_evidence(r["evidence"])
        lacking = [line for line in LINES if not ev.get(line)]
        if lacking:
            raise InputError(f"{who}: the evidence has no entry for {', '.join(lacking)}; every line needs one, "
                             f"saying what was seen or why it could not be seen.")
        out[key] = {"scores": scores, "evidence": ev}
    return out


def load_posts(path, longlist, as_of):
    rows = read_csv(path, POSTS_HEADER, "posts", optional=POSTS_OPTIONAL)
    m = re.search(r"posts-(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    read_date = dt.date.fromisoformat(m.group(1)) if m else None
    if read_date and read_date > as_of:
        raise InputError(f"{path.name} says its counts were read on {read_date}, after --as-of {as_of}; check the dates.")
    posts, ignored, dupes, seen = {}, 0, 0, set()
    for n, r in rows:
        key = (r["platform"].lower(), norm_handle(r["handle"]))
        if key not in longlist:
            ignored += 1
            continue
        url = norm_url(r["post_url"])
        if url and (key, url) in seen:
            dupes += 1
            continue
        seen.add((key, url))
        where = f"posts line {n}"
        posted = parse_date(r["posted_at"], f"{where} posted_at")
        if posted > as_of:
            raise InputError(f"{where} is dated {posted}, after --as-of {as_of}; check the date or the as-of date.")
        if read_date and posted > read_date:
            raise InputError(f"{where} is dated {posted}, after the day its counts were read ({read_date}, from the "
                             f"file name); check the date or the file name.")
        sponsored = r.get(POSTS_OPTIONAL, "").lower()
        if sponsored not in ("", "yes", "no"):
            raise InputError(f"{where} sponsored reads '{r[POSTS_OPTIONAL]}'; use yes, no or leave it empty.")
        posts.setdefault(key, []).append({
            "posted": posted,
            "likes": int_cell(r["likes"], f"{where} likes"),
            "comments": int_cell(r["comments"], f"{where} comments"),
            "shares": int_cell(r["shares"], f"{where} shares"),
            "views": int_cell(r["views"], f"{where} views"),
            "sponsored": sponsored,
        })
    return posts, ignored, dupes, len(rows), read_date


def load_roster(ws):
    path = ws / "data" / "creators.csv"
    if not path.exists():
        return None, 0, 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in ROSTER_NEEDS if c not in header]
        if missing:
            raise InputError(f"data/creators.csv lacks {', '.join(missing)}; run creator-roster check and fix the roster.")
        index, count, merged = {}, 0, 0
        for r in reader:
            if r["status"].strip() == "ended" and MERGED.search(r["notes"] or ""):
                merged += 1
                continue
            count += 1
            entry = (r["creator_ref"].strip(), r["status"].strip())
            index[("h", r["primary_platform"].strip().lower(), norm_handle(r["primary_handle"]))] = entry
            for item in (r["other_platforms"] or "").split(";"):
                if ":" in item:
                    p, h = item.split(":", 1)
                    index[("h", p.strip().lower(), norm_handle(h))] = entry
            if r["profile_url"].strip():
                index[("u", norm_url(r["profile_url"]))] = entry
    return index, count, merged


# ---------- arithmetic ----------

def tier_of(followers, s):
    if followers is None:
        return None
    if followers >= s["tier_floor_macro"]:
        return "macro"
    if followers >= s["tier_floor_mid"]:
        return "mid"
    if followers >= s["tier_floor_micro"]:
        return "micro"
    return "nano"


def engagement(row, plist, as_of, s, read_date=None):
    """Median per-post rate over usable posts inside the window. scoring.md section 3."""
    platform = row["platform"].lower()
    basis = "views" if platform in s["views_basis_platforms"] else "followers"
    followers = row["_followers"]
    e = {"basis": basis, "rows": len(plist), "usable": 0, "outside": 0, "no_numbers": 0,
         "rate": None, "spon": None, "org": None, "n_spon": 0, "n_org": 0,
         "label": f"Measured, counts read {read_date}" if read_date else "User-provided, read date not stated"}
    rates, spon, org = [], [], []
    for p in plist:
        if (as_of - p["posted"]).days > s["posts_window_days"]:
            e["outside"] += 1
            continue
        if p["likes"] is None or p["comments"] is None:
            e["no_numbers"] += 1
            continue
        divisor = p["views"] if basis == "views" else followers
        if not divisor:
            e["no_numbers"] += 1
            continue
        rate = (p["likes"] + p["comments"] + (p["shares"] or 0)) / divisor * 100
        rates.append(rate)
        (spon if p["sponsored"] == "yes" else org).append(rate)
    e["usable"] = len(rates)
    if rates:
        e["rate"] = round(statistics.median(rates), 2)
    if spon and org:
        e["spon"], e["org"] = round(statistics.median(spon), 2), round(statistics.median(org), 2)
        e["n_spon"], e["n_org"] = len(spon), len(org)
    return e


def position(rate, band, s):
    if rate is None or band is None:
        return None
    low, high = band
    if rate < low * s["far_below_fraction"]:
        return "far below"
    if rate < low:
        return "below"
    if rate > high * s["far_above_multiple"]:
        return "far above"
    if rate > high:
        return "above"
    return "within"


def assess_evidence(row, e, observed, as_of, s):
    """The three confidence checks of scoring.md section 5."""
    recent = (row["followers_source"] == "profile" and observed is not None
              and 0 <= (as_of - observed).days <= s["followers_max_age_days"])
    full = e["usable"] >= s["min_posts_high"]
    computed = e["rate"] is not None
    passed = sum([recent, full, computed])
    level = "high" if passed == 3 else "medium" if passed == 2 else "low"
    return level, recent, full, computed


def confidence_text(level, recent, full, computed, e, s, unjudged=False):
    if level == "high":
        return "confidence high"
    gaps = []
    if unjudged:
        gaps.append("a line not judged")
    if not recent:
        gaps.append("followers not a recent profile count")
    if computed and not full:
        gaps.append(f"{e['usable']} usable posts where the full sample is {s['min_posts_high']}")
    if not computed:
        gaps.append("engagement not computed")
    return f"confidence {level}: " + ", ".join(gaps)


def flag_for(verdict, sc, ev, s):
    """brand_safety_flag for the roster (scoring.md section 6). Returns (flag, why)."""
    bs = sc["brand_safety"]
    if verdict == "exclude":
        return "exclude", ""
    if bs is None:
        return "review", "brand_safety not judged"
    if OWNER_QUESTION in ev.get("brand_safety", "").lower():
        return "review", "a section 9 question is open for the owner"
    if bs <= s["review_brand_safety_max"]:
        return "review", f"brand_safety {bs} has something to settle first"
    return "none", ""


def verdict_for(sc, conf, ruling, roster_status, s, owner_question=False):
    """The verdict rules of scoring.md section 6, in order. Returns (verdict, cause)."""
    if roster_status == "excluded":
        return "exclude", "already excluded on the roster; only the owner reverses that, in creator-roster"
    bs = sc["brand_safety"]
    if bs is not None and bs <= s["exclude_brand_safety_max"]:
        return "exclude", f"brand_safety {bs}, at or below the exclusion line (programme section 9; the evidence says why)"
    unjudged = [line for line in LINES if sc[line] is None]
    if unjudged:
        return "skip", "not judged: " + ", ".join(unjudged) + "; score them and rerun"
    _, rule, cond = ruling
    if rule == "no":
        return "skip", "programme section 3 says no to organic creator posts on this platform"
    total = sum(sc.values())
    if total >= s["engage_min_total"] and bs >= s["engage_min_brand_safety"]:
        verdict, cause = "engage", f"total {total}, brand_safety {bs}"
    elif total >= s["negotiate_min_total"] and bs >= s["negotiate_min_brand_safety"]:
        verdict, cause = "negotiate", f"total {total}, brand_safety {bs}"
    else:
        return "skip", f"total {total}, brand_safety {bs}"
    if sc["authenticity"] < s["min_authenticity"]:
        return "skip", f"authenticity {sc['authenticity']} is below the floor"
    if verdict == "engage" and conf == "low":
        return "negotiate", cause + "; held at negotiate because confidence is low: verify the numbers first"
    if verdict == "engage" and owner_question:
        return "negotiate", cause + "; held at negotiate because a section 9 question is open for the owner"
    if verdict == "engage" and rule == "unknown":
        return "negotiate", cause + "; held at negotiate because programme section 3 has no ruling for this platform yet"
    return verdict, cause


def checks_for(sc, ev, e, pos):
    """Disagreements between a confirmed score and the computed numbers. They never change the verdict."""
    out = []
    eq, au, af = sc["engagement_quality"], sc["authenticity"], sc["audience_fit"]
    if eq is not None and pos in ("far below", "below") and eq >= 4:
        out.append(f"engagement_quality {eq} but the computed rate is {pos} the starting norm")
    if eq is not None and pos in ("within", "above", "far above") and eq <= 1:
        out.append(f"engagement_quality {eq} but the computed rate is {pos} the starting norm")
    if eq is not None and e["rate"] is None:
        out.append(f"engagement_quality {eq} was scored without a computed rate; it rests on a read of the profile")
    if au is not None and pos == "far above" and au >= 4:
        out.append(f"authenticity {au} but engagement is far above the starting norm; look for engagement groups")
    if af == 5 and "analytics" not in ev.get("audience_fit", "").lower():
        out.append("audience_fit 5 needs the creator's own analytics, and its evidence does not cite them")
    return out


# ---------- the run ----------

def describe_rate(e, band, pos):
    if e["rate"] is None:
        if e["rows"] == 0:
            return "engagement not computed: no posts data"
        return f"engagement not computed: none of {e['rows']} posts usable"
    text = (f"engagement {fmt(e['rate'])} pct of {e['basis']} ({e['label']}, median of {e['usable']} posts"
            f"{', ' + str(e['outside']) + ' outside the window' if e['outside'] else ''})")
    if band:
        text += f", {pos} the starting norm {band[0]} to {band[1]} pct (Estimated)"
    if e["spon"] is not None:
        text += f"; sponsored median {fmt(e['spon'])} pct over {e['n_spon']} vs other posts {fmt(e['org'])} pct over {e['n_org']}"
    return text


def rates_only(ws, longlist, order, observed, posts, as_of, s, posts_path, posts_meta):
    lines, lacking = [], []
    for key in order:
        row = longlist[key]
        tier = tier_of(row["_followers"], s)
        e = engagement(row, posts.get(key, []), as_of, s, posts_meta[4])
        band = s.get(f"norm_{e['basis']}_{tier}") if tier else None
        pos = position(e["rate"], band, s)
        conf, recent, full, computed = assess_evidence(row, e, observed, as_of, s)
        if e["rate"] is None:
            lacking.append(row["handle"])
        lines.append(f"- {row['handle']} ({row['platform']}): tier {tier or 'unknown (no followers)'}; "
              f"followers {row['followers'] or 'unknown'} ({FOLLOWER_LABELS.get(row['followers_source'], 'source not given')}); "
              f"{describe_rate(e, band, pos)}; evidence {confidence_text(conf, recent, full, computed, e, s)}")
    head = f"partial ({len(lacking)} creator(s) without usable posts data)" if lacking else "complete"
    print(f"Rates run {as_of}: {head}; nothing written")
    print("Labels: engagement " + (f"Measured (counts read off public post pages on {posts_meta[4]})" if posts_meta[4]
          else "User-provided (the posts file name states no read date)") +
          "; norms Estimated starting values (references/scoring.md section 4); followers as labelled.")
    print("\n".join(lines))
    used = f"{posts_path.name} ({posts_meta[3]} rows)" if posts_path else "no posts file"
    warnings = []
    if posts_meta[1]:
        warnings.append(f"{posts_meta[1]} posts row(s) for creators not on the longlist were ignored")
    if posts_meta[2]:
        warnings.append(f"{posts_meta[2]} duplicate post row(s) were counted once")
    if observed is None:
        warnings.append("the longlist file name carries no date, so no follower count counts as recent")
    if posts_path and posts_meta[4] is None:
        warnings.append("the posts file name carries no read date, so engagement is User-provided, not Measured")
    print(f"Coverage. Used: {len(order)} longlist rows; {used}. "
          f"Missing: {('usable posts for ' + ', '.join(lacking)) if lacking else 'nothing'}. "
          f"Could not judge: any score (this run computes numbers only). "
          f"Warnings: {'; '.join(warnings) if warnings else 'none'}. "
          f"Fine: headers valid; every number parsed.")
    return 2 if lacking else 0


def score_run(ws, args, longlist, order, observed, posts, posts_meta, as_of, s):
    rulings, program_path = check_program(ws)
    scores_path = pathlib.Path(args.scores)
    scores = load_scores(scores_path, longlist)
    roster, roster_rows, roster_merged = load_roster(ws)
    out_path = ws / "data" / f"shortlist-{as_of}.csv"
    if out_path.exists() and not args.replace:
        raise InputError(f"{out_path.name} already exists; rerun with --replace to set the old file aside "
                         f"under a dated name, or use another --as-of date.")
    results, partial, unscored, no_posts, unjudged, checks_all = [], [], [], [], [], []
    for key in order:
        row = longlist[key]
        if key not in scores:
            unscored.append(row["handle"])
            continue
        sc, ev = scores[key]["scores"], scores[key]["evidence"]
        ruling = platform_ruling(rulings, row["platform"].lower())
        tier = tier_of(row["_followers"], s)
        e = engagement(row, posts.get(key, []), as_of, s, posts_meta[4])
        band = s.get(f"norm_{e['basis']}_{tier}") if tier else None
        pos = position(e["rate"], band, s)
        conf, recent, full, computed = assess_evidence(row, e, observed, as_of, s)
        if any(v is None for v in sc.values()):
            conf = "low"
            unjudged.append(row["handle"])
        if not computed:
            no_posts.append(row["handle"])
        ref, status = "", ""
        if roster is not None:
            hit = roster.get(("h", key[0], key[1])) or roster.get(("u", norm_url(row["profile_url"])))
            if hit:
                ref, status = hit
        owner_question = OWNER_QUESTION in ev.get("brand_safety", "").lower()
        verdict, cause = verdict_for(sc, conf, ruling, status, s, owner_question)
        flag, flag_why = flag_for(verdict, sc, ev, s)
        checks = checks_for(sc, ev, e, pos)
        checks_all.extend(f"{row['handle']}: {c}" for c in checks)
        total = sum(sc.values()) if all(v is not None for v in sc.values()) else None
        followers_txt = (f"followers {row['followers']} ({FOLLOWER_LABELS.get(row['followers_source'], 'source not given')}"
                         f"{', ' + str(observed) if observed else ', date unknown'})" if row["followers"] else "followers unknown")
        parts = [f"{verdict}: {cause}", followers_txt, describe_rate(e, band, pos),
                 confidence_text(conf, recent, full, computed, e, s, unjudged=row["handle"] in unjudged)]
        if ruling[1] in ("with conditions", "unknown"):
            parts.append(f"programme section 3 for {ruling[0]}: {ruling[1]}" + (f" ({ruling[2]})" if ruling[2] else ""))
        if flag == "review":
            parts.append(f"brand_safety_flag review: {flag_why}")
        parts += [f"check: {c}" for c in checks]
        reasons = "; ".join(parts).replace("\n", " ")
        out = [row[c] for c in LONGLIST_HEADER]
        out += ["" if sc[line] is None else str(sc[line]) for line in LINES]
        out += ["" if total is None else str(total), conf, verdict, reasons, str(as_of), ref,
                tier or "", "" if e["rate"] is None else fmt(e["rate"]), flag]
        results.append({"row": out, "handle": row["handle"], "platform": row["platform"], "tier": tier, "flag": flag,
                        "rate": e, "total": total, "conf": conf, "verdict": verdict, "ref": ref, "pos": pos})

    earlier_rows, aside_note = 0, ""
    if out_path.exists():
        with out_path.open(encoding="utf-8-sig", newline="") as f:
            earlier_rows = max(0, sum(1 for _ in csv.reader(f)) - 1)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%MZ")
        aside = out_path.with_name(f"shortlist-{as_of}.replaced-{stamp}.csv")
        out_path.rename(aside)
        aside_note = f" The earlier file was set aside, unchanged, as {aside.name}."
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(SHORTLIST_HEADER)
        for r in results:
            w.writerow(r["row"])

    if no_posts:
        partial.append(f"{len(no_posts)} creator(s) without usable posts data, scored at low confidence")
    if unjudged:
        partial.append(f"{len(unjudged)} creator(s) with a line not judged")
    if unscored:
        partial.append(f"{len(unscored)} longlist row(s) not scored")
    head = "partial (" + "; ".join(partial) + ")" if partial else "complete"
    print(f"Vetting run {as_of}: {head}")
    print(f"Read: {program_path.relative_to(ws)} sections 2, 3, 9; {args.longlist} ({len(order)} rows); "
          f"{scores_path.name} ({len(scores)} rows); "
          f"{(pathlib.Path(args.posts).name + ' (' + str(posts_meta[3]) + ' rows)') if args.posts else 'no posts file'}; "
          f"data/creators.csv ({str(roster_rows) + ' row(s)' if roster is not None else 'not found'}"
          f"{', ' + str(roster_merged) + ' merged-away row(s) skipped' if roster_merged else ''}). "
          f"Wrote {out_path.relative_to(ws)}: {earlier_rows} existing rows read, {len(results)} added, 0 changed."
          + aside_note)
    print("Labels: scores and totals User-provided (the programme lead's confirmed judgments); "
          + ("engagement Measured (counts read off public post pages on " + str(posts_meta[4]) + ")" if posts_meta[4]
             else "engagement User-provided (the posts file name states no read date)" if args.posts else "no engagement")
          + "; norms Estimated starting values; followers as labelled.")
    counts = {v: sum(1 for r in results if r["verdict"] == v) for v in ("engage", "negotiate", "skip", "exclude")}
    print("Verdicts: " + ", ".join(f"{v} {n}" for v, n in counts.items()))
    for r in results:
        rate = f"{fmt(r['rate']['rate'])} pct ({r['rate']['basis']}, {r['pos'] or 'no norm'})" if r["rate"]["rate"] is not None else "not computed"
        print(f"- {r['handle']} ({r['platform']}): tier {r['tier'] or 'unknown'}; engagement {rate}; "
              f"total {r['total'] if r['total'] is not None else 'not complete'}; confidence {r['conf']}; verdict {r['verdict']}; "
              f"brand_safety_flag {r['flag']}")
    proposals = [r for r in results if r["verdict"] in ("engage", "negotiate")]
    print("Proposed roster additions (the programme lead approves the shortlist first):")
    if not proposals:
        print("- none")
    for r in proposals:
        if r["ref"]:
            print(f"- {r['handle']} ({r['platform']}), {r['verdict']}: already on the roster as {r['ref']}; "
                  f"record the new total with creator-roster update")
        else:
            print(f"- {r['handle']} ({r['platform']}), {r['verdict']}: new; creator-roster add assigns its creator_ref")
    for r in results:
        if r["verdict"] == "exclude" and r["ref"]:
            print(f"- {r['handle']} is on the roster as {r['ref']} and is now exclude; creator-roster update can record it")
    print("Checks for the programme lead:")
    for c in checks_all or ["none"]:
        print(f"- {c}")
    xlsx = ws / "data" / "creator-programme.xlsx"
    roster_csv = ws / "data" / "creators.csv"
    warnings = []
    if xlsx.exists() and roster_csv.exists() and xlsx.stat().st_mtime > roster_csv.stat().st_mtime:
        warnings.append("the workbook is newer than data/creators.csv; if it was edited, run creator-roster "
                        "import-xlsx and rerun, or creator_ref matches may be stale")
    if roster is None:
        warnings.append("no data/creators.csv, so creator_ref is empty and earlier exclusions could not be checked")
    if posts_meta[1]:
        warnings.append(f"{posts_meta[1]} posts row(s) for creators not on the longlist were ignored")
    if posts_meta[2]:
        warnings.append(f"{posts_meta[2]} duplicate post row(s) were counted once")
    if observed is None:
        warnings.append("the longlist file name carries no date, so no follower count counts as recent")
    if args.posts and posts_meta[4] is None:
        warnings.append("the posts file name carries no read date, so engagement is User-provided, not Measured; "
                        "name it posts-YYYY-MM-DD.csv for the day the counts were read")
    if roster_merged:
        warnings.append(f"{roster_merged} roster row(s) merged into another were skipped, never matched")
    missing = []
    if no_posts:
        missing.append("usable posts for " + ", ".join(no_posts))
    if unscored:
        missing.append("scores for " + ", ".join(unscored))
    if roster is None:
        missing.append("data/creators.csv")
    cannot = ["audience demographics (public signals only, unless an evidence line cites the creator's own analytics)"]
    if unjudged:
        cannot.append("the lines left empty for " + ", ".join(unjudged))
    if no_posts:
        cannot.append("engagement for " + ", ".join(no_posts))
    print("Coverage. Used: " + f"program.md sections 2, 3, 9; the longlist; the scores; "
          + ("the posts file" if args.posts else "no posts file") + "; "
          + ("the roster" if roster is not None else "no roster") + ". "
          + "Missing: " + ("; ".join(missing) if missing else "nothing") + ". "
          + "Could not judge: " + "; ".join(cannot) + ". "
          + "Warnings: " + ("; ".join(warnings) if warnings else "none") + ". "
          + "Fine: headers valid; every score in range; every line has evidence; programme sections 2 and 9 decided.")
    return 2 if partial else 0


def main():
    ap = argparse.ArgumentParser(
        description="Score a creator longlist and write data/shortlist-<as-of>.csv. Thresholds live in "
                    "references/scoring.md section 8. Exit 0 complete, 1 bad input, 2 partial.")
    ap.add_argument("workspace", help="the programme workspace folder")
    ap.add_argument("longlist", help="data/longlist-YYYY-MM-DD.csv")
    ap.add_argument("scores", nargs="?", help="the confirmed scores file (not used with --rates-only)")
    ap.add_argument("--posts", help="recent posts per creator; without it every creator is scored at low confidence")
    ap.add_argument("--as-of", required=True, help="the scoring date, YYYY-MM-DD")
    ap.add_argument("--rates-only", action="store_true", help="print tier and engagement per creator; write nothing")
    ap.add_argument("--replace", action="store_true", help="set an existing shortlist for this date aside and write anew")
    args = ap.parse_args()
    try:
        ws = pathlib.Path(args.workspace)
        if not ws.is_dir():
            raise InputError(f"the workspace {ws} is not a folder; give the programme workspace path first.")
        as_of = parse_date(args.as_of, "--as-of")
        s = load_settings()

        def resolve(p):
            path = pathlib.Path(p)
            return path if path.exists() or path.is_absolute() else ws / p

        longlist_path = resolve(args.longlist)
        longlist, order, observed = load_longlist(longlist_path)
        args.longlist = longlist_path.name
        posts, posts_meta, posts_path = {}, (0, 0, 0, 0, None), None
        if args.posts:
            posts_path = resolve(args.posts)
            p, ignored, dupes, nrows, read_date = load_posts(posts_path, longlist, as_of)
            posts, posts_meta = p, (len(p), ignored, dupes, nrows, read_date)
            args.posts = str(posts_path)
        if args.rates_only:
            return rates_only(ws, longlist, order, observed, posts, as_of, s, posts_path, posts_meta)
        if not args.scores:
            raise InputError("no scores file given; give the confirmed scores file, or use --rates-only.")
        args.scores = str(resolve(args.scores))
        return score_run(ws, args, longlist, order, observed, posts, posts_meta, as_of, s)
    except InputError as err:
        print(f"Cannot run: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
