#!/usr/bin/env python3
"""
build-index.py  —  VibhillionAI · India Year Book 2026 (Bharat 2026) viewer

Looks at the chapter pages you push into the  chapters/  folder, e.g.

    chapters/iyb2026_part03_ch3.html          (chapter 3 — Polity)
    chapters/iyb2026_part21_ch21-22.html      (one file that covers chapters 21 and 22)

and writes content-index.json, which index.html fetches on load.

* The file name must contain  ch<number>  (ch3, ch12, ch21-22 ...). That number is how the chapter
  is placed under the right Part of the book (see PARTS below).
* The chapter title and section headings are read from the page itself (<title> and <h2>).
* Chapters that have no file yet show as "Coming soon" in the app.

Run by the GitHub Pages workflow on every push — nothing to run by hand. Standard library only.
"""
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOLDER = "chapters"
OUT = ROOT / "content-index.json"

# --------------------------------------------------------------------------------------------
# The book's 9 Parts and 32 chapters. Titles here are only the default for chapters that have no
# file yet; once a file is pushed, the title written inside that file is used instead.
# If a title below is not exactly how the book names it, just edit it here.
# --------------------------------------------------------------------------------------------
PARTS = [
    ("I",    "Land, People & Jurisprudence",   [(1, "Land and the People"), (2, "National Symbols"), (3, "Polity"),
                                                 (4, "Defence"), (5, "Law and Justice"), (6, "India and the World")]),
    ("II",   "Economy, Labour & Finance",      [(7, "Basic Economic Data"), (8, "Finance"), (9, "Corporate Affairs"),
                                                 (10, "Commerce"), (11, "Industry"), (12, "Labour, Skill Development and Employment")]),
    ("III",  "Human Resources",                [(13, "Health and Family Welfare"), (14, "Education"), (15, "Welfare")]),
    ("IV",   "Farmers & Civil Supplies",       [(16, "Agriculture and Farmers' Welfare"), (17, "Food, Public Distribution and Consumer Affairs")]),
    ("V",    "Infrastructure",                 [(18, "Planning and Development"), (19, "Rural Development"), (20, "Housing and Urban Affairs"), (21, "Transport")]),
    ("VI",   "Energy & Resources",             [(22, "Energy"), (23, "Water Resources"), (24, "Environment, Forests and Climate Change")]),
    ("VII",  "Information & Communication",    [(25, "Communications and IT"), (26, "Mass Communication")]),
    ("VIII", "Science, Culture & Sports",      [(27, "Culture and Tourism"), (28, "Science and Technology"), (29, "Youth Affairs and Sports")]),
    ("IX",   "Federal Structure & Events",     [(30, "States and Union Territories"), (31, "National Events Diary"), (32, "General Information and Appendices")]),
]
KNOWN = {n for _, _, chs in PARTS for n, _ in chs}


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.h2 = []
        self._in_title = False
        self._in_h2 = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag == "h2":
            self._in_h2, self._buf = True, []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "h2" and self._in_h2:
            self._in_h2 = False
            t = clean("".join(self._buf))
            if t and t not in self.h2:
                self.h2.append(t)

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_h2:
            self._buf.append(data)


def chapter_numbers(name):
    """ch3 -> [3];  ch21-22 / ch21_22 / ch21_ch22 -> [21, 22]"""
    m = re.search(r"ch(?:apter)?[-_ ]?(\d{1,2})(?:[-_ ]+(?:ch(?:apter)?[-_ ]?)?(\d{1,2}))?", name, re.I)
    if not m:
        return []
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) else a
    if b < a or b - a > 6:
        b = a
    return list(range(a, b + 1))


def page_title(raw, nums):
    t = clean(raw)
    if "|" in t:
        t = clean(t.split("|")[-1])
    t = re.sub(r"^ch(?:apter)?\.?\s*\d+(?:\s*[-–&,]\s*\d+)*\s*[:.\-–·]?\s*", "", t, flags=re.I)
    return t


def main():
    files, skipped, warnings = {}, [], []
    folder = ROOT / FOLDER
    if folder.is_dir():
        for f in sorted(folder.iterdir()):
            if not f.is_file() or f.name.startswith(".") or f.suffix.lower() != ".html":
                continue
            nums = chapter_numbers(f.stem)
            if not nums:
                skipped.append(f"{FOLDER}/{f.name}  (file name needs ch<number>, e.g. iyb2026_part03_ch3.html)")
                continue
            unknown = [n for n in nums if n not in KNOWN]
            if unknown:
                skipped.append(f"{FOLDER}/{f.name}  (chapter {unknown[0]} is not in the book's 1-32 list)")
                continue
            p = PageParser()
            p.feed(f.read_text(encoding="utf-8", errors="replace"))
            title = page_title(p.title, nums)
            if not title:
                warnings.append(f"{FOLDER}/{f.name}: no <title> found, using the default chapter name")
            entry = {"path": f"{FOLDER}/{f.name}", "title": title, "sections": p.h2[:60], "chapters": nums}
            for n in nums:
                if n in files:
                    warnings.append(f"chapter {n} appears in two files ({files[n]['path']} and {entry['path']}); using the second")
                files[n] = entry

    parts = []
    n_ready = 0
    for roman, name, chs in PARTS:
        out = []
        for n, default in chs:
            e = files.get(n)
            row = {"n": n, "title": default, "ready": bool(e)}
            if e:
                n_ready += 1
                row.update(path=e["path"], sections=e["sections"], span=e["chapters"])
                if e["title"] and len(e["chapters"]) == 1:
                    row["title"] = e["title"]
                elif e["title"]:
                    row["fileTitle"] = e["title"]      # one file covering several chapters
            out.append(row)
        parts.append({"roman": roman, "name": name, "chapters": out})

    index = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "parts": parts}
    OUT.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"content-index.json written: {n_ready} of {len(KNOWN)} chapters have a page")
    ready = sorted(files)
    print("  ready chapters:", ", ".join(map(str, ready)) if ready else "none yet")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print("  -", w)
    if skipped:
        print("\nSkipped (not picked up by the viewer):")
        for s in skipped:
            print("  -", s)
    if not folder.is_dir():
        print(f"\nNo '{FOLDER}' folder yet. Add e.g. {FOLDER}/iyb2026_part01_ch1.html and push again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
