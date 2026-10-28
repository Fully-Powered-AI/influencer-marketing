#!/usr/bin/env python3
"""Compare what each compensation model costs the brand, per order and per post.

Reads the average order value, gross margin band and store currency from
programme section 1, and the commission rate and customer discount from
section 4, when those lines are filled; every value can be given or
overridden by a flag. Prints, at the low and the high end of the margin
band: the discount, revenue per order, cost of goods and commission; the
contribution per tracked order; the highest commission rate before a
tracked order loses money; and, for flat, hybrid and gift deals, the fixed
cost per deliverable set and the tracked orders needed to cover it.

The per-order arithmetic is the pack's shared definition
(references/schemas.md section 12, "Per-order arithmetic for offers and
plans"), so this script and creator-outreach's offer_calc.py agree; the
formulas are written out in references/compensation-models.md section 2.
A deal's commission is its own rate: the programme rate for cpa and
hybrid, none for flat and gift. Rail and app fees are programme costs
recorded in costs.csv (schemas.md section 12), not per-order figures.

Every printed figure is labelled. Inputs carry the label of their source;
everything computed is Estimated (arithmetic on the inputs, not a forecast).

Exit codes: 0 every requested model was compared; 1 a required value is
missing or impossible (one sentence names the section or flag); 2 partial,
a model named in --models lacked its input and was skipped.

Run with: python3 -I compare_models.py <workspace> [flags]
"""
import argparse
import math
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path

sys.dont_write_bytecode = True  # keep the skill folder free of cache files
sys.path.insert(0, str(Path(__file__).resolve().parent))
import programme_file as pf  # noqa: E402

CENT = Decimal("0.01")
TENTH = Decimal("0.1")
HUNDRED = Decimal(100)
MODELS = ("cpa", "flat", "hybrid", "gift")


def fail(message):
    print(message)
    sys.exit(1)


def dec(text, what):
    try:
        value = Decimal(str(text))
    except InvalidOperation:
        fail(f"{what} must be a number; got '{text}'.")
    if not value.is_finite():
        fail(f"{what} must be a number; got '{text}'.")
    return value


def money(value):
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def pct(fraction):
    return str((fraction * HUNDRED).quantize(TENTH, rounding=ROUND_HALF_UP))


def pct_down(fraction):
    """A ceiling is rounded down, so the printed rate never loses money."""
    return str((fraction * HUNDRED).quantize(TENTH, rounding=ROUND_DOWN))


def from_programme(program_text, section, label_start):
    """A filled, non-open value from the programme file, else None."""
    if program_text is None:
        return None
    value, status = pf.field_value(program_text, section, label_start)
    if value is None or status in ("open", "unfilled", "missing"):
        return None
    return value


def main():
    parser = argparse.ArgumentParser(
        description="Compare cpa, flat, hybrid and gift deals per tracked order and per deliverable set.")
    parser.add_argument("workspace", help="the workspace folder; program/program.md is read when present")
    parser.add_argument("--aov", help="average order value at list price, before the creator discount (store currency)")
    parser.add_argument("--aov-measured", action="store_true",
                        help="label the average order value Measured (read from the store's own report); "
                             "a section 1 value marked [observed] is labelled so already")
    parser.add_argument("--margin", nargs=2, metavar=("LOW", "HIGH"),
                        help="gross margin band, percent, for example 55 65; on list price unless --margin-on-net-revenue")
    parser.add_argument("--margin-on-net-revenue", action="store_true",
                        help="read --margin on net revenue, the revenue per order after the customer discount (schemas.md section 12)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--discount", help="customer discount on the creator's code, percent")
    group.add_argument("--discount-fixed", help="customer discount on the creator's code, fixed amount per order")
    parser.add_argument("--commission", help="commission rate, percent of the commission basis")
    parser.add_argument("--flat-fee", help="fee per deliverable set for a flat deal (store currency)")
    parser.add_argument("--hybrid-fee", help="fee per deliverable set for a hybrid deal (store currency)")
    parser.add_argument("--gift-cost", help="cost of the product sent to one creator, shipping included (store currency)")
    parser.add_argument("--models", help="comma list from cpa,flat,hybrid,gift; default: every model whose inputs are given")
    parser.add_argument("--currency", help="store currency code; default from programme section 1")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser()
    if not workspace.is_dir():
        fail(f"The workspace folder {workspace} does not exist; pass the workspace path first.")
    program_path = workspace / "program" / "program.md"
    program_text = program_path.read_text(encoding="utf-8") if program_path.is_file() else None

    inputs = []  # (name, shown value, label and source)

    # Average order value: section 1.
    aov_source = "flag --aov"
    aov_text = args.aov
    if aov_text is None:
        value = from_programme(program_text, 1, "Average order value")
        if value is not None and pf.numbers_in(value):
            aov_text = pf.numbers_in(value)[0]
            aov_source = "programme section 1"
            # The mark decides the label, as in creator-outreach's offer_calc.py:
            # [observed] (read from the store's own report on a date) is Measured.
            if "[observed]" in value:
                args.aov_measured = True
    if aov_text is None:
        fail("Missing the average order value: fill programme section 1 ('Average order value...') or pass --aov.")
    aov = dec(aov_text, "The average order value")
    if aov <= 0:
        fail("The average order value must be above zero.")

    # Margin band: section 1, read on list price (schemas.md section 12).
    margin_source = "flag --margin, read as on list price"
    margin_on_list = True
    margin_texts = args.margin
    if margin_texts is None:
        value = from_programme(program_text, 1, "Gross margin band")
        if value and re.search(r"net revenue", value, re.IGNORECASE) and not re.search(r"list price", value, re.IGNORECASE):
            margin_on_list = False
            margin_source = "programme section 1, on net revenue (after the customer discount)"
        nums = pf.numbers_in(value) if value else []
        if nums:
            margin_texts = [nums[0], nums[1] if len(nums) > 1 else nums[0]]
            margin_source = "programme section 1"
    if margin_texts is None:
        fail("Missing the gross margin band: fill programme section 1 ('Gross margin band...') or pass --margin LOW HIGH.")
    if args.margin is not None:
        margin_on_list = not args.margin_on_net_revenue
        if args.margin_on_net_revenue:
            margin_source = "flag --margin, on net revenue (after the customer discount)"
    m_low, m_high = (dec(t, "The gross margin") / HUNDRED for t in margin_texts)
    if not (0 < m_low <= m_high < 1):
        fail("The gross margin band must be two percentages above 0 and below 100, low first.")

    # Customer discount: section 4.
    discount_source = "flag --discount-fixed" if args.discount_fixed is not None else "flag --discount"
    fixed_discount = None
    discount_fraction = None
    if args.discount_fixed is not None:
        fixed_discount = dec(args.discount_fixed, "The fixed discount")
    elif args.discount is not None:
        discount_fraction = dec(args.discount, "The discount") / HUNDRED
    else:
        value = from_programme(program_text, 4, "Customer-facing discount")
        if value is not None:
            discount_source = "programme section 4"
            bare = pf.MARK_RE.sub(" ", value)
            nums = pf.numbers_in(value)
            # The line must say which it is (programme rules ruling; read as offer_calc.py reads it).
            if bare.strip().lower().startswith("none"):
                discount_fraction = Decimal(0)
            elif not nums:
                fail("Programme section 4's customer discount has no number; write '15 percent' or 'fixed 5.00 USD'.")
            elif re.search(r"%|\bpercent\b|\bpct\b", bare, re.IGNORECASE):
                discount_fraction = dec(nums[0], "The discount") / HUNDRED
            elif re.search(r"\bfixed\b|\b[A-Z]{3}\b", bare):
                fixed_discount = dec(nums[0], "The fixed discount")
            else:
                fail("Programme section 4's customer discount does not say whether it is a percent or a fixed amount; "
                     "write '15 percent' or 'fixed 5.00 USD', or pass --discount or --discount-fixed.")
    if fixed_discount is None and discount_fraction is None:
        fail("Missing the customer discount: fill programme section 4 ('Customer-facing discount...') or pass --discount or --discount-fixed.")
    if fixed_discount is not None:
        if not (0 <= fixed_discount < aov):
            fail("The fixed discount must be at least 0 and below the average order value.")
        discount = fixed_discount
        discount_shown = f"{money(fixed_discount)} per order (fixed amount)"
    else:
        if not (0 <= discount_fraction < 1):
            fail("The discount must be a percentage from 0 to below 100.")
        discount = aov * discount_fraction
        discount_shown = f"{pct(discount_fraction)} percent"

    # Commission rate: section 4.
    commission_source = "flag --commission"
    commission_text = args.commission
    if commission_text is None:
        value = from_programme(program_text, 4, "Commission rate for")
        nums = pf.numbers_in(value) if value else []
        if nums:
            commission_text = nums[0]
            commission_source = "programme section 4"
    if commission_text is None:
        fail("Missing the commission rate: fill programme section 4 ('Commission rate for...') or pass --commission.")
    commission_rate = dec(commission_text, "The commission rate") / HUNDRED
    if not (0 <= commission_rate < 1):
        fail("The commission rate must be a percentage from 0 to below 100.")

    # Commission basis: section 4; the template default is the subtotal after discounts.
    basis_value = from_programme(program_text, 4, "Commission basis")
    basis_after = True
    basis_source = "template default" if basis_value is None else "programme section 4"
    if basis_value is not None:
        lowered = basis_value.lower()
        if "after discounts" in lowered:
            basis_after = True
        elif "before discounts" in lowered:
            basis_after = False
        else:
            fail("Programme section 4's commission basis is neither the subtotal after discounts nor before "
                 "discounts; this script computes only those two (schemas.md section 12). Ask the owner which applies.")

    currency = args.currency
    if currency is None:
        value = from_programme(program_text, 1, "Store currency")
        match = re.search(r"\b[A-Z]{3}\b", value or "")
        currency = match.group(0) if match else "store currency"

    def optional_money(text, what):
        if text is None:
            return None
        value = dec(text, what)
        if value < 0:
            fail(f"{what} cannot be negative.")
        return value

    flat_fee = optional_money(args.flat_fee, "The flat fee")
    hybrid_fee = optional_money(args.hybrid_fee, "The hybrid fee")
    gift_cost = optional_money(args.gift_cost, "The gift cost")

    available = {"cpa": True, "flat": flat_fee is not None,
                 "hybrid": hybrid_fee is not None, "gift": gift_cost is not None}
    needs = {"flat": "--flat-fee", "hybrid": "--hybrid-fee", "gift": "--gift-cost"}
    if args.models:
        requested = [m.strip() for m in args.models.split(",") if m.strip()]
        unknown = [m for m in requested if m not in MODELS]
        if unknown:
            fail(f"--models takes cpa, flat, hybrid and gift; '{unknown[0]}' is not one of them.")
    else:
        requested = [m for m in MODELS if available[m]]
    compared = [m for m in requested if available[m]]
    skipped = [m for m in requested if not available[m]]
    not_asked = [m for m in MODELS if m not in requested]

    aov_label = "Measured" if args.aov_measured else "User-provided"
    inputs.append(("average order value at list price", f"{money(aov)} {currency}", f"{aov_label}, {aov_source}"))
    inputs.append(("gross margin band", f"{pct(m_low)} to {pct(m_high)} percent", f"User-provided, {margin_source}"))
    inputs.append(("customer discount", discount_shown, f"User-provided, {discount_source}"))
    inputs.append(("commission rate", f"{pct(commission_rate)} percent of the basis", f"User-provided, {commission_source}"))
    inputs.append(("commission basis", "subtotal after discounts" if basis_after else "subtotal before discounts",
                   f"{'User-provided' if basis_value else 'default'}, {basis_source}"))
    for name, value in (("flat fee per deliverable set", flat_fee), ("hybrid fee per deliverable set", hybrid_fee),
                        ("product sent per creator", gift_cost)):
        if value is not None:
            inputs.append((name, f"{money(value)} {currency}", "User-provided, flag"))

    # Arithmetic: schemas.md section 12, per-order arithmetic for offers and plans.
    revenue = aov - discount                      # revenue per order
    base = revenue if basis_after else aov        # the commission basis
    commission = base * commission_rate           # the programme rate, for cpa and hybrid
    gift = gift_cost or Decimal(0)

    def at(margin):
        # cost of goods: on list price, or on net revenue (revenue after the discount), schemas.md section 12
        cogs = (aov if margin_on_list else revenue) * (1 - margin)
        with_commission = revenue - cogs - commission
        without_commission = revenue - cogs       # flat and gift deals carry no commission
        ceiling = without_commission / base
        return with_commission, without_commission, ceiling, cogs

    low, high = at(m_low), at(m_high)

    def breakeven(fixed, keep):
        if fixed == 0:
            return "0 (no fixed cost)"
        if keep <= 0:
            return f"never: each tracked order loses {money(-keep)}"
        return str(math.ceil(fixed / keep))

    first = "Partial comparison" if skipped else "Comparison"
    print(f"{first} of compensation models, by compare_models.py. Computed figures are Estimated: "
          "arithmetic on the inputs below, not a forecast of sales.")
    print("Inputs")
    for name, shown, label in inputs:
        print(f"  {name}: {shown} [{label}]")
    head_low, head_high = f"at {pct(m_low)} percent margin", f"at {pct(m_high)} percent margin"
    print(f"Per tracked order ({currency}, Estimated)")
    print(f"  {'':<62}{head_low:>24}{head_high:>26}")
    rows = [
        ("discount given to the customer", money(discount), money(discount)),
        ("revenue per order", money(revenue), money(revenue)),
        ("commission basis", money(base), money(base)),
        ("cost of goods per order", money(low[3]), money(high[3])),
        ("commission at the programme rate (cpa and hybrid)", money(commission), money(commission)),
        ("contribution per tracked order, cpa or hybrid", money(low[0]), money(high[0])),
        ("contribution per tracked order, flat or gift", money(low[1]), money(high[1])),
        ("highest commission rate before an order loses money (percent, rounded down)", pct_down(low[2]), pct_down(high[2])),
    ]
    for name, a, b in rows:
        print(f"  {name:<62}{a:>24}{b:>26}")
    print(f"Per deliverable set ({currency}, Estimated)")
    for model in compared:
        if model == "cpa" and gift_cost is None:
            print("  cpa: no fixed cost; the brand pays only on tracked orders (pass --gift-cost to include product sent to try)")
            continue
        if model == "cpa":
            fixed = gift
            keep = (low[0], high[0])
            what = "product sent" if gift_cost is not None else "no fixed cost entered"
        elif model == "flat":
            fixed = flat_fee + gift
            keep = (low[1], high[1])
            what = "flat fee" + (" plus product sent" if gift_cost is not None else "")
        elif model == "hybrid":
            fixed = hybrid_fee + gift
            keep = (low[0], high[0])
            what = "hybrid fee" + (" plus product sent" if gift_cost is not None else "")
        else:
            fixed = gift
            keep = (low[1], high[1])
            what = "product sent; assumes the creator carries a code, without one no order is Measured"
        print(f"  {model}: fixed cost {money(fixed)} ({what}); tracked orders to cover it: "
              f"{breakeven(fixed, keep[0])} at {pct(m_low)} percent, {breakeven(fixed, keep[1])} at {pct(m_high)} percent")
    if skipped:
        print("Skipped: " + "; ".join(f"{m} (pass {needs[m]})" for m in skipped))
    if not_asked:
        print("Not compared: " + "; ".join(f"{m} (pass {needs[m]})" for m in not_asked if m in needs))
    missing = [needs[m] for m in skipped]
    print("Coverage: inputs used are listed above"
          + ("; missing for the requested models: " + ", ".join(missing) if missing else "; nothing requested was missing")
          + ". Not included: rail and app fees, which are programme costs (schemas.md section 12). "
          "Not judged: how many orders a creator will drive, and whether creators will accept the terms.")
    return 2 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
