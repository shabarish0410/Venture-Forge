"""Bounded, explicit research reads. Retrieved content is data, never instructions."""
import hashlib
import ipaddress
import io
import socket
from html.parser import HTMLParser
from urllib.parse import urlsplit
import httpx

MAX_BYTES = 4 * 1024 * 1024


class ReadFailure(ValueError):
    pass


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden, self.parts = 0, []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}: self.hidden += 1
        if tag in {"p", "div", "br", "h1", "h2", "h3", "tr", "li"}: self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}: self.hidden = max(0, self.hidden - 1)

    def handle_data(self, value):
        if not self.hidden: self.parts.append(value)


def extract_document(payload, filename, content_type=""):
    if not payload or len(payload) > MAX_BYTES: raise ReadFailure("Use a nonempty file no larger than 4 MB.")
    pages = []
    if payload.startswith(b"%PDF-") or filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(payload))
            if reader.is_encrypted or len(reader.pages) > 100:
                raise ReadFailure("Use an unencrypted PDF with at most 100 pages.")
            remaining = 100000
            for number, page in enumerate(reader.pages, 1):
                text = (page.extract_text() or "")[:min(20000, remaining)]
                if text.strip(): pages.append({"locator": f"{filename}, page {number}", "text": text})
                remaining -= len(text)
                if remaining <= 0: break
        except ReadFailure: raise
        except Exception: raise ReadFailure("The PDF could not be read. Try a text PDF or paste an excerpt.") from None
    else:
        try: text = payload.decode("utf-8-sig")
        except UnicodeError: raise ReadFailure("Text files must use UTF-8 encoding.") from None
        if "html" in content_type:
            parser = PageText()
            parser.feed(text)
            text = "".join(parser.parts)
        if len(text) > 100000: text = text[:100000]
        for start in range(0, len(text), 20000):
            pages.append({"locator": f"{filename}, characters {start + 1}-{min(start + 20000, len(text))}", "text": text[start:start + 20000]})
    if not pages: raise ReadFailure("No readable text was found. Scanned PDF OCR is outside this MVP.")
    return {"filename": filename, "sha256": hashlib.sha256(payload).hexdigest(), "pages": pages, "notice": "Read the source, select an exact passage and register it before making a claim. Extraction is limited to 100,000 characters; original rights and limitations still apply."}


def public_target(url, allowed_hosts, resolver=socket.getaddrinfo):
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError: raise ReadFailure("Enter a valid HTTPS source URL.") from None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or port not in {None, 443}:
        raise ReadFailure("Use a public HTTPS URL on port 443 without credentials or fragments.")
    host = parsed.hostname.lower()
    if host not in {h.lower() for h in allowed_hosts}:
        raise ReadFailure("This host has not been approved in RESEARCH_ALLOWED_HOSTS.")
    try: addresses = list(dict.fromkeys(item[4][0] for item in resolver(host, 443, type=socket.SOCK_STREAM)))
    except OSError: raise ReadFailure("The source hostname could not be resolved.") from None
    if not addresses or any(not ipaddress.ip_address(addr).is_global for addr in addresses):
        raise ReadFailure("Private, local and reserved network addresses are not permitted.")
    return host, addresses[0]


def fetch_source(url, settings):
    host, address = public_target(url, settings.research_allowed_hosts)
    # Connect to the checked IP, preserving certificate verification and TLS SNI.
    # No second DNS lookup, redirects, cookies or environment proxies are allowed.
    target = httpx.URL(url).copy_with(host=address)
    try:
        with httpx.Client(timeout=12, trust_env=False, follow_redirects=False) as client:
            with client.stream("GET", target, headers={"Host": host, "Accept": "text/html,text/plain,application/pdf", "User-Agent": "VentureForge-Research/1.0"}, extensions={"sni_hostname": host}) as response:
                if response.status_code != 200: raise ReadFailure("Source unavailable or redirected. Open the original source and review its final URL.")
                kind = response.headers.get("content-type", "").split(";", 1)[0]
                if kind not in {"text/html", "text/plain", "application/pdf", "text/csv"}: raise ReadFailure("This source format is not supported.")
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES: raise ReadFailure("This source exceeds the 4 MB reading limit.")
                    chunks.append(chunk)
                return extract_document(b"".join(chunks), url, kind)
    except httpx.HTTPError: raise ReadFailure("The research source could not be reached. Check connectivity and access permissions.") from None


def web_search(query, settings):
    key = settings.research_search_api_key.get_secret_value()
    if not key: raise ReadFailure("Web search needs a server-side Brave Search API key (RESEARCH_SEARCH_API_KEY). Saved-source search and file reading are available locally.")
    try:
        with httpx.Client(timeout=12, trust_env=False, follow_redirects=False) as client:
            response = client.get("https://api.search.brave.com/res/v1/web/search", params={"q": query, "count": 5}, headers={"Accept": "application/json", "X-Subscription-Token": key})
            response.raise_for_status()
            if len(response.content) > 1000000: raise ReadFailure("Search response exceeded the limit.")
            body = response.json()
            results = body.get("web", {}).get("results", [])
            return [{"title": str(r.get("title", ""))[:300], "url": str(r.get("url", ""))[:2000], "status": "discovery_only_read_original_before_citing"} for r in results[:5] if isinstance(r, dict) and str(r.get("url", "")).startswith("https://")]
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise ReadFailure("Web search is unavailable; check the configured key and provider connectivity.") from None
