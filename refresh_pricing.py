#!/usr/bin/env python3
"""Safely refresh the embedded dashboard from official pricing pages.

This intentionally updates only records it can positively identify. It writes a
timestamped audit report and leaves model-guide.html untouched if parsing fails.
No API key is needed.
"""
from __future__ import annotations
import datetime as dt, json, re, sys, urllib.request
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
DASHBOARD = HERE / "index.html"
AUDIT = HERE / "pricing-refresh-audit.json"
SOURCES = {
    "OpenAI": "https://developers.openai.com/api/docs/pricing",
    "Anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
}
# Name in the dashboard -> exact visible model name on the provider pricing page.
TARGETS = {"OpenAI": {"GPT-6 Astra": "gpt-6-astra", "GPT-6.1 Sol": "gpt-6.1-sol", "GPT-6 Luna": "gpt-6-luna",
                      "GPT-5.6 Sol": "gpt-5.6-sol", "GPT-5.6 Terra": "gpt-5.6-terra", "GPT-5.6 Luna": "gpt-5.6-luna", "GPT-5.5": "gpt-5.5"},
           "Anthropic": {"Claude Fable 5.1": "Claude Fable 5.1", "Claude Opus 5.5": "Claude Opus 5.5", "Claude Sonnet 5.5": "Claude Sonnet 5.5", "Claude Haiku 4.5": "Claude Haiku 4.5"}}

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "model-guide-refresh/1.0 (+local dashboard)"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", "replace")

class TableReader(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows = []; self.row = None; self.cell = None
    def handle_starttag(self, tag, attrs):
        if tag == "tr": self.row = []
        elif tag in ("td", "th") and self.row is not None: self.cell = []
    def handle_data(self, value):
        if self.cell is not None: self.cell.append(value)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip()); self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row: self.rows.append(self.row)
            self.row = None

def table_rows(text: str) -> list[list[str]]:
    parser = TableReader(); parser.feed(text); return parser.rows

def dollars(value: str) -> float:
    m = re.search(r"\$\s*([0-9]+(?:\.[0-9]+)?)", value)
    if not m: raise ValueError(f"not a dollar value: {value!r}")
    return float(m.group(1))

def rate(rows: list[list[str]], provider: str, model: str, raw: str) -> tuple[float, float]:
    # First matching row is the provider's Standard/Base pricing table.
    for row in rows:
        label = row[0].lower()
        if (provider == "OpenAI" and (label == model.lower() or label.startswith(model.lower() + " ("))) or (provider == "Anthropic" and label.startswith(model.lower())):
            if provider == "OpenAI" and len(row) >= 5: return dollars(row[1]), dollars(row[4])
            if provider == "Anthropic" and len(row) >= 3: return dollars(row[1]), dollars(row[2])
    # Some OpenAI "All models" rows are present in the page's serialized table
    # data but not in the initially rendered tab. The serialized column order is
    # model, input, cached input, cache writes, output.
    if provider == "OpenAI":
        pattern = (r"\[0,&quot;" + re.escape(model) +
                   r"(?:&quot;|[^\]]+?&quot;)\],\[0,([0-9.]+)\],\[0,[^\]]+\],\[0,[^\]]+\],\[0,([0-9.]+)\]")
        m = re.search(pattern, raw, re.I)
        if m: return float(m.group(1)), float(m.group(2))
    raise ValueError(f"standard/base pricing row not found for: {model}")

def main() -> int:
    page = DASHBOARD.read_text()
    m = re.search(r"PRICING_DATA_START\s*([\s\S]*?)\s*PRICING_DATA_END", page)
    if not m: raise RuntimeError("dashboard data marker missing")
    data = json.loads(m.group(1)); audit = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(), "sources": SOURCES, "changes": [], "errors": []}
    fetched = {}; rows = {}
    for provider, url in SOURCES.items():
        try:
            fetched[provider] = fetch(url); rows[provider] = table_rows(fetched[provider])
        except Exception as exc: audit["errors"].append(f"{provider}: fetch failed: {exc}")
    if audit["errors"]:
        AUDIT.write_text(json.dumps(audit, indent=2) + "\n"); print("No update: source fetch failed."); return 1
    try:
        for record in data["models"]:
            provider = record["provider"]
            source_name = TARGETS.get(provider, {}).get(record["name"])
            if not source_name: continue
            new_input, new_output = rate(rows[provider], provider, source_name, fetched[provider])
            if (record["input"], record["output"]) != (new_input, new_output):
                audit["changes"].append({"model": record["name"], "from": [record["input"], record["output"]], "to": [new_input, new_output]})
                record["input"], record["output"] = new_input, new_output
        data["updated"] = dt.date.today().isoformat()
    except Exception as exc:
        audit["errors"].append(str(exc)); AUDIT.write_text(json.dumps(audit, indent=2) + "\n"); print("No update: parser verification failed."); return 1
    replacement = "PRICING_DATA_START\n" + json.dumps(data, indent=2) + "\nPRICING_DATA_END"
    DASHBOARD.write_text(page[:m.start()] + replacement + page[m.end():])
    AUDIT.write_text(json.dumps(audit, indent=2) + "\n")
    print("Updated dashboard; changes:", len(audit["changes"]))
    return 0

if __name__ == "__main__": sys.exit(main())
