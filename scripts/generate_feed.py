import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime

REPO = "shixunD/ebookCollection"
FOLDER = "history"
FEED_TITLE = "ebookCollection – History Notes"
FEED_DESC = "Auto-generated RSS from shixunD/ebookCollection/history"
FEED_LINK = "https://github.com/shixunD/ebookCollection/tree/main/history"
OUTPUT = "feed.xml"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rss-gen/1.0"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def encode_url(url):
    """Percent-encode any unencoded characters in a URL while preserving
    already-encoded sequences and the URL structure (scheme, host, path, query)."""
    parsed = urllib.parse.urlsplit(url)
    encoded_path = urllib.parse.quote(parsed.path, safe="/:@!$&'()*+,;=-._~%")
    return urllib.parse.urlunsplit((
        parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment
    ))


def fetch_text(url):
    safe_url = encode_url(url)
    req = urllib.request.Request(safe_url, headers={"User-Agent": "rss-gen/1.0"})
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_filename(name):
    """
    Supported format: YYYY-MM-DD[-[ ]]Author, Book — Title [ — Subtitle]
    - Date separator: dash-only OR dash-space (both accepted).
    - Any characters tolerated in the body: colons, semicolons,
      quotes, parentheses, Chinese characters, etc.
    Returns (date_str, author, book_or_body, title)
    """
    stem = name[:-4]  # strip .txt
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-\s*(.+)$", stem)
    if not m:
        return None, stem, "", ""
    date_str = m.group(1)
    rest = m.group(2).strip()

    parts = rest.split(" — ", 1)
    if len(parts) == 2:
        author_book = parts[0].strip()
        ab_parts = author_book.split(", ", 1)
        author = ab_parts[0].strip() if len(ab_parts) == 2 else ""
        book = ab_parts[1].strip() if len(ab_parts) == 2 else author_book
        title = parts[1].strip()
        subtitle = ""
        if " — " in title:
            t, s = title.split(" — ", 1)
            title, subtitle = t.strip(), s.strip()
    else:
        ab_parts = rest.split(", ", 1)
        author = ab_parts[0].strip() if len(ab_parts) == 2 else ""
        book = ab_parts[1].strip() if len(ab_parts) == 2 else rest
        title, subtitle = "", ""

    return date_str, author, book, title


def date_to_rfc822(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return format_datetime(dt)
    except Exception:
        return format_datetime(datetime.now(tz=timezone.utc))


def escape_xml(s):
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def text_to_html(text):
    lines = text.splitlines()
    html_parts = []
    buf = []

    def flush():
        if buf:
            para = " ".join(buf).strip()
            if para:
                html_parts.append(f"<p>{escape_xml(para)}</p>")
            buf.clear()

    for line in lines:
        stripped = line.strip()
        if stripped == "":
            flush()
        elif stripped == "---":
            flush()
            html_parts.append("<hr/>")
        else:
            buf.append(stripped)
    flush()
    return "\n".join(html_parts)


def main():
    api_url = f"https://api.github.com/repos/{REPO}/contents/{FOLDER}"
    files = fetch_json(api_url)
    items = []
    for f in files:
        if not f["name"].endswith(".txt") or f.get("size", 0) == 0:
            continue
        date_str, author, book, title = parse_filename(f["name"])
        content = fetch_text(f["download_url"])
        html_content = text_to_html(content)

        # Build the body part of the title (without date)
        if author and book:
            body_title = f"{author}, {book}"
        elif book:
            body_title = book
        else:
            body_title = f["name"][:-4]  # fallback: full stem
        if title:
            body_title += f" — {title}"

        # Prepend date so the full filename (minus .txt) is preserved as title
        if date_str:
            full_title = f"{date_str}-{body_title}"
        else:
            full_title = body_title

        guid = f["html_url"]
        items.append({
            "title": full_title,
            "link": guid,
            "guid": guid,
            "pubDate": date_to_rfc822(date_str or "2000-01-01"),
            "description": html_content,
            "date_str": date_str or "0000-00-00",
        })

    items.sort(key=lambda x: x["date_str"], reverse=True)
    now_rfc = format_datetime(datetime.now(tz=timezone.utc))

    xml_items = []
    for it in items:
        xml_items.append(f"""    <item>
      <title>{escape_xml(it['title'])}</title>
      <link>{escape_xml(it['link'])}</link>
      <guid isPermaLink=\"true\">{escape_xml(it['guid'])}</guid>
      <pubDate>{it['pubDate']}</pubDate>
      <description><![CDATA[{it['description']}]]></description>
    </item>""")

    feed = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rss version=\"2.0\" xmlns:atom=\"http://www.w3.org/2005/Atom\">
  <channel>
    <title>{escape_xml(FEED_TITLE)}</title>
    <link>{escape_xml(FEED_LINK)}</link>
    <description>{escape_xml(FEED_DESC)}</description>
    <language>en</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <atom:link href=\"https://shixunD.github.io/ebookCollection/feed.xml\" rel=\"self\" type=\"application/rss+xml\"/>
{chr(10).join(xml_items)}
  </channel>
</rss>"""

    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write(feed)
    print(f"Generated {OUTPUT} with {len(items)} items.")


if __name__ == "__main__":
    main()
