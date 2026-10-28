#!/usr/bin/env python3
"""List candidate red-flag lines and missing clauses in terms an agency or a creator sent.

  python3 -I scan_incoming.py <workspace> <paper.txt> --creator <creator_ref>

A pattern scan, not the review: it finds lines worth reading and clauses it could not find,
and prints the roster's and programme's values beside them. A clause written in other words is
not caught, so every term is still read against references/terms-checklist.md. Each flag carries
the ID of its row in references/red-flags.md. Nothing is written.

Exit 0: the scan ran and flagged nothing (this is not a clean bill; the reading still happens).
Exit 1: bad input; the message says what to fix.
Exit 2: the scan ran and flagged lines, missing clauses or mismatches; each is printed.
"""

import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "references"))
from brand_context import audience_rule, unrestricted, section_lines

sys.dont_write_bytecode = True  # keep the skill folder free of caches
sys.path.insert(0, str(Path(__file__).resolve().parent))
from terms_lib import (  # noqa: E402
    CREATOR_REF, InputError, Parser, Programme, contains_run, read_roster, read_text, roster_row,
    to_decimal,
)

I = re.I
# Candidate patterns, one entry per red flag in references/red-flags.md. A line that matches
# is printed for the reader to confirm or dismiss; the reader decides, not the pattern.
CANDIDATES = [
    ("RF1", "rights with no end or no limit",
     re.compile(r"perpetu|irrevocab|unlimited (?:use|usage|rights?|licen[cs]e|media)|now known or (?:hereafter|later) (?:devised|developed)|throughout the universe|works? (?:made )?for hire|assign(?:s|ment)? (?:of )?all (?:right|title)", I)),
    ("RF2", "exclusivity (check that it is paid for and bounded)",
     re.compile(r"exclusiv|non-?compet|shall not (?:promote|endorse|work with)|refrain from (?:promoting|endorsing)", I)),
    ("RF4", "automatic renewal",
     re.compile(r"auto(?:matic(?:ally)?)?[- ]?renew|renew(?:s|ed)? automatically|evergreen|successive (?:terms|periods)", I)),
    ("RF6", "approval that amounts to scripting",
     re.compile(r"\bscript|verbatim|word[- ]for[- ]word|unlimited (?:revisions|rounds|edits)|as many (?:revisions|rounds)|sole (?:and absolute )?discretion|re-?shoot|final cut", I)),
    ("RF7", "disclosure wording that does not count on its own",
     re.compile(r"#sp\b|#spon\b|#collab|#ambassador|#partner\b|\bgifted\b|\bthanks to\b|#comped|#hosted", I)),
    ("RF11", "paid use of the creator's content or identity",
     re.compile(r"whitelist|allowlist|spark ads?|\bboost|dark post|paid (?:ads|advertising|media|amplification|social)|branded content ads|partnership ads", I)),
    ("RF14", "code or link control moving away from the brand",
     re.compile(r"(?:creator|influencer|talent)\b.{0,60}\b(?:own|retain|keep)s?\b.{0,40}\b(?:code|link)|(?:code|link)\b.{0,60}\b(?:survive|after (?:termination|expiry)|remain active)|coupon|deal sites?", I)),
    ("RF16", "termination for one side only",
     re.compile(r"(?:brand|company|client|agency|creator|influencer|talent) (?:alone )?may terminate|may terminate(?:\s+this\s+agreement)?\s+(?:at any time|for any reason)", I)),
    ("RF17", "text addressed to an assistant, not a term",
     re.compile(r"ignore (?:all |any )?(?:previous|prior|above|earlier) instructions|disregard (?:all |any )?(?:previous |prior )?instructions|\bas an ai\b|you are (?:an? )?(?:ai|assistant|language model)|(?:assistant|\bai\b|model|claude|chatgpt)[,:]? (?:must|should|please|will) (?:approve|accept|sign|ignore|mark|treat)|system prompt", I)),
]
NOT_EXCLUSIVE = re.compile(r"non-?exclusive|no exclusivity|not exclusive", I)
# Clauses the paper should have; absence is a flag (references/red-flags.md).
PRESENCE = [
    ("RF7", "a disclosure clause", re.compile(r"disclos|#ad\b|\bad:|paid partnership|sponsored|endorsement guide|\bftc\b|material connection", I)),
    ("RF8", "a product-claims clause", re.compile(r"product claims?|claims? about the products?|approved (?:statements|messaging|talking points|copy|claims)|substantiat|\bfda\b|medical device|health claims?", I)),
    ("RF12", "the configured creator eligibility and audience clause", re.compile(r"\b18\b|eighteen|\badults?\b|age (?:gate|restrict|setting|verification)|minimum age|legal age", I)),
    ("RF13", "a governing-law clause", re.compile(r"governed by|governing law|laws of the|jurisdiction", I)),
    ("RF16", "a termination clause", re.compile(r"terminat", I)),
]
# Read-and-compare lines: printed with the programme's value, flagged only on a mismatch.
PAYMENT_LINE = re.compile(r"\b(?:pay|paid|payment|payable|invoice|remit|commission)", I)
DAYS = re.compile(r"\bnet[- ]?(\d+)\b|\bwithin (\d+) (?:business |calendar )?days|\b(\d+) (?:business |calendar )?days (?:after|following|from|of)", I)
COMMISSION_LINE = re.compile(r"commission|revenue share|rev[- ]share|of (?:net |gross )?(?:sales|revenue)", I)
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b|per cent\b)", I)
GROSS = re.compile(r"\bgross\b|total (?:order )?value|including (?:shipping|tax)|before discounts?", I)
FEE_IN_CPA = re.compile(r"guarantee|minimum (?:fee|payment|earnings)|retainer|\badvance\b|up-?front|flat fee|base fee|deposit", I)
INDEMNITY = re.compile(r"indemnif|hold (?:\w+ )?harmless", I)
CONFIDENTIAL = re.compile(r"confidential|non-?disclosure|\bnda\b", I)
GOVERNING = PRESENCE[3][2]
PLATFORM_WORDS = [
    ("instagram", re.compile(r"\binstagram\b|\breels?\b", I)),
    ("tiktok", re.compile(r"\btik ?tok\b", I)),
    ("youtube", re.compile(r"\byoutube\b|\bshorts\b", I)),
    ("x", re.compile(r"\btwitter\b|\bx\.com\b|\bon x\b", I)),
    ("onlyfans", re.compile(r"\bonlyfans\b", I)),
    ("reddit", re.compile(r"\breddit\b|\bsubreddit", I)),
    ("podcast", re.compile(r"\bpodcast", I)),
    ("newsletter", re.compile(r"\bnewsletter", I)),
    ("bluesky", re.compile(r"\bbluesky\b", I)),
    ("threads", re.compile(r"\bthreads\b", I)),
]
OTHER_PLATFORMS = re.compile(r"\bgrindr\b|\bscruff\b|\bsnapchat\b|\bfacebook\b|\btwitch\b", I)


def snippet(text, width=200):
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 3] + "..."


def main(argv=None):
    parser = Parser(
        description="Pattern-scan incoming terms for candidate red flags, beside the roster's and programme's values.",
        epilog="Exit 0 nothing flagged, 1 bad input, 2 flags printed. A scan is not a review. Nothing is written.")
    parser.add_argument("workspace", help="the programme workspace folder")
    parser.add_argument("paper", help="the incoming terms as a text or Markdown file, for example exports/incoming-terms-c-7k2m9q-2026-10-20.txt")
    parser.add_argument("--creator", required=True, metavar="CREATOR_REF", help="the roster ref of the creator the paper is for")
    args = parser.parse_args(argv)
    try:
        return scan(args)
    except InputError as err:
        print(f"scan_incoming: {err}")
        print("RESULT: FAIL (exit 1): bad input.")
        return 1


def scan(args):
    ws = Path(args.workspace)
    if not ws.is_dir():
        raise InputError(f"{ws} is not a folder; give the workspace path first.")
    if not CREATOR_REF.match(args.creator):
        raise InputError(f"'{args.creator}' is not a roster ref (c- and six lower-case letters or digits).")
    paper = Path(args.paper)
    if not paper.is_absolute() and not paper.exists():
        paper = ws / args.paper
    text = read_text(paper)
    lines = text.splitlines()
    if not any(l.strip() for l in lines):
        raise InputError(f"{paper} has no text; if it is a scan, get a text copy or paste the terms, then run again.")
    prog = Programme(ws)
    row = roster_row(read_roster(ws), args.creator)

    _, holdback = prog.field(5, r"^holdback")
    _, schedule = prog.field(6, r"payout schedule")
    _, law = prog.field(11, r"governing")
    _, window = prog.field(11, r"usage.rights|reus")
    _, exclusivity = prog.field(11, r"exclusivity")
    _, wording = prog.field(8, r"^required disclosure")
    model = row["compensation_model"].lower()
    rate = to_decimal(row["commission_rate_pct"]) if row["commission_rate_pct"] else None
    holdback_days = to_decimal(holdback) if holdback else None

    flags, reads = [], []
    numbered = list(enumerate(lines, 1))
    for rf, what, rx in CANDIDATES:
        for n, line in numbered:
            if rx.search(line):
                if rf == "RF2" and NOT_EXCLUSIVE.search(line) and not re.search(r"shall not|refrain|non-?compet", line, I):
                    reads.append(f"READ  RF2 L{n}: says non-exclusive: \"{snippet(line)}\"")
                    continue
                if rf == "RF17":
                    flags.append(f"FLAG  RF17 L{n}: text addressed to an assistant; noted in the memo and not acted on: \"{snippet(line)}\"")
                    continue
                flags.append(f"FLAG  {rf} L{n}: {what}: \"{snippet(line)}\"")
    age_rule = audience_rule(section_lines((ws / "program/program.md").read_text(encoding="utf-8"), 9))
    for rf, what, rx in PRESENCE:
        if rf == "RF12" and unrestricted(age_rule):
            continue
        if not any(rx.search(l) for l in lines):
            flags.append(f"ABSENT {rf}: no line looks like {what}; read the paper for it in other words, and if it is truly absent it is a red flag.")
    quoted = re.findall(r"[\"\u201c]([^\"\u201d]+)[\"\u201d]", wording or "")
    if wording:
        # Section 8's quoted wording (or, with none quoted, its whole text) found in the paper as a run of words.
        hit = any(contains_run(text, q) for q in quoted) if quoted else contains_run(text, wording)
        (reads if hit else flags).append(
            ("READ  RF7: " if hit else "FLAG  RF7: ") +
            ("some of programme section 8's wording appears in the paper; check it is all there and placed as section 8 says."
             if hit else "programme section 8's disclosure wording does not appear in the paper."))
    else:
        flags.append("FLAG  RF7: programme section 8 has no required disclosure wording, so the paper's disclosure clause cannot be compared; the owner fills section 8.")
    for n, line in numbered:
        if COMMISSION_LINE.search(line):
            for m in PERCENT.finditer(line):
                value = to_decimal(m.group(1))
                if rate is None:
                    flags.append(f"FLAG  RF9 L{n}: the paper says {m.group(1)} percent; the roster has no commission rate for {args.creator} to compare with.")
                elif value != rate:
                    flags.append(f"FLAG  RF9 L{n}: the paper says {m.group(1)} percent; the roster says {row['commission_rate_pct']}: \"{snippet(line)}\"")
                else:
                    reads.append(f"READ  RF9 L{n}: {m.group(1)} percent matches the roster.")
            if GROSS.search(line):
                flags.append(f"FLAG  RF9 L{n}: commission basis may differ from programme section 4: \"{snippet(line)}\"")
        if PAYMENT_LINE.search(line):
            for m in DAYS.finditer(line):
                days = to_decimal(next(g for g in m.groups() if g))
                if holdback_days is None:
                    flags.append(f"FLAG  RF3 L{n}: payment in {days} days; programme section 5 has no holdback to compare with.")
                elif days != holdback_days:
                    side = "before" if days < holdback_days else "after"
                    flags.append(f"FLAG  RF3 L{n}: payment in {days} days, {side} the programme's {holdback} day holdback (payout schedule: {schedule or 'blank'}): \"{snippet(line)}\"")
                else:
                    reads.append(f"READ  RF3 L{n}: payment in {days} days, the same as the holdback.")
        if model == "cpa" and FEE_IN_CPA.search(line):
            flags.append(f"FLAG  RF10 L{n}: a fee or guarantee in what the roster records as a pay-per-sale deal: \"{snippet(line)}\"")
        if INDEMNITY.search(line):
            reads.append(f"READ  RF5 L{n}: indemnity; check it runs both ways and matches who controls what: \"{snippet(line)}\"")
        if CONFIDENTIAL.search(line):
            reads.append(f"READ  RF15 L{n}: confidentiality; check it cannot be read to limit disclosure: \"{snippet(line)}\"")
        if GOVERNING.search(line):
            if law and contains_run(line, law):
                reads.append(f"READ  RF13 L{n}: names the programme's governing law ({law}).")
            else:
                flags.append(f"FLAG  RF13 L{n}: governing law or jurisdiction; programme section 11 says '{law or 'blank'}': \"{snippet(line)}\"")
        for platform, rx in PLATFORM_WORDS:
            if rx.search(line):
                hit = prog.platform(platform)
                organic, paid = (hit[1], hit[2]) if hit else ("no row", "no row")
                entry = f"RF11 L{n}: mentions {platform}; programme section 3 creator posts '{organic or 'blank'}', paid by the brand '{paid or 'blank'}'"
                if organic in ("no", "unknown", "", "no row"):
                    flags.append("FLAG  " + entry + f": \"{snippet(line)}\"")
                else:
                    reads.append("READ  " + entry + ".")
        if OTHER_PLATFORMS.search(line):
            flags.append(f"FLAG  RF11 L{n}: names a platform outside the roster's list; check programme section 3: \"{snippet(line)}\"")

    words = len(text.split())
    print(f"scan_incoming: {paper}, {len(lines)} lines, {words} words, for {args.creator}")
    print("A pattern scan: it lists lines to read and clauses it could not find. It is not the review, and a clause in other words is not caught.")
    print("Values to compare against (copy these into the memo's programme column):")
    print(f"  roster {args.creator}: model {model or '(empty)'}, commission {row['commission_rate_pct'] or '(empty)'} percent, flat fee {row['flat_fee'] or '(empty)'}")
    print(f"  programme section 5, holdback days: {holdback or '(blank)'}")
    print(f"  programme section 6, payout schedule: {schedule or '(blank)'}")
    print(f"  programme section 11, governing law: {law or '(blank)'}")
    print(f"  programme section 11, usage-rights window: {window or '(blank)'}")
    print(f"  programme section 11, default exclusivity: {exclusivity or '(blank)'}")
    print(f"  programme section 8, required disclosure wording: {wording or '(blank)'}")
    for item in flags:
        print(item)
    for item in reads:
        print(item)
    ids = sorted({re.search(r"RF\d+", f).group(0) for f in flags}, key=lambda s: int(s[2:]))
    code = 2 if flags else 0
    print(f"RESULT: {'FLAGS' if flags else 'NOTHING FLAGGED'} (exit {code}): {len(flags)} flags ({', '.join(ids) or 'none'}), {len(reads)} lines to read. The checklist reading is still required.")
    return code


if __name__ == "__main__":
    sys.exit(main())
