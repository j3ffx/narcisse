"""Refreshes the copy of WhatsMyName's site list that the accounts module reads.

    uv run python scripts/update-wmn.py

The list is CC BY-SA 4.0 (Micah Hoffman and contributors): the copy keeps its licence and authors,
and `wmn-source.json` records which upstream commit it is. Commit both, after a look at the diff.
"""

import json
import re
from pathlib import Path

import httpx

REPO = "WebBreacher/WhatsMyName"
DATA = Path(__file__).resolve().parents[1] / "src" / "narcisse" / "modules" / "data"

with httpx.Client(timeout=30, follow_redirects=True) as client:
    commit = client.get(f"https://api.github.com/repos/{REPO}/commits/main").json()
    sha = commit["sha"]
    date = commit["commit"]["committer"]["date"]
    response = client.get(f"https://raw.githubusercontent.com/{REPO}/{sha}/wmn-data.json")
    response.raise_for_status()
    data = response.json()

# Sites queried with a third party's API key or token are left out: Narcisse only uses what is
# public, and never someone else's credentials (CC BY-SA allows this adaptation; it is recorded).
CREDENTIALS = re.compile(
    r"[?&](api_?key|apikey|key|token|access_token|client_id|client_secret|auth)=", re.I
)
dropped = [s["name"] for s in data["sites"] if CREDENTIALS.search(s["uri_check"])]
data["sites"] = [s for s in data["sites"] if s["name"] not in dropped]

DATA.mkdir(parents=True, exist_ok=True)
(DATA / "wmn-data.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
)
source = {
    "repository": f"https://github.com/{REPO}",
    "commit": sha,
    "date": date,
    "licence": "CC BY-SA 4.0",
    "changes": f"sites queried with a third party's credentials removed: {', '.join(dropped)}",
}
(DATA / "wmn-source.json").write_text(
    json.dumps(source, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print(f"{len(data['sites'])} sites, upstream commit {sha[:7]} of {date}")
