"""Shared reading of the programme file and the workspace CSVs for affiliate-onboarding.

Standard library only. Imported by mint_codes.py, record_onboarding.py and check_kit.py,
which put this folder on sys.path themselves (they run under python3 -I).

Sources for the fixed shapes below:
- Programme file headings and line texts: the pack's programme template, version 0.1.2,
  2026-10-20 (skills/program-setup/assets/program-template.md). Its rule: the value follows
  the template's text on each line and the source mark comes last; extra detail goes on
  indented lines, each with its own mark. The template's own indented lines (instructions,
  no mark) are never read as a value.
- CSV headers and identifier shapes: the pack's schemas, 2026-10-20 (references/schemas.md,
  sections 2, 4, 5 and 9).
- Token forms for the code and link schemes: this skill's references/code-and-link-schemes.md.
"""
import csv
import datetime
import os
import re
import sys
import tempfile
import urllib.parse
from decimal import Decimal, InvalidOperation
from pathlib import Path


class InputError(Exception):
    """Bad or missing input. The message is one plain sentence saying what to fix."""


class SkipCreator(Exception):
    """This creator cannot go ahead; the message says why and what unblocks it."""


# schemas.md section 4
ROSTER_HEADER = [
    "creator_ref", "display_name", "primary_platform", "primary_handle", "profile_url",
    "other_platforms", "tier", "followers_primary", "followers_as_of", "engagement_rate_pct",
    "engagement_as_of", "niche_tags", "audience_fit_score", "brand_safety_flag", "contact_path",
    "contact_email", "status", "compensation_model", "commission_rate_pct", "flat_fee", "code",
    "affiliate_link", "rail", "agreement_date", "agreement_file", "usage_rights_until",
    "exclusivity_until", "first_campaign", "last_activity", "notes",
]
# schemas.md section 5
PIPELINE_HEADER = [
    "campaign_slug", "creator_ref", "stage", "stage_date", "next_action", "next_action_date",
    "owner_role", "last_message_date", "offer_summary", "notes",
]
# schemas.md section 9
PLAN_HEADER = [
    "creator_ref", "code", "discount_type", "discount_value", "applies_to", "starts_at",
    "ends_at", "usage_limit", "once_per_customer", "status", "minted_at", "minted_by", "notes",
]
PLAN_STATUSES = ("planned", "minted", "active", "disabled", "collision")
RAILS = ("collabs", "app", "manual")

CODE_RE = re.compile(r"^[A-Z0-9]{4,20}$")          # schemas.md section 2
REF_RE = re.compile(r"^c-[a-z0-9]{6}$")            # schemas.md section 2
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MARK_RE = re.compile(r"\s*\[(owner|observed|default|open)\]")   # template, first section
OPEN_RE = re.compile(r"\[open\]")

# Programme lines this skill reads: (section, full template text). The full text is how a
# line is found (template rule); the short prefix is a fallback for a hand-edited line.
FIELDS = {
    "currency": (1, "Store currency:", "Store currency"),
    "commission_basis": (4, "Commission basis: `subtotal after discounts, before shipping and tax` [default] or another:", "Commission basis"),
    "discount": (4, "Customer-facing discount carried by each creator's code, percent or fixed amount:", "Customer-facing discount"),
    "combining": (4, "Whether creator codes combine with other discounts (other codes, automatic discounts, free shipping), and which ones:", "Whether creator codes combine"),
    "after_window": (4, "Codes after a campaign window: `end` with the window, or `stay active` [default stay active]:", "Codes after a campaign window"),
    "code_scheme": (5, "Code scheme (how a creator's code is formed; upper case letters and digits only), for example the creator's handle without punctuation followed by the discount number:", "Code scheme"),
    "link_scheme": (5, "Link scheme: the domain and path creators link to, and the UTM convention (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content` values):", "Link scheme"),
    "attribution": (5, "Attribution model, declared once: a matching code wins; a tracked link without a code is second; nothing else is attributed [default]. Changes here change every report:", "Attribution model"),
    "holdback": (5, "Holdback before a sale counts as commissionable, in days (refund window) [default 30]:", "Holdback"),
    "store_codes": (5, "Store promotion codes that are not creators' codes (so the unattributed list shows only unknown codes), one per indented line:", "Store promotion codes"),
    "self_referral": (5, "Self-referral rule: an order placed by the creator, or shipped to the creator's own address, does not earn commission [default]:", "Self-referral rule"),
    "store": (6, "Store URL and Shopify plan:", "Store URL"),
    "rail": (6, "Rail chosen: `collabs` (Shopify Collabs), `app` (name the app), `manual` (Admin API or admin UI codes plus the pack's statement script and a payout list), `none` yet:", "Rail chosen"),
    "prerequisites": (6, "Prerequisites verified on the store, each with the date and the role that checked: Shopify Payments active, country supported, Collabs or app installed, discount-creation access, API access scope and token custodian role:", "Prerequisites verified"),
    "payout_schedule": (6, "Payout schedule (for example monthly, after the holdback) and minimum payout amount:", "Payout schedule"),
}
SECTION_TITLES = {1: "Brand and products", 3: "Platforms", 4: "Compensation", 5: "Tracking and attribution",
                  6: "Shopify and the payout rail", 7: "Approved and forbidden claims", 8: "Disclosure rules",
                  10: "Roles and approvals"}

# Roster primary_platform (schemas.md section 4) to the first word of a section 3 row.
PLATFORM_ROW = {
    "instagram": "instagram", "tiktok": "tiktok", "youtube": "youtube", "x": "x",
    "onlyfans": "onlyfans", "reddit": "reddit", "podcast": "podcasts", "newsletter": "podcasts",
    "bluesky": "other", "threads": "other", "other": "other",
}


def norm(text):
    return " ".join(text.split())


def strip_marks(text):
    return MARK_RE.sub("", text).strip()


def sec(num):
    return f"Programme section {num} ({SECTION_TITLES.get(num, '')})"


def today(arg=None):
    if arg:
        if not DATE_RE.match(arg):
            raise InputError(f"--date must be YYYY-MM-DD; got '{arg}'.")
        return arg
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


class Programme:
    """The programme file, read by its fixed numbered headings."""

    def __init__(self, path):
        self.path = path
        self.sections = {}
        current = None
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^## (\d+)\. ", line)
            if m:
                current = int(m.group(1))
                self.sections[current] = []
            elif line.startswith("## "):
                current = None
            elif current is not None:
                self.sections[current].append(line)

    @classmethod
    def load(cls, ws):
        p = ws / "program" / "program.md"
        if not p.exists():
            raise InputError(f"No programme file at {p}; run program-setup with the owner first.")
        return cls(p)

    def _bullets(self, num):
        out, cur = [], None
        for line in self.sections.get(num, []):
            if line.startswith("- "):
                cur = [line[2:].rstrip(), []]
                out.append(cur)
            elif cur is not None and line[:1] in (" ", "\t") and line.strip():
                cur[1].append(line.strip())
            else:
                cur = None
        return out

    def _line(self, key):
        """(text after the template's words on the field's line, indented lines under it), or None."""
        num, label, prefix = FIELDS[key]
        nlabel = norm(label)
        for text, cont in self._bullets(num):
            ntext = norm(text)
            if ntext.startswith(nlabel):
                return ntext[len(nlabel):], cont
            if ntext.lower().startswith(prefix.lower()):
                # Hand-edited line: take what follows the template's last word and colon.
                tail = nlabel.split()[-1]
                i = ntext.rfind(tail)
                rest = ntext[i + len(tail):] if i >= 0 else ntext[ntext.find(":", len(prefix)) + 1:]
                return rest, cont
        return None

    def field(self, key):
        """The owner's value on a template line, marks removed; None when blank or [open].

        The value is what follows the template's text on the field's own line. Indented lines
        under it are added only when they carry a source mark (the owner's detail); the
        template's own indented instructions carry none and are never part of a value.
        """
        found = self._line(key)
        if found is None:
            return None
        rest, cont = found
        if OPEN_RE.search(rest) or not strip_marks(rest):
            return None
        extra = [strip_marks(c) for c in cont if MARK_RE.search(c) and not OPEN_RE.search(c)]
        return " ".join([strip_marks(rest)] + [e for e in extra if e])

    def require(self, key, what):
        v = self.field(key)
        if v is None:
            num = FIELDS[key][0]
            raise InputError(f"{sec(num)} has no {what} (line '{FIELDS[key][2]}'); fill it with the owner through program-setup, then run this again.")
        return v

    # --- section 6 ---
    def rail(self):
        v = self.require("rail", "rail chosen")
        found = [r for r in RAILS + ("none",) if re.search(rf"(^|[^a-z]){r}([^a-z]|$)", v.lower())]
        if not found or found == ["none"]:
            raise InputError(f"{sec(6)} names no rail yet ('{v}'); the owner chooses collabs, app or manual through program-setup first.")
        if len(found) > 1:
            raise InputError(f"{sec(6)} names more than one rail ('{v}'); the programme runs one rail, so the owner settles which.")
        return found[0]

    def app_name(self):
        v = self.field("rail") or ""
        m = re.search(r"app\W*\(([^)]+)\)", v)
        return m.group(1).strip() if m else None

    def store_domain(self):
        v = self.require("store", "store URL")
        m = re.search(r"\b([a-z0-9][a-z0-9-]*\.myshopify\.com)\b", v.lower())
        if not m:
            raise InputError(f"{sec(6)} gives no myshopify.com domain on the 'Store URL' line ('{v}'); the Admin API needs it, so add it there.")
        return m.group(1)

    # --- section 5 ---
    def code_scheme(self):
        v = self.require("code_scheme", "code scheme")
        m = re.search(r"`([^`]*\{[A-Za-z]+\}[^`]*)`", v) or re.search(r"(\S*\{[A-Za-z]+\}\S*)", v)
        if not m:
            raise InputError(f"{sec(5)} describes the code scheme in words ('{v}'); write it as a template such as `{{HANDLE}}{{DISCOUNT}}` (references/code-and-link-schemes.md) so the code is built the same way every time.")
        scheme = m.group(1).strip()
        tokens = re.findall(r"\{([A-Za-z]+)\}", scheme)
        bad = [t for t in tokens if t.upper() not in ("HANDLE", "NAME", "REF", "DISCOUNT")]
        if bad:
            raise InputError(f"{sec(5)} code scheme uses an unknown token {{{bad[0]}}}; the tokens are {{HANDLE}}, {{NAME}}, {{REF}} and {{DISCOUNT}}.")
        literal = re.sub(r"\{[A-Za-z]+\}", "", scheme)
        if not re.fullmatch(r"[A-Z0-9]*", literal):
            raise InputError(f"{sec(5)} code scheme '{scheme}' has characters a code cannot hold; outside the tokens use upper case letters and digits only.")
        if not any(t.upper() in ("HANDLE", "NAME", "REF") for t in tokens):
            raise InputError(f"{sec(5)} code scheme '{scheme}' gives every creator the same code; include {{HANDLE}}, {{NAME}} or {{REF}}.")
        return scheme

    def link_scheme(self):
        v = self.require("link_scheme", "link scheme")
        m = re.search(r"(https://[^\s`\]]+)", v)
        if not m:
            raise InputError(f"{sec(5)} link scheme has no https:// address template ('{v}'); write it as in references/code-and-link-schemes.md.")
        tpl = m.group(1)
        tokens = [t.lower() for t in re.findall(r"\{([A-Za-z]+)\}", tpl)]
        bad = [t for t in tokens if t not in ("handle", "ref", "code", "platform", "campaign")]
        if bad:
            raise InputError(f"{sec(5)} link scheme uses an unknown token {{{bad[0]}}}; the tokens are {{handle}}, {{ref}}, {{code}}, {{platform}} and {{campaign}}.")
        if not any(t in ("handle", "ref", "code") for t in tokens):
            raise InputError(f"{sec(5)} link scheme gives every creator the same link, so a link could not show whose sale it was; include {{handle}}, {{ref}} or {{code}}.")
        return tpl

    def after_window(self):
        """'end', 'stay' or None, from section 4's codes-after-a-campaign-window line."""
        v = self.field("after_window")
        if v is None:
            return None
        low = v.lower().replace("`", "")
        if "stay active" in low:
            return "stay"
        if low.startswith("end"):
            return "end"
        raise InputError(f"{sec(4)} line 'Codes after a campaign window' reads '{v}'; it should say `end` or `stay active`.")

    def combines_with(self):
        """Section 4's combining line as Shopify's three discount classes, or None when unsure.

        Returns ({"orderDiscounts": bool, "productDiscounts": bool, "shippingDiscounts": bool}
        or None, the line as written or None). The rules and worked examples are in
        references/code-and-link-schemes.md section 5; anything they do not settle is None,
        so nothing is guessed and the admin setting and the test order decide.
        """
        v = self.field("combining")
        if v is None:
            return None, None
        t = v.lower().replace("free-shipping", "free shipping").replace("`", "")
        classes = {"orderDiscounts": None, "productDiscounts": None, "shippingDiscounts": None}
        lead = re.match(r"^\W*(no|none|never|yes|all)\b", t)
        default = None if not lead else lead.group(1) in ("yes", "all")
        for clause in re.split(r";|,|\bbut\b", t):
            neg = re.search(r"\b(no|not|never|none|cannot|can't|doesn't)\b", clause)
            pos = re.search(r"\b(yes|with|combines?|allowed|only|all)\b", clause)
            pol = False if neg else (True if pos else None)
            named = set()
            if "shipping" in clause:
                named.add("shippingDiscounts")
            else:
                if re.search(r"\border\b|\bcodes?\b|\bautomatic\b|\bdiscounts?\b", clause):
                    named |= {"orderDiscounts", "productDiscounts"}
                if "product" in clause:
                    named.add("productDiscounts")
            if pol is None:
                continue
            for k in named:
                classes[k] = pol
            if re.search(r"\bonly\b", clause) and pol:
                default = False
        for k, val in classes.items():
            if val is None:
                classes[k] = default
        if any(val is None for val in classes.values()):
            return None, v
        return classes, v

    def combining(self):
        """('no' | 'some' | None, the line as written): 'no' when the code combines with nothing."""
        classes, v = self.combines_with()
        if v is None:
            return None, None
        if classes is not None:
            return ("some" if any(classes.values()) else "no"), v
        return ("no" if re.match(r"^\W*(no|none|never)\b", v.lower()) and not re.search(r"\byes\b", v.lower()) else "some"), v

    def attribution_line(self, rail, app_name=None):
        """The sentence the kit gives a creator on how orders are credited, per rail.

        Manual: programme section 5's attribution model. Collabs: the pack's Shopify reference
        found no published rule for which wins when an order carries both (rails.md section 1),
        so the kit says Collabs' record decides. App: the app's own tracking decides.
        """
        if rail == "collabs":
            return ("Orders are credited to you as Shopify Collabs records them, through your link or your code, "
                    "and the brand's statement follows the Collabs report.")
        if rail == "app":
            name = app_name or "the app"
            return f"Orders are credited to you as {name} records them, and the brand's statement follows the {name} report."
        v = self.field("attribution")
        if v is None:
            raise InputError(f"{sec(5)} has no ruling on the attribution model; the owner settles the 'Attribution model' line through program-setup before the kit can say how orders are credited.")
        if re.match(r"^\W*(as written|accepted|agreed|yes|default|as stated|as above)\b", v.lower()):
            return ("An order is credited to you when it carries your code; an order that came through your link "
                    "without a code is credited second. Nothing else counts as yours.")
        return f"Orders are credited to you under the programme's rule: {v.rstrip('.')}."

    def store_codes(self):
        """Codes the store uses for its own promotions, from section 5's indented lines."""
        found = self._line("store_codes")
        if found is None:
            return []
        rest, cont = found
        codes = []
        for part in [rest] + cont:
            if OPEN_RE.search(part) or (part is not rest and not MARK_RE.search(part)):
                continue
            codes += re.findall(r"\b[A-Z0-9]{4,20}\b", strip_marks(part).replace("`", ""))
        return codes

    def holdback_days(self):
        v = self.require("holdback", "holdback in days")
        m = re.match(r"^\s*(\d+)\b", v)
        if not m:
            raise InputError(f"{sec(5)} holdback '{v}' is not a whole number of days.")
        return int(m.group(1))

    # --- section 4 and 1 ---
    def currency(self):
        v = self.field("currency")
        if not v:
            return None
        m = re.search(r"\b([A-Z]{3})\b", v)
        return m.group(1) if m else None

    def discount(self):
        """(discount_type, Decimal value) from section 4."""
        v = self.require("discount", "customer-facing discount")
        num = r"(\d+(?:\.\d+)?)"
        pct = re.search(num + r"\s*(?:%|percent\b|per cent\b|pct\b)", v, re.I)
        cur = self.currency() or "USD"
        fixed = (re.search(r"\b(?:" + cur + r"|USD)\s*" + num, v) or
                 re.search(num + r"\s*(?:" + cur + r"\b|USD\b|dollars?\b)", v, re.I))
        if pct and fixed:
            raise InputError(f"{sec(4)} customer discount '{v}' reads as both a percentage and an amount; the owner settles one.")
        if pct:
            val = Decimal(pct.group(1))
            if not (Decimal(0) < val <= Decimal(100)):
                raise InputError(f"{sec(4)} customer discount {val} percent is outside 0 to 100.")
            return "percentage", val
        if fixed:
            return "fixed_amount", Decimal(fixed.group(1)).quantize(Decimal("0.01"))
        raise InputError(f"{sec(4)} customer discount '{v}' is neither a percentage ('15 percent') nor an amount ('USD 10').")

    def commission_basis(self):
        v = self.field("commission_basis")
        return v.replace("`", "").strip() if v else None

    # --- section 3 ---
    def platform_rule(self, platform):
        """(ruling, row text) for a roster platform: ruling is yes, conditions, no, unknown or None."""
        want = PLATFORM_ROW.get((platform or "").strip().lower())
        if not want:
            return None, ""
        header_seen = False
        for line in self.sections.get(3, []):
            if not line.startswith("|"):
                header_seen = False
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not header_seen:
                header_seen = True
                continue
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                continue
            first = re.split(r"\W+", cells[0].lower().strip(), maxsplit=1)[0]
            if first != want:
                continue
            organic = strip_marks(cells[1]).strip("`").strip().lower() if len(cells) > 1 else ""
            if not organic:
                return None, line
            for ruling, pat in (("conditions", r"^with conditions"), ("yes", r"^yes\b"),
                                ("no", r"^no\b"), ("unknown", r"^unknown\b")):
                if re.match(pat, organic):
                    return ruling, line
            return None, line
        return None, ""

    def platform_ok(self, creator):
        ruling, row = self.platform_rule(creator["primary_platform"])
        plat = creator["primary_platform"] or "(blank)"
        if ruling in ("yes", "conditions"):
            return ruling
        if ruling == "no":
            raise SkipCreator(f"{sec(3)} says organic creator posts on {plat} are not allowed; the owner rules on any exception before this creator is onboarded.")
        if ruling == "unknown":
            raise SkipCreator(f"{sec(3)} marks organic creator posts on {plat} as unknown; the owner settles the row first.")
        raise SkipCreator(f"{sec(3)} has no ruling for organic creator posts on {plat}; the owner fills that row through program-setup first.")

    # --- section 10 and 7 ---
    def roles(self):
        roles = []
        header_seen = False
        for line in self.sections.get(10, []):
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not header_seen:
                header_seen = True
                continue
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                continue
            if cells and cells[0]:
                roles.append(strip_marks(cells[0]).lower())
        return roles

    def approved_claims(self):
        out, inside = [], False
        for line in self.sections.get(7, []):
            if line.startswith("### "):
                inside = line.lower().startswith("### approved")
                continue
            if inside and line.startswith("- "):
                text = strip_marks(line[2:])
                if text and not OPEN_RE.search(line):
                    out.append(text)
        return out


# --- CSV ---

def read_csv(path, header, what):
    """Rows as dicts. Refuses a file whose header differs, naming the column."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            found = next(reader)
        except StopIteration:
            raise InputError(f"{what} at {path} is empty; it needs the header row from the schemas.")
        if found != header:
            missing = [c for c in header if c not in found]
            extra = [c for c in found if c not in header]
            if missing:
                raise InputError(f"{what} at {path} is missing the column '{missing[0]}'; fix the header (creator-roster check shows the expected one).")
            if extra:
                raise InputError(f"{what} at {path} has a column the schemas do not list, '{extra[0]}'; remove it or ask the roster owner.")
            raise InputError(f"{what} at {path} has its columns in a different order from the schemas; reorder the header.")
        rows = []
        for n, values in enumerate(reader, start=2):
            if not any(v.strip() for v in values):
                continue
            if len(values) != len(header):
                raise InputError(f"{what} at {path} line {n} has {len(values)} cells where the header has {len(header)}.")
            rows.append(dict(zip(header, values)))
        return rows


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([r.get(c, "") for c in header])
    os.replace(tmp, path)


def load_roster(ws):
    p = ws / "data" / "creators.csv"
    if not p.exists():
        raise InputError(f"No roster at {p}; creator-roster creates it.")
    return p, read_csv(p, ROSTER_HEADER, "The roster")


def load_pipeline(ws):
    p = ws / "data" / "pipeline.csv"
    if not p.exists():
        return p, None
    return p, read_csv(p, PIPELINE_HEADER, "The pipeline")


def plan_files(ws):
    d = ws / "codes"
    return sorted(d.glob("code-plan-*.csv")) if d.exists() else []


def load_plans(ws):
    """{path: rows} for every code plan under codes/."""
    return {p: read_csv(p, PLAN_HEADER, "The code plan") for p in plan_files(ws)}


def codes_in_use(roster, plans, store_codes=()):
    """{CODE: [(where, creator_ref, status)]} from the roster, every code plan and section 5's store codes."""
    used = {}
    for c in store_codes:
        used.setdefault(c.upper(), []).append(("programme section 5 store promotion codes", "the store", "store promotion"))
    for r in roster:
        if r["code"].strip():
            used.setdefault(r["code"].strip().upper(), []).append(("data/creators.csv", r["creator_ref"], r["status"]))
    for p, rows in plans.items():
        for r in rows:
            if r["code"].strip():
                used.setdefault(r["code"].strip().upper(), []).append((f"codes/{p.name}", r["creator_ref"], r["status"]))
    return used


def collision_with(code, ref, used, own_ok=("planned", "minted", "active")):
    """The first use of `code` by anything other than this creator's own planned or minted row."""
    for where, other, status in used.get(code.upper(), []):
        if other == ref and (status in own_ok or where == "data/creators.csv"):
            continue
        return where, other, status
    return None


def append_note(existing, entry):
    entry = entry.replace(";", ",")
    return f"{existing};{entry}" if existing.strip() else entry


def campaign_for(ref, pipeline, stages=("agreed", "onboarded")):
    """The one campaign slug where this creator stands at one of the stages, or None and a reason."""
    if pipeline is None:
        return None, "no data/pipeline.csv"
    slugs = sorted({r["campaign_slug"] for r in pipeline if r["creator_ref"] == ref and r["stage"] in stages})
    if len(slugs) == 1:
        return slugs[0], ""
    if not slugs:
        return None, f"no pipeline row at stage {' or '.join(stages)}"
    return None, "more than one campaign in the pipeline: " + ", ".join(slugs)


# --- schemes ---

def _alnum_upper(text):
    return re.sub(r"[^A-Za-z0-9]", "", text or "").upper()


def build_code(scheme, creator, discount_type, discount_value):
    def sub(m):
        t = m.group(1).upper()
        if t == "HANDLE":
            v = _alnum_upper((creator["primary_handle"] or "").lstrip("@"))
            if not v:
                raise SkipCreator("the roster row has no primary_handle for the {HANDLE} token")
            return v
        if t == "NAME":
            v = _alnum_upper(creator["display_name"])
            if not v:
                raise SkipCreator("the roster row has no display_name for the {NAME} token")
            return v
        if t == "REF":
            return creator["creator_ref"][2:].upper()
        if t == "DISCOUNT":
            if discount_value != discount_value.to_integral_value():
                raise SkipCreator(f"the discount {discount_value} is not a whole number, so {{DISCOUNT}} cannot go in a code; set the code with --code")
            return str(int(discount_value))
        raise SkipCreator(f"unknown token {{{t}}}")
    code = re.sub(r"\{([A-Za-z]+)\}", sub, scheme)
    check_code_shape(code, skip=True)
    return code


def check_code_shape(code, skip=False):
    if not CODE_RE.match(code or ""):
        msg = (f"the code '{code}' is not 4 to 20 upper case letters and digits (schemas.md section 2)"
               + ("; set one with --code" if skip else ""))
        if skip:
            raise SkipCreator(msg)
        raise InputError(msg[0].upper() + msg[1:] + ".")


def build_link(template, creator, code, campaign):
    def sub(m):
        t = m.group(1).lower()
        if t == "handle":
            v = re.sub(r"[^a-z0-9._-]", "", (creator["primary_handle"] or "").lstrip("@").lower())
            if not v:
                raise SkipCreator("the roster row has no primary_handle for the {handle} token")
        elif t == "ref":
            v = creator["creator_ref"]
        elif t == "code":
            v = code
        elif t == "platform":
            v = (creator["primary_platform"] or "").lower()
            if not v:
                raise SkipCreator("the roster row has no primary_platform for the {platform} token")
        elif t == "campaign":
            if not campaign:
                raise SkipCreator("the link scheme needs the campaign and none is known; give --campaign")
            v = campaign
        else:
            raise SkipCreator(f"unknown token {{{t}}}")
        return urllib.parse.quote(v, safe="")
    return re.sub(r"\{([A-Za-z]+)\}", sub, template)


# --- values the welcome kit must carry, rendered one way for the kit and its check ---

def fmt_number(d):
    d = Decimal(d)
    return str(int(d)) if d == d.to_integral_value() else format(d.normalize(), "f")


def render_discount(dtype, dval, currency):
    if dtype == "percentage":
        return f"{fmt_number(dval)} percent"
    return f"{currency or 'USD'} {Decimal(dval).quantize(Decimal('0.01'))}"


def render_commission(creator, basis):
    model = creator["compensation_model"].strip()
    if model not in ("cpa", "hybrid"):
        return None
    rate = creator["commission_rate_pct"].strip()
    if not rate:
        raise InputError(f"The roster row for {creator['creator_ref']} is {model} with no commission_rate_pct; record the agreed rate with creator-roster first.")
    try:
        Decimal(rate)
    except InvalidOperation:
        raise InputError(f"The roster row for {creator['creator_ref']} has commission_rate_pct '{rate}', which is not a number.")
    return f"{fmt_number(rate)} percent of {basis or 'the commission basis in your agreement'}"


def find_creator(roster, ref):
    if not REF_RE.match(ref or ""):
        raise InputError(f"'{ref}' is not a creator_ref (c- followed by six lowercase letters or digits).")
    for r in roster:
        if r["creator_ref"] == ref:
            return r
    raise InputError(f"No creator {ref} in data/creators.csv; check the ref with creator-roster.")


def add_script_dir():
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)


class Parser:
    """argparse that exits 1 with one sentence on bad arguments (contract: 1 is bad input)."""

    @staticmethod
    def make(**kw):
        import argparse

        class P(argparse.ArgumentParser):
            def error(self, message):
                self.print_usage(sys.stderr)
                print(f"Stopped: {message}.", file=sys.stderr)
                sys.exit(1)
        return P(**kw)
