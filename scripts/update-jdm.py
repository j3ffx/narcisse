"""Refreshes the copy of JustDeleteMe's list of account deletion pages that the action sheets read.

    uv run python scripts/update-jdm.py

The list is MIT (Robb Lewis, the JDM Contrib Team and contributors): the copy keeps only what
the action sheets use (English and French), and `jdm-source.json` records which upstream commit
it is, with the licence notice. Commit both, after a look at the diff.
"""

import json
from pathlib import Path

import httpx

REPO = "jdm-contrib/jdm"
DATA = Path(__file__).resolve().parents[1] / "src" / "narcisse" / "remediation" / "data"
KEEP = (
    "name",
    "url",
    "url_fr",
    "difficulty",
    "notes",
    "notes_fr",
    "email",
    "email_subject",
    "email_body",
    "domains",
)

with httpx.Client(timeout=30, follow_redirects=True) as client:
    commit = client.get(f"https://api.github.com/repos/{REPO}/commits/master").json()
    sha = commit["sha"]
    date = commit["commit"]["committer"]["date"]
    raw = f"https://raw.githubusercontent.com/{REPO}/{sha}"
    response = client.get(f"{raw}/_data/sites.json")
    response.raise_for_status()
    sites = response.json()
    licence = client.get(f"{raw}/LICENSE")
    licence.raise_for_status()

kept = [
    {key: site[key] for key in KEEP if site.get(key)}
    for site in sites
    if site.get("domains") and site.get("difficulty")
]
kept.sort(key=lambda site: site["name"].casefold())

DATA.mkdir(parents=True, exist_ok=True)
(DATA / "jdm-sites.json").write_text(
    json.dumps(kept, ensure_ascii=False, indent=0) + "\n", encoding="utf-8", newline="\n"
)
source = {
    "repository": f"https://github.com/{REPO}",
    "commit": sha,
    "date": date,
    "licence": "MIT",
    "notice": licence.text.strip(),
    "changes": "only the fields Narcisse uses are kept, in English and French",
}
(DATA / "jdm-source.json").write_text(
    json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print(f"{len(kept)} sites, upstream commit {sha[:7]} of {date}")
