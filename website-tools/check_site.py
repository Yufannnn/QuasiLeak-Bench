"""Catch missing local files/anchors before uploading the standalone Pages artifact."""
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links, self.ids = [], set()
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.add(values["id"])
        for key in ("src", "href"):
            if values.get(key):
                self.links.append(values[key])


def check(root):
    root = root.resolve()
    pages = {path.resolve(): Page(path.read_text(encoding="utf-8")) for path in root.glob("*.html")}
    errors = []
    for path, page in pages.items():
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            target = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not target.is_relative_to(root):
                errors.append(f"{path.name}: link escapes website: {link}")
            elif not target.exists():
                errors.append(f"{path.name}: missing file: {link}")
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                # Leaderboard views use script-driven hash state, not document anchors.
                if not (target.name == "index.html" and url.fragment in {"test", "full", "nonrevealing", "policyshift"}):
                    errors.append(f"{path.name}: missing anchor: {link}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Checked {len(pages)} public pages: local files and anchors resolve.")


if __name__ == "__main__":
    check(Path(sys.argv[1]))
