"""Builds stats.svg (terminal style) for the profile README.

Reads public data from the GitHub API and writes an SVG file.
Usage: python scripts/build_stats.py <output_path>
Env:   GH_USER (default: gwilhrm), GITHUB_TOKEN (optional, raises rate limit
       and enables the contribution count through GraphQL).
"""
import datetime
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "gwilhrm")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
FONT = "Consolas, Menlo, 'Courier New', monospace"
BAR_COLORS = ["#4fd1c5", "#1e6fff", "#7aa7ff", "#f6c177", "#b9cdf0"]


def api(url, payload=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def collect():
    user = api("https://api.github.com/users/" + USER)
    repos = api("https://api.github.com/users/%s/repos?per_page=100" % USER)
    own = [r for r in repos if not r["fork"]]
    langs = {}
    for repo in own:
        for name, size in api(repo["languages_url"]).items():
            langs[name] = langs.get(name, 0) + size
    contributions = None
    if TOKEN:
        query = ("query($u:String!){user(login:$u){contributionsCollection"
                 "{contributionCalendar{totalContributions}}}}")
        try:
            out = api("https://api.github.com/graphql",
                      {"query": query, "variables": {"u": USER}})
            contributions = (out["data"]["user"]["contributionsCollection"]
                             ["contributionCalendar"]["totalContributions"])
        except Exception as err:  # the card still renders without this number
            print("contribution count unavailable:", err)
    return {
        "contributions": contributions,
        "repos": user["public_repos"],
        "followers": user["followers"],
        "stars": sum(r["stargazers_count"] for r in own),
        "langs": langs,
    }


def render(data, today):
    rows = []
    if data["contributions"] is not None:
        rows.append(("contributions", data["contributions"], "last 12 months"))
    rows += [
        ("public repos", data["repos"], "projects and studies"),
        ("followers", data["followers"], "on GitHub"),
    ]
    total = sum(data["langs"].values()) or 1
    top = sorted(data["langs"].items(), key=lambda kv: -kv[1])[:5]

    def text(x, y, body, size=19, anchor="start"):
        return ('<text x="%s" y="%s" text-anchor="%s" font-family="%s" font-size="%s">%s</text>'
                % (x, y, anchor, FONT, size, body))

    def span(fill, value, weight=None):
        w = ' font-weight="%s"' % weight if weight else ""
        return '<tspan fill="%s"%s>%s</tspan>' % (fill, w, escape(str(value)))

    height = 356
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" viewBox="0 0 1200 %d" width="1200" height="%d" '
        'role="img" aria-label="GitHub statistics for %s, updated daily by GitHub Actions">'
        % (height, height, USER),
        '<defs><linearGradient id="sbg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#050b1a"/><stop offset="0.6" stop-color="#0a1830"/>'
        '<stop offset="1" stop-color="#06122a"/></linearGradient>'
        '<pattern id="sgrid" width="24" height="24" patternUnits="userSpaceOnUse">'
        '<circle cx="1" cy="1" r="1" fill="#2a4a7a" opacity="0.3"/></pattern></defs>',
        '<rect width="1200" height="%d" rx="14" fill="url(#sbg)" stroke="#1d3a66" stroke-width="1.5"/>' % height,
        '<rect width="1200" height="%d" rx="14" fill="url(#sgrid)"/>' % height,
        '<path d="M14,0 H1186 A14,14 0 0 1 1200,14 V44 H0 V14 A14,14 0 0 1 14,0 Z" fill="#0c1d3a"/>',
        '<circle cx="26" cy="22" r="7" fill="#ff5f57"/><circle cx="48" cy="22" r="7" fill="#febc2e"/>'
        '<circle cx="70" cy="22" r="7" fill="#28c840"/>',
        text(600, 28, span("#6f8bb5", "guilherme@ubuntu: ~/stats"), 15, "middle"),
        text(40, 92, span("#4fd1c5", "$ ") + span("#d6e2f5", "git shortlog --summary --author=" + USER)),
        text(640, 92, span("#4fd1c5", "$ ") + span("#d6e2f5", "ls --sort=size languages/")),
        '<line x1="600" y1="66" x2="600" y2="%d" stroke="#1d3a66" stroke-width="1" stroke-dasharray="4 6"/>' % (height - 58),
    ]
    y = 146
    for label, value, note in rows:
        out.append(text(140, y, span("#ffffff", value, "bold"), 26, "end"))
        out.append(text(158, y, span("#b9cdf0", label) + span("#6f8bb5", "  # " + note)))
        y += 54
    y = 124
    for i, (name, size) in enumerate(top):
        pct = 100.0 * size / total
        color = BAR_COLORS[i % len(BAR_COLORS)]
        width = max(4, round(300 * pct / 100))
        out.append(text(640, y + 14, span("#d6e2f5", name), 18))
        out.append('<rect x="790" y="%d" width="300" height="12" rx="6" fill="#0c1d3a"/>' % y)
        out.append('<rect x="790" y="%d" width="%d" height="12" rx="6" fill="%s">'
                   '<animate attributeName="width" from="0" to="%d" dur="1.2s" fill="freeze"/></rect>'
                   % (y, width, color, width))
        out.append(text(1160, y + 14, span("#b9cdf0", "%.1f%%" % pct), 18, "end"))
        y += 38
    out.append(text(40, height - 26,
                    span("#4fd1c5", "> ") + span("#6f8bb5", "updated daily by GitHub Actions · " + today), 15))
    out.append("</svg>")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "stats.svg"
    if os.environ.get("STATS_MOCK"):
        stats = json.loads(os.environ["STATS_MOCK"])
    else:
        stats = collect()
    svg = render(stats, datetime.date.today().isoformat())
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(svg)
    print("wrote", target, stats)
