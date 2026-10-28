"""Owner configuration used by public-edition checks. Standard library only."""
import re

AUDIENCE_LABEL = "Audience age: applicable audience restrictions and required evidence, or none with a reason:"
MARK = re.compile(r"\[(?:owner|observed|default|open)\]")

def section_lines(text, number):
    match = re.search(rf"^## {number}\.[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1).splitlines() if match else []

def value(lines, labels):
    found = []
    for line in lines:
        if not line.startswith("- "):
            continue
        for label in labels:
            if line[2:].startswith(label):
                raw = line[2 + len(label):]
                found.append(None if "[open]" in raw else MARK.sub("", raw).strip())
                break
    # A missing or repeated field is not a decision.
    return found[0] if len(found) == 1 and found[0] else None

def brand_name(lines, explicit=None):
    if explicit is not None:
        if not explicit.strip():
            raise ValueError("--brand-name must not be blank")
        return explicit.strip()
    name = value(lines, ("Brand name:",))
    if not name:
        raise ValueError("programme section 1 needs one settled Brand name field, or pass --brand-name")
    return name

def audience_rule(lines):
    return value(lines, (AUDIENCE_LABEL, "Audience age:"))

def unrestricted(rule):
    return bool(rule and re.match(r"^(?:none|no audience age restriction|not required)\b", rule, re.I))

def claim_cues(lines, defaults):
    """An optional settled field replaces defaults; quoted phrases are literal cues."""
    raw = value(lines, ("Claim review cues:",))
    if raw is None:
        return tuple(defaults)
    if raw.lower() == "none":
        return ()
    phrases = re.findall(r'"([^"\n]+)"', raw)
    residue = re.sub(r'"([^"\n]+)"', "", raw)
    if not phrases or any(not phrase.strip() for phrase in phrases) or residue.strip(" ;,\t"):
        raise ValueError('programme section 7 Claim review cues must be quoted phrases separated by semicolons, or none')
    return tuple(phrase.strip().lower() for phrase in phrases)
