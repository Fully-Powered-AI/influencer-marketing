"""Drive mint_codes.py's live branch with canned store answers and no network.

    python3 -I fake_live.py SCRIPT WORKSPACE ANSWERS CONFIRM

ANSWERS is a comma list, one per planned code in plan order: ok, taken, taken_code_only, refused, throttled.
CONFIRM is the typed confirmation to give, or 'expected' for the one the script asks for.
Sockets are refused throughout, so a real call would fail the case.
"""
import importlib.util
import socket
import sys

sys.dont_write_bytecode = True


def refused(*args, **kwargs):
    raise RuntimeError("network call attempted")


socket.socket.connect = refused
socket.create_connection = refused
socket.getaddrinfo = refused

script, ws, answers, confirm_arg = sys.argv[1:5]
spec = importlib.util.spec_from_file_location("mint_codes", script)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

queue = answers.split(",")
sent = []


def transport(store, version, token, body):
    sent.append(body["variables"]["input"]["code"])
    kind = queue.pop(0)
    if kind == "ok":
        return 200, {"data": {"discountCodeBasicCreate": {"codeDiscountNode": {"id": f"gid://shopify/DiscountCodeNode/{len(sent)}"}, "userErrors": []}}}
    if kind == "taken":
        return 200, {"data": {"discountCodeBasicCreate": {"codeDiscountNode": None, "userErrors": [{"field": ["basicCodeDiscount", "code"], "message": "Code must be unique. Please try a different code.", "code": "TAKEN"}]}}}
    if kind == "taken_code_only":
        # the error code alone (shopify reference 4.3), with a message the word list would miss
        return 200, {"data": {"discountCodeBasicCreate": {"codeDiscountNode": None, "userErrors": [{"field": ["basicCodeDiscount", "code"], "message": "Code is not valid for this shop.", "code": "DUPLICATE"}]}}}
    if kind == "refused":
        return 200, {"data": {"discountCodeBasicCreate": {"codeDiscountNode": None, "userErrors": [{"field": ["basicCodeDiscount", "startsAt"], "message": "Starts at is invalid"}]}}}
    if kind == "throttled":
        return 200, {"errors": [{"message": "Throttled", "extensions": {"code": "THROTTLED"}}]}
    raise SystemExit(f"unknown canned answer {kind}")


def confirm(expected):
    return expected if confirm_arg == "expected" else confirm_arg


rc = mod.main([ws, "--live", "--yes", "--date", "2026-10-20"], transport=transport, confirm=confirm,
              env={"SHOPIFY_ADMIN_TOKEN": "fixture-token-not-real"})
print(f"fake transport received {len(sent)} request(s): {', '.join(sent) or 'none'}")
sys.exit(rc)
