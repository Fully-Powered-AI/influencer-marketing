"""Attribution for performance-report: the programme's declared model, applied the same way on every run.

This is performance-report's own copy. commission-statement carries its own copy of the same rules inside
its script; the two are kept alike by hand, not by import, so that each skill works when installed alone.
The shared definitions are in references/schemas.md section 12.

The model (programme section 5, pack default): a code belonging to an active creator wins; a tracked link
recorded in exports/link-attribution-<period>.csv is second; nothing else is attributed (schemas.md
section 10). The orders export itself carries no link columns (shopify-affiliate-rails.md section 6).
"""
import csv
import re

CODE_THEN_LINK = "code_then_link"
CODE_ONLY = "code_only"

# schemas.md section 9 and section 10 (link file), 2026-10-20.
CODE_PLAN_HEADER = ("creator_ref,code,discount_type,discount_value,applies_to,starts_at,ends_at,usage_limit,"
                    "once_per_customer,status,minted_at,minted_by,notes").split(",")
LINK_HEADER = ["order_name", "creator_ref", "source", "exported_at"]
LINK_SOURCES = {"collabs", "app", "api", "manual"}
# Same as commission-statement: a code-plan row counts as the creator's code in these states.
LIVE_CODE_STATES = {"minted", "active"}
# schemas.md section 10: only a code (or link) belonging to an active creator attributes.
ACTIVE = "active"


class InputError(Exception):
    """Bad input the person must fix; the message is one plain sentence."""


def norm_order(name):
    return (name or "").strip().lstrip("#").strip().lower()


def split_codes(cell):
    # schemas.md section 10 (pack rule until a real export settles it): several codes in one Discount Code
    # cell are split on commas. Spaces around each code are dropped.
    return [c.strip().upper() for c in (cell or "").split(",") if c.strip()]


def read_model(value, tags):
    """Turn the programme's section 5 attribution line into a model, or raise InputError."""
    v = (value or "").lower()
    if not v and "default" in tags:
        return CODE_THEN_LINK
    if not v:
        raise InputError("program/program.md section 5 does not declare the attribution model; "
                         "fill the 'Attribution model' line with program-setup.")
    if re.search(r"\bcodes? only\b|\bonly (discount )?codes?\b", v):
        return CODE_ONLY
    if "code" in v and "link" in v and v.find("code") < v.find("link"):
        return CODE_THEN_LINK
    raise InputError("program/program.md section 5 declares an attribution model this script does not apply "
                     "('{}'); it applies 'code first, then tracked link' or 'codes only'.".format(value))


def read_exact(path, header, what):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        got = [h.strip() for h in (next(reader, None) or [])]
        if got != header:
            missing = [h for h in header if h not in got]
            extra = [h for h in got if h not in header]
            if missing or extra:
                raise InputError("{} header differs from schemas.md: missing {}, extra {}; fix the header and "
                                 "run again.".format(what, missing or "none", extra or "none"))
            raise InputError("{} has the right columns in the wrong order; restore the schemas.md order.".format(what))
        rows = []
        for n, row in enumerate(reader, start=2):
            if not any(c.strip() for c in row):
                continue
            if len(row) != len(header):
                raise InputError("{} line {} has {} cells where the header has {}.".format(what, n, len(row), len(header)))
            rows.append(dict(zip(header, [c.strip() for c in row])))
    return rows


def build_code_map(creators, code_plan_paths):
    """Map each code to (creator_ref, source). Raises InputError when two active creators share a code."""
    owner = {}
    for r in creators.values():
        c = r["code"].strip().upper()
        if not c:
            continue
        if c in owner and owner[c][0] != r["creator_ref"] and r["status"] == ACTIVE \
                and creators[owner[c][0]]["status"] == ACTIVE:
            raise InputError("code {} belongs to two active creators ({} and {}); fix it with creator-roster.".format(
                c, owner[c][0], r["creator_ref"]))
        if c not in owner or r["status"] == ACTIVE:
            owner[c] = (r["creator_ref"], "roster")
    for p in code_plan_paths:
        for row in read_exact(p, CODE_PLAN_HEADER, "codes/" + p.name):
            c = row["code"].strip().upper()
            if not c or row["status"].strip().lower() not in LIVE_CODE_STATES or row["creator_ref"] not in creators:
                continue
            if c in owner and owner[c][0] != row["creator_ref"]:
                raise InputError("code {} is the roster's code for {} and a code-plan code for {} ({}).".format(
                    c, owner[c][0], row["creator_ref"], p.name))
            owner.setdefault(c, (row["creator_ref"], "codes/" + p.name))
    return owner


def load_links(paths, creators):
    """Read the link-attribution files. Returns (links, notes); links maps an order to a creator_ref."""
    links, seen = {}, {}
    notes = {"rows": 0, "conflict": [], "not_active": [], "bad_source": 0, "files": []}
    for p in paths:
        rows = read_exact(p, LINK_HEADER, "exports/" + p.name)
        notes["files"].append(p.name)
        notes["rows"] += len(rows)
        for lr in rows:
            if lr["source"].strip().lower() not in LINK_SOURCES:
                notes["bad_source"] += 1
            k = norm_order(lr["order_name"])
            if k in seen and seen[k] != lr["creator_ref"]:
                notes["conflict"].append(lr["order_name"])
            seen.setdefault(k, lr["creator_ref"])
    conflicted = {norm_order(x) for x in notes["conflict"]}
    for k, ref in seen.items():
        if k in conflicted:
            continue
        c = creators.get(ref)
        if c is None or c["status"] != ACTIVE:
            notes["not_active"].append("#{} ({})".format(k, ref))
            continue
        links[k] = ref
    return links, notes


def attribute(order_name, code_cell, code_owner, creators, links, model):
    """Apply the model to one order.

    Returns a dict: creator_ref (or None), method ('code', 'link' or ''), conflict (list of creator_refs when
    two active creators' codes are on one order), unmatched (codes on the order that attribute to no active
    creator, with the owner if the code is known), link_overridden (the link's creator when a code won)."""
    out = {"creator_ref": None, "method": "", "conflict": [], "unmatched": [], "link_overridden": None}
    owners = []
    for c in split_codes(code_cell):
        own = code_owner.get(c)
        if own and creators[own[0]]["status"] == ACTIVE:
            owners.append(own[0])
        else:
            out["unmatched"].append((c, "{} (status {})".format(own[0], creators[own[0]]["status"] or "empty") if own else ""))
    owners = sorted(set(owners))
    link = links.get(norm_order(order_name)) if model == CODE_THEN_LINK else None
    if len(owners) > 1:
        out["conflict"] = owners
        return out
    if owners:
        out["creator_ref"], out["method"] = owners[0], "code"
        if link and link != owners[0]:
            out["link_overridden"] = link
        return out
    if link:
        out["creator_ref"], out["method"] = link, "link"
    return out
