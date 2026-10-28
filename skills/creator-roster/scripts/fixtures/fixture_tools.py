#!/usr/bin/env python3
"""Helpers for run_fixtures.sh. Standard library only; used by the fixtures, never by the skill.

  fixture_tools.py rows CSV                         number of data rows
  fixture_tools.py cell CSV KEYCOL=KEY COLUMN        one cell's value
  fixture_tools.py set-cell CSV KEYCOL=KEY COLUMN VALUE
  fixture_tools.py serial YYYY-MM-DD                 the Excel 1900-system serial for a date
  fixture_tools.py parts XLSX                        the part names in a workbook
  fixture_tools.py edit-xlsx IN OUT OP [OP ...]      edit a workbook made by roster.py, as a person would:
      set:SHEET:KEYCOL=KEY:COLUMN=VALUE    a typed text value
      number:SHEET:KEYCOL=KEY:COLUMN=N     a typed number (Excel stores dates typed into General cells this way)
      append:SHEET:COL=VAL,COL=VAL         a new row
      drop:SHEET:KEYCOL=KEY                a deleted row
      rename:OLD:NEW                       a renamed sheet
      shared                               save every text cell as a shared string, as Excel does
  fixture_tools.py schema-drift RUNTIME_COPY PACK_SOURCE
      the runtime copy must equal the pack source apart from its first line and the
      section 1.1 "decided with ..." attribution; prints "skipped" when the pack source is absent
"""
import csv
import datetime as dt
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
T = lambda tag: f"{{{NS}}}{tag}"


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def find(header, rows, keyspec):
    col, _, key = keyspec.partition("=")
    i = header.index(col)
    return [r for r in rows if r[i] == key]


def col_letters(index):
    letters, index = "", index + 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def sheet_grid(xml):
    """Rows of (value, is_number) from a sheet roster.py wrote (inline strings)."""
    root = ET.fromstring(xml)
    grid = []
    for row in root.iter(T("row")):
        cells = {}
        for c in row.findall(T("c")):
            i = col_index(re.match(r"[A-Z]+", c.get("r")).group(0))
            t = c.find(f"{T('is')}/{T('t')}")
            cells[i] = ((t.text or "") if t is not None else "", False)
        width = max(cells) + 1 if cells else 0
        grid.append([cells.get(i, ("", False)) for i in range(width)])
    return grid


def sheet_xml(grid, shared=None):
    out = [f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="{NS}"><sheetData>']
    for r, row in enumerate(grid, start=1):
        cells = []
        for c, (value, number) in enumerate(row):
            if value == "":
                continue
            ref = f"{col_letters(c)}{r}"
            if number:
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            elif shared is not None:
                if value not in shared:
                    shared.append(value)
                cells.append(f'<c r="{ref}" t="s"><v>{shared.index(value)}</v></c>')
            else:
                esc = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{esc}</t></is></c>')
        out.append(f'<row r="{r}">{"".join(cells)}</row>')
    out.append("</sheetData></worksheet>")
    return "".join(out)


def edit_xlsx(src, dst, ops):
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    order = {"creators": 1, "pipeline": 2, "publications": 3}
    grids = {name: sheet_grid(parts[f"xl/worksheets/sheet{i}.xml"]) for name, i in order.items()}
    use_shared = False
    for op in ops:
        kind, _, rest = op.partition(":")
        if kind in ("set", "number"):
            sheet, keyspec, assign = rest.split(":", 2)
            grid = grids[sheet]
            header = [v for v, _ in grid[0]]
            keycol, _, key = keyspec.partition("=")
            column, _, value = assign.partition("=")
            for row in grid[1:]:
                while len(row) < len(header):
                    row.append(("", False))
                if row[header.index(keycol)][0] == key:
                    row[header.index(column)] = (value, kind == "number")
        elif kind == "append":
            sheet, _, assigns = rest.partition(":")
            grid = grids[sheet]
            header = [v for v, _ in grid[0]]
            row = [("", False)] * len(header)
            for pair in assigns.split(","):
                column, _, value = pair.partition("=")
                row[header.index(column)] = (value, False)
            grid.append(row)
        elif kind == "drop":
            sheet, _, keyspec = rest.partition(":")
            grid = grids[sheet]
            header = [v for v, _ in grid[0]]
            keycol, _, key = keyspec.partition("=")
            grids[sheet] = [grid[0]] + [r for r in grid[1:] if r[header.index(keycol)][0] != key]
        elif kind == "rename":
            old, _, new = rest.partition(":")
            parts["xl/workbook.xml"] = parts["xl/workbook.xml"].replace(f'name="{old}"'.encode(), f'name="{new}"'.encode())
        elif kind == "shared":
            use_shared = True
        else:
            raise SystemExit(f"unknown op {op}")
    shared = [] if use_shared else None
    for name, i in order.items():
        parts[f"xl/worksheets/sheet{i}.xml"] = sheet_xml(grids[name], shared).encode("utf-8")
    if use_shared:
        items = "".join(f'<si><t xml:space="preserve">{v.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}</t></si>' for v in shared)
        parts["xl/sharedStrings.xml"] = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<sst xmlns="{NS}" count="{len(shared)}" uniqueCount="{len(shared)}">{items}</sst>'.encode("utf-8")
        parts["xl/_rels/workbook.xml.rels"] = parts["xl/_rels/workbook.xml.rels"].replace(
            b"</Relationships>", b'<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>')
        parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
            b"</Types>", b'<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>')
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)


def main(argv):
    cmd = argv[0]
    if cmd == "rows":
        print(len(read_csv(argv[1])[1]))
    elif cmd == "cell":
        header, rows = read_csv(argv[1])
        print("\n".join(r[header.index(argv[3])] for r in find(header, rows, argv[2])))
    elif cmd == "set-cell":
        header, rows = read_csv(argv[1])
        for r in find(header, rows, argv[2]):
            r[header.index(argv[3])] = argv[4]
        with open(argv[1], "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
    elif cmd == "serial":
        print((dt.date.fromisoformat(argv[1]) - dt.date(1899, 12, 30)).days)
    elif cmd == "parts":
        with zipfile.ZipFile(argv[1]) as z:
            print("\n".join(sorted(z.namelist())))
    elif cmd == "edit-xlsx":
        edit_xlsx(argv[1], argv[2], argv[3:])
    elif cmd == "schema-drift":
        if not os.path.isfile(argv[2]):
            print("skipped: the pack source is not beside this skill (installed alone)")
            return 0
        mask = lambda text: re.sub(r"\(decided with [^,]+, 2026-10-20", "(decided with ROLE, 2026-10-20", text)
        runtime = open(argv[1], encoding="utf-8").read().split("\n", 1)[1]
        source = open(argv[2], encoding="utf-8").read()
        if mask(runtime) != mask(source):
            print("DRIFT: references/schemas.md differs from the pack's references/schemas.md")
            return 1
        print("same as the pack source")
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
