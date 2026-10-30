# Narcisse

What the Internet knows about you, and how to shrink it. ([Français](README.md))

You describe who you are (names, usernames, emails, phone numbers, domains…). Narcisse looks for
the public traces of that identity, links them in a graph to show how one leads to another, rates
what each one exposes, and helps you clean up: delete an account, get a page delisted, send a GDPR
request. Then it follows your progress from one scan to the next.

> **Early version.** Narcisse looks for your accounts from a username (over 600 sites), reads your
> public profiles (GitHub, GitLab, Bluesky, Mastodon, Hacker News, Stack Exchange, Keybase), what
> Gravatar and PGP key servers publish about you, what your domains say (registry, DNS,
> certificates, your site's legal notice), what web archives keep of them, the breaches your email
> appears in and company registries, and prepares the searches to run on search engines. It links
> everything in a graph, tells you for each trace how surely it is you and how much it exposes you
> (and why), what to do about it (with GDPR requests ready to send) and follows your requests until
> the trace is gone. What each version brings: the [changelog](CHANGELOG.md) (in French).

Narcisse speaks French and English: it follows your browser's language, or the one chosen in
**Settings**. The screenshots below are of the French interface.

![The graph of a fictitious profile in demo mode: a selected trace and the path linking it to the
identity, the rest dimmed, the minimap and the trace's details](docs/capture-graphe.png)

## Who it is for, what it is for

Narcisse is made for **looking yourself up**, or someone who **explicitly asked you to** (a
relative you help, the client of an exposure audit, with their written consent).

It is not made for investigating others. Excluded, among others: searching for someone without
their knowledge, watching them, harassing them, gathering information to find them, impersonating
or discrediting them. These uses are often illegal, and always against the spirit of the project.

## The legal frame

- Public information is still **personal data**. In Europe, the GDPR applies as soon as data about
  an identifiable person is collected and organised, even when found online. Using it on yourself
  is a personal matter; as soon as other people are concerned, you need a legal basis (their
  consent, in practice).
- Outside the European Union, other laws apply: check those of your country.
- The terms of use of the sites asked apply too: Narcisse keeps to the public access each service
  provides.

## How Narcisse behaves

- **Everything stays on your machine.** Narcisse runs locally and only listens on `127.0.0.1`. No
  account, no remote server, no telemetry. The only requests that leave go to the sources asked
  (and to the AI assistant you chose, if you choose one, for the traces you ask it about only).
- **Passive.** It reads public APIs and pages, open archives and registries. It never pokes a
  service to guess whether you have an account there, never signs in anywhere and never fills in a
  form.
- **Polite with sites.** To know whether an account exists, it asks for one page per site; when it
  goes from link to link, it follows `robots.txt`. It limits its pace per site and always announces
  itself with an honest User-Agent, never as a browser.
- **Never a workaround.** No signing in on your behalf, no captcha solved (protected sites are not
  asked, an anti-bot page means "I don't know"), no paywall crossed, no fake account, never someone
  else's API key.
- **Nothing is sent for you.** Narcisse prepares the removal requests; you always send them
  yourself.
- **Free.** No paid API; a free token (GitHub, say) can lift limits, but nothing requires one.

## Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/), which also installs
Python if it is missing. Then, in a terminal:

```bash
uv tool install https://github.com/j3ffx/narcisse/releases/download/v0.4.0/narcisse-0.4.0-py3-none-any.whl
```

(For a newer version, take the link of the `.whl` file on the
[releases](https://github.com/j3ffx/narcisse/releases) page.) Then:

```bash
narcisse serve --demo
```

- **Update**: the same command with the new version's link and `--force`, then "Restart" in the
  menu of Narcisse's icon.
- **Uninstall**: `uv tool uninstall narcisse`. Your data stays in its folder (`narcisse paths`
  tells you where): delete it to erase everything.
- **From the sources** (to contribute): you also need [Node.js](https://nodejs.org/) 22 or later.
  `git clone https://github.com/j3ffx/narcisse.git`, then in the folder `npm ci`, `npm run build`
  and `uv run narcisse serve --demo`. The repository's rules are in [CLAUDE.md](CLAUDE.md).

The command line speaks your system's language; `NARCISSE_LANG=en` makes it speak English.

## First steps

The browser opens on <http://narcisse.localhost>: an address browsers send to your machine on
their own, with nothing to set up. In demo mode, create a fictitious profile ("Jeanne Exemple"),
add a name, a username, an email and a domain, then start a scan with the demo module: results
come in as they are found for about thirty seconds, with a rate limit, a network error caught
again on its own and a failure to retry. You can pause, cancel, close the browser or stop
Narcisse: everything picks up where it was.

The profile opens on its **graph**: each trace shows up during the scan, linked to the one that led
to it (a username → an account → the site given on that account), bigger the more it exposes you.
Click a trace to see its scores and their reasons, its proofs and its neighbours, search for one
(`/` key), filter by kind, source, status, confidence, risk or date, ask how two traces are linked
(the shortest path), fold the lone traces, group by kind, source or site, and save the view to
come back to it. The **List** view shows the same traces, with the same filters and the same
selection, in a form everyone can read. In demo mode, the "Fictitious graph" button creates a
profile of 500 to 20,000 made-up traces, to see the graph at scale.

- `narcisse serve`: without `--demo`, the demo module is not offered. Demo mode's data is kept
  apart: fictitious profiles never mix with real ones.
- `narcisse paths`: where your data is kept (your system's data folder, never the project's) and
  the log.

### As an app (Windows)

```powershell
narcisse shortcut --demo
```

(Without `--demo`, it opens straight on your real data.)

Narcisse shows up in the Start menu (type "Narcisse", or pin it). A click opens it in its own
window, starting it first if it isn't running. It then sits by the clock: the icon tells what is
going on (a blue dot during a scan, yellow when paused, red if a search fails), and its menu opens
Narcisse, pauses the scans, mutes notifications, switches between demo mode and your real data
(the "Demo mode" box: the Start menu and starting with Windows then reopen the last one chosen),
makes it start with Windows (unticked until you tick it), restarts or quits it. A notification
tells you when a scan ends or a search fails.

To install it as a browser app (icon in the taskbar), open <http://narcisse.localhost> in Chrome
or Edge and click the install icon in the address bar.

From the sources, to update: `git pull`, then `npm run build`, then "Restart" in the icon's menu.

### An even shorter address (optional)

To open Narcisse on <http://narcisse/>, add a line to your system's `hosts` file:
`127.0.0.1 narcisse`. On Windows, in a PowerShell run as administrator:

```powershell
Add-Content -Path "$env:SystemRoot\System32\drivers\etc\hosts" -Value "127.0.0.1 narcisse"
```

On macOS or Linux: `echo "127.0.0.1 narcisse" | sudo tee -a /etc/hosts`. Then restart Narcisse: it
sees the line and answers on that address too. Without it, it refuses the name, which a malicious
network could otherwise hijack. In the browser, type `narcisse/` (with the slash) the first time;
afterwards it offers it on its own.

## The sources

| Source                                  | From                                            | What it finds                                                                                                                                                                                             |
| --------------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Accounts by username (WhatsMyName list) | a username                                      | accounts with that name on over 600 sites (social networks, games, code, forums, adult sites flagged as such)                                                                                             |
| GitHub                                  | a username, an email                            | the public profile and the emails visible in commits; for an email, the accounts using it                                                                                                                 |
| Gravatar                                | an email                                        | the public profile and the accounts it lists (only the email's hash is sent)                                                                                                                              |
| Public PGP keys (keys.openpgp.org)      | an email                                        | a published key, and the names and addresses on it                                                                                                                                                        |
| GitLab                                  | a username, an account                          | the profile on gitlab.com, framagit.org, salsa.debian.org, GNOME and freedesktop.org, and the emails of recent commits                                                                                    |
| Bluesky                                 | a username, a domain, an account                | the profile, its description and links; a domain used as a handle is checked by Bluesky                                                                                                                   |
| Mastodon and the Fediverse              | a username, a user@instance, an account         | the account on some fifteen large instances and those you add; the links Mastodon verified                                                                                                                |
| Hacker News                             | a username, an account                          | the account, its age, and the links and addresses in its about                                                                                                                                            |
| Stack Exchange                          | a username, a name                              | Stack Overflow users with exactly that name (namesakes are possible) and their accounts on the network                                                                                                    |
| Keybase                                 | a username, a domain, an account                | the account and its identity proofs, which surely link other accounts and domains                                                                                                                         |
| Domain registration (RDAP, WHOIS)       | a domain                                        | the registrar and dates, and the holder's name, email, phone and address when the registry publishes them (or the fact it hides them)                                                                     |
| Domain DNS                              | a domain                                        | who receives its emails, who hosts it, the services it was verified with, the addresses its records name (through your machine's resolver)                                                                |
| Certificates (crt.sh, Cert Spotter)     | a domain                                        | its subdomains (`nas.`, `vpn.`, `cloud.`…) published in certificate logs                                                                                                                                  |
| Domain's website                        | a domain                                        | what its legal notice, contact and "about" pages say: name, address, phone, email, SIREN, links to profiles (following `robots.txt`)                                                                      |
| Web archives (Wayback Machine)          | a domain, an account                            | the site's archived pages (a CV, a contact or "about" page, documents, even deleted since) and since when a profile is archived                                                                           |
| Web search (your SearXNG instance)      | a name, a username, an email, a phone, a domain | the pages quoting them exactly, found by your SearXNG instance (optional, see below)                                                                                                                      |
| Data breaches (XposedOrNot)             | an email                                        | the known breaches it appears in: when, which data (passwords, addresses, birth dates…), whether passwords were readable; the address is sent to XposedOrNot                                              |
| Company registries (France)             | a name, an organisation, a SIREN                | the companies you run or ran, or in your name: the registry publishes the directors' month and year of birth and the head office, often the home; for a company, its directors, office and BODACC notices |
| Phone number                            | a phone                                         | what it says about itself, asking nobody: mobile or landline, country, region, original carrier                                                                                                           |

Each search says what it could check: for instance "640 checked · 12 found · 109 blocked by an
anti-bot". The details of each source (sites contacted, pace, licence) are on Narcisse's "Sources"
page. In the settings, a free personal GitHub token lifts GitHub's limit from 60 to 5,000 requests
an hour, and a free GitLab token adds the bio, location and site of gitlab.com profiles; nothing
requires them. You can also add your Mastodon instances there: only the listed instances are
contacted.

### Has a password leaked?

The "Password" page checks whether it appears in the breaches Pwned Passwords lists, without it
leaving the page: it computes its hash, sends only its first 5 characters, and compares the answer
itself. Nothing is kept.

### Search engines

Narcisse never asks Google, Bing or another engine itself. A profile's "Search" tab prepares the
searches worth running for each of your elements (a name in documents and company registries, an
email in lists, a number written several ways…) and opens them in your browser; a page that
talks about you, you paste it back and it joins your traces.

If you want scans to search the web too, run your own [SearXNG](https://docs.searxng.org/)
instance (a metasearch engine running at home) with Docker:

```bash
narcisse searxng
```

The command writes its configuration in your configuration folder (with a secret key of its own),
starts it on `127.0.0.1:8888` and sets its address in Narcisse. It is the one asking the engines,
as your browser would.

### Confidence, risk and leads

Each trace has two scores out of 100, with their reasons in its details ("Why these scores?"):

- **confidence** ("is it you?") starts from what the source says, rises when several independent
  sources find it or it links several of your elements, drops a lot when it was only found through
  traces you rejected. "It’s me" sets it to 100, "not me" to 0, and the neighbouring traces follow;
- **risk** ("how much does it expose you?") depends on the kind of trace (a postal address exposes
  more than a username) and on what it reveals: readable passwords in a breach, birth date in a
  registry, data broker, adult site, Strava, a subdomain like `nas.` or `vpn.`, contact details
  published by a domain's registry, a copy in an archive… For a professional profile (or personal
  and professional), what is normal to show (your company, your domain, the registry) counts half
  as much. It is weighted by confidence, and rated low, medium, high or critical.

A scan starts from your profile's elements. **Leads**, in the Elements tab, are traces sure enough
for a scan to start from them too (an email read in a profile, a domain named in a bio…): "Add as an
element" or "Dismiss". If you choose so for a profile, scans follow the surest ones themselves,
one or two hops away, at most 25 per scan, never a trace you rejected.

In demo mode, only the demo module is offered: fictitious identities never ask real sites.

### What to do about each trace

A trace's details say what you can do, the most useful first: delete an account (the site's
deletion page and how hard it is, from JustDeleteMe), ask a site to erase a page, get it delisted
from search engines (Google, Bing and Qwant forms), get removed from a data broker or a company
directory, remove copies from the Wayback Machine, hide your contact details in the domain
directory, make your INSEE record partly private, make a breach harmless…

To write, Narcisse prepares the request (erasure or objection under the GDPR, account deletion,
delisting), in French or in English, signed with your profile's elements (name, email, address)
and "[to fill in]" for the rest. You read it, change it, then copy it or open it in your mail
app: **Narcisse never sends anything**. With no answer within a month, the page points to a
complaint to the CNIL (France's data protection authority).

"I sent it" (or "Add to To do") follows the action in the profile's **To do** tab: its status (to
do, sent, waiting, done, refused), the reminder ready a month after sending (the tab flags it, and
Narcisse's icon reminds you once a day), and "Check now", which runs again only the searches that
had found the trace. Any scan that no longer finds it marks it gone and closes the request. At the
top of the tab, your exposure: your traces by risk level, and how it changes scan after scan.

### What changed, your exports, your backup

A trace no scan finds any more (all the searches that had found it ran again without error,
without seeing it) is marked **gone**: greyed in the graph and the list, out of your exposure, and
back if a scan finds it again. The **Scans** tab compares two finished scans: new, gone and
modified traces (the page changed), and those that can't be said gone because their searches did
not all run again.

A profile can **run again on its own** every week or month (Elements tab): as long as Narcisse runs
("Start with Windows" in its icon's menu so it always does), it starts a scan with the sources
ticked by default, and a computer that was off catches up at startup. At the end of each scan, its
page and the notification say what changed ("3 new traces, 1 gone"). For cron or the Task
Scheduler, `narcisse scan` starts the scheduled scans that are due (or `--profile N` a profile's),
waits for them to end and says so. Above the graph and the list, a **slider** goes back in time:
the traces as each scan left them.

A profile's **Export** button saves an HTML report to read or print (no script or outside
resource), its traces as CSV for a spreadsheet, or everything as JSON. In **Settings**, "Download a
backup" puts all your profiles, requests and settings in a `.narcisse` file, encrypted if you give
a passphrase (it then also keeps your tokens and your AI assistant's key); "Restore" puts it back,
after keeping your current data in a safety backup. On the command line, `narcisse backup
[--encrypt]` and `narcisse restore FILE` do the same (the latter with Narcisse stopped).

### An AI assistant, if you want one

Narcisse works without AI, and uses none until you choose one in **Settings**:

- **Claude Code**, with your subscription: install it and sign in once, Narcisse only starts it.
  It runs with no tools, none of your settings or MCP servers, in an empty folder: it can only read
  the text it is given and answer.
- **A model on your machine** (Ollama, LM Studio, llama.cpp): nothing leaves your computer.
  Narcisse reads your memory and graphics card, suggests a model that fits (with the answer time to
  expect) and, with Ollama, downloads it on your click (size shown, progress in "Activity"). It
  doesn't install Ollama itself.
- **Another OpenAI-compatible service**: its address, its model, its key if it asks for one.

From a trace's details:

- **"Is it me?"**: it compares the trace and its proofs with the names and usernames you
  declared, and says whether it is probably you, probably not, or impossible to tell. A profile's
  **Sort with the AI** button asks for the traces not sorted yet (50 at a time, the number is shown
  first).
- **Explain this trace**: what it is, and what a stranger could make of it. You can rewrite or hide
  the explanation.
- **Look for leads**: it picks out emails, usernames, domains… in the proofs that could lead to
  other traces. Only those written as such in the proofs are kept; they wait in Elements → Leads
  for you to add them, and no scan follows them on its own.

And in "Prepare the request", **Adapt with the AI** rewrites the letter with what you want to add and
the tone chosen. Your name, email, address and phone are replaced by placeholders before sending,
and put back on return; a proposal that loses the articles of law is dropped. The text only
replaces yours if you click "Take this text".

The assistant answers in the language Narcisse speaks to you. Each answer is marked "AI opinion"
and changes nothing on its own: a verdict is applied to the trace's status only if you click
"Apply: it’s me" (or "not me"). "See what is sent" shows the exact text before sending (the trace, its proofs, your
declared names and usernames, nothing else from your profile). An assistant outside your machine
(Claude Code, a service, or a server on your local network) receives nothing until you accepted it
once in Settings.

## Add a source

A source is a file in `src/narcisse/modules/`, with a class describing what it does (title and
description in French and English, kinds of elements accepted and produced, sites contacted, rate
limit, licence) and a method yielding its results one by one. The engine takes care of the rest:
queue, pause, resume, errors, rate limits, display. The demo module,
[`demo.py`](src/narcisse/modules/demo.py), serves as an example.

## Contribute

The repository's rules (commands, commits, privacy, invariants): [CLAUDE.md](CLAUDE.md).

## Credits

- Site list: [WhatsMyName](https://github.com/WebBreacher/WhatsMyName), Micah Hoffman and
  contributors, licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Adapted
  copy (sites asked with a third party's key removed), provenance in
  `src/narcisse/modules/data/wmn-source.json`.
- Account deletion pages: [JustDeleteMe](https://github.com/jdm-contrib/jdm), Robb Lewis, the JDM
  Contrib Team and contributors, MIT licence. Trimmed copy (English and French), provenance and
  notice in `src/narcisse/remediation/data/jdm-source.json`.
- Data breaches: [XposedOrNot](https://xposedornot.com/), for personal use.
- Passwords: [Pwned Passwords](https://haveibeenpwned.com/Passwords), from Have I Been Pwned (Troy
  Hunt), licence [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Companies: [API Recherche d'entreprises](https://recherche-entreprises.api.gouv.fr/) and
  [BODACC](https://www.bodacc.fr/) (DILA), French public data, Licence Ouverte.
- Phones: [libphonenumber](https://github.com/google/libphonenumber) (Google), Apache 2.0 licence.
- RDAP and WHOIS servers, registrars: public data from the
  [IANA](https://www.iana.org/domains/root/db), dated copy in
  `src/narcisse/modules/data/registries-source.json`.

## Licence

[GPL-3.0](LICENSE).
