"""Refreshes the copy of IANA's registry data that the domain registration module reads.

    uv run python scripts/update-registries.py

Writes `registries.json`: the RDAP server of each top-level domain (IANA's bootstrap file), the
hosts of the registrars' RDAP servers (IANA's registrar IDs), and, for the top-level domains
without RDAP, their WHOIS server (asked of whois.iana.org, one at a time). `registries-source.json`
records when. Commit both, after a look at the diff.
"""

import csv
import io
import json
import socket
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

DATA = Path(__file__).resolve().parents[1] / "src" / "narcisse" / "modules" / "data"
BOOTSTRAP = "https://data.iana.org/rdap/dns.json"
TLDS = "https://data.iana.org/TLD/tlds-alpha-by-domain.txt"
REGISTRARS = "https://www.iana.org/assignments/registrar-ids/registrar-ids-1.csv"
USER_AGENT = "Narcisse registry data refresh (+https://github.com/j3ffx/narcisse)"


def whois_server(tld: str) -> str | None:
    """The WHOIS server IANA lists for a top-level domain, if any."""
    with socket.create_connection(("whois.iana.org", 43), timeout=20) as connection:
        connection.sendall(f"{tld}\r\n".encode())
        answer = b""
        while chunk := connection.recv(65536):
            answer += chunk
    for line in answer.decode("utf-8", "replace").splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "whois" and value.strip():
            return value.strip().lower()
    return None


with httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT}) as client:
    bootstrap = client.get(BOOTSTRAP).raise_for_status().json()
    tlds = [
        line.strip().lower()
        for line in client.get(TLDS).raise_for_status().text.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    registrars_csv = client.get(REGISTRARS).raise_for_status().text

rdap = {
    tld.lower(): urls[0] if urls[0].endswith("/") else f"{urls[0]}/"
    for tlds_of_service, urls in bootstrap["services"]
    for tld in tlds_of_service
}
registrars = sorted(
    {
        host
        for row in csv.DictReader(io.StringIO(registrars_csv))
        if row["Status"] == "Accredited"
        and (host := urlsplit(row["RDAP Base URL"].strip()).hostname)
    }
)
whois: dict[str, str] = {}
for tld in tlds:
    if tld in rdap or tld == "arpa":
        continue
    if server := whois_server(tld):
        whois[tld] = server
    time.sleep(1)  # whois.iana.org is a shared service

DATA.mkdir(parents=True, exist_ok=True)
(DATA / "registries.json").write_text(
    json.dumps(
        {"rdap": dict(sorted(rdap.items())), "registrars": registrars, "whois": whois},
        indent=1,
    )
    + "\n",
    encoding="utf-8",
    newline="\n",
)
source = {
    "rdap": BOOTSTRAP,
    "rdap_published": bootstrap.get("publication"),
    "registrars": REGISTRARS,
    "whois": "whois.iana.org, for the top-level domains without RDAP",
    "fetched": datetime.now(UTC).strftime("%Y-%m-%d"),
}
(DATA / "registries-source.json").write_text(
    json.dumps(source, indent=2) + "\n", encoding="utf-8", newline="\n"
)
print(f"{len(rdap)} TLDs with RDAP, {len(registrars)} registrar hosts, {len(whois)} WHOIS servers")
