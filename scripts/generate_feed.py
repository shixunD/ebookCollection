import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime

REPO = "shixunD/ebookCollection"
FOLDER = "history"
FEED_TITLE = "ebookCollection - History Notes"
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


def fetch_text(url):
    from urllib.parse import quote, urlsplit, urlunsplit
    parts = urlsplit(url)
    encoded_path = quote(parts.path, safe="/:@!$&'()*+,;=")
    safe_url = urlunsplit((parts.scheme, parts.netloc, encoded_path, parts.query, parts.fragment))
    req = urllib.request.Request(safe_url, headers={"User-Agent": "rss-gen/1.0"})
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_filename(name):
    stem = name[:-4]
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", stem)
    if not m:
        return None, stem, "", ""
    date_str = m.group(1)
    rest = m.group(2)
    parts = rest.split(" - ", 1)
    if len(parts) == 2:
        author = parts[0].strip()
        title_part = parts[1].strip()
    else:
        author = ""
        title_part = rest.strip()
    if " \u2014 " in title_part:
        title, subtitle = title_part.split(" \u2014 ", 1)
    else:
        title, subtitle = title_part, ""
    return date_str, author, title.strip(), subtitle.strip()


def date_to_rfc822(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return format_datetime(dt)
    except Exception:
        return format_datetime(datetime.now(tz=timezone.utc))


def escape_xml(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def parse_header_and_body(text):
    """Split the file into a metadata header dict and the body paragraphs."""
    header = {}
    body_lines = []
    in_header = True
    for line in text.splitlines():
        stripped = line.strip()
        if in_header:
            if stripped == "---":
                in_header = False
                continue
            # lines like "KEY: value"
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                header[key.strip()] = val.strip()
            # else skip junk header lines
        else:
            body_lines.append(line)
    return header, body_lines


def lines_to_html(lines):
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
        else:
            buf.append(stripped)
    flush()
    return "\n".join(html_parts)


def build_html(header, body_lines, author, title, subtitle):
    parts = []
    # Clean metadata block
    parts.append("<div style='border-left:3px solid #ccc;padding:0 1em;margin-bottom:1.5em;color:#555;font-size:0.9em'>")
    if author:
        parts.append(f"<p><strong>Author:</strong> {escape_xml(author)}</p>")
    book = header.get("BOOK", "")
    if book:
        parts.append(f"<p><strong>Book:</strong> {escape_xml(book)}</p>")
    concept = header.get("CORE CONCEPT", "")
    if concept:
        parts.append(f"<p><strong>Core concept:</strong> {escape_xml(concept)}</p>")
    ref = header.get("KEY REFERENCE", "")
    if ref:
        parts.append(f"<p><strong>Key reference:</strong> {escape_xml(ref)}</p>")
    parts.append("</div>")
    # Body
    parts.append(lines_to_html(body_lines))
    return "\n".join(parts)


def main():
    api_url = f"https://api.github.com/repos/{REPO}/contents/{FOLDER}"
    files = fetch_json(api_url)
    items = []
    for f in files:
        if not f["name"].endswith(".txt") or f.get("size", 0) == 0:
            continue
        date_str, author, title, subtitle = parse_filename(f["name"])
        content = fetch_text(f["download_url"])
        header, body_lines = parse_header_and_body(content)
        html_content = build_html(header, body_lines, author, title, subtitle)
        # Title: plain ASCII-safe
        full_title = f"{author} - {title}" if author else title
        if subtitle:
            full_title += f": {subtitle}"
        guid = f["html_url"]
        items.append({
            "title": full_title,
            "link": guid,
            "guid": guid,
            "pubDate": date_to_rfc822(date_str or "2000-01-01"),
            "html": html_content,
            "date_str": date_str or "0000-00-00",
        })

    items.sort(key=lambda x: x["date_str"], reverse=True)
    now_rfc = format_datetime(datetime.now(tz=timezone.utc))

    xml_items = []
    for it in items:
        xml_items.append(f"""    <item>
      <title>{escape_xml(it['title'])}</title>
      <link>{escape_xml(it['link'])}</link>
      <guid isPermaLink="true">{escape_xml(it['guid'])}</guid>
      <pubDate>{it['pubDate']}</pubDate>
      <description><![CDATA[{it['html']}]]></description>
      <content:encoded><![CDATA[{it['html']}]]></content:encoded>
    </item>""")

    feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{title}</title>
    <link>{link}</link>
    <description>{desc}</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="https://shixunD.github.io/ebookCollection/feed.xml" rel="self" type="application/rss+xml"/>
{items}
  </channel>
</rss>""".format(
        title=escape_xml(FEED_TITLE),
        link=escape_xml(FEED_LINK),
        desc=escape_xml(FEED_DESC),
        now=now_rfc,
        items="\n".join(xml_items),
    )

    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write(feed)
    print(f"Generated {OUTPUT} with {len(items)} items.")


if __name__ == "__main__":
    main()
