"""manas.sources — REAL readers for the connected channels (the setu bridge's hands).

No mocks. A GitHub repo is cloned over the founder's existing git auth and its
README / manifests / structure / in-repo docs are read; a website is fetched with
httpx and its homepage + a few key pages are reduced to text. Every chunk carries
real provenance (a path or a URL) so the facts manas commits cite something that
actually exists.

GitHub access is abstracted behind ``GitHubSource`` so the mechanism is a choice,
not a rewrite:
  * SSH (default)  — git@github.com:owner/repo.git over the founder's existing key
                     (verified working as Bashocodes; reads private repos, zero setup)
  * PAT            — https://x-access-token:<token>@github.com/owner/repo.git (BYOK)
  * public         — https clone by URL, no auth

The readers are defensive: a channel that errors returns an empty bundle with the
error in ``meta`` rather than throwing, so one bad source never sinks the connect.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


# Char caps keep ingestion token cost bounded (the imbiber prompts include this text).
REPO_CAP = 22000
WEB_CAP = 16000
DOCS_CAP = 12000


@dataclass
class SourceBundle:
    """What one channel hands the matching imbiber: real text + real provenance."""

    channel: str                       # "repo" | "web" | "docs" | "social"
    ref: str                           # the connected ref (repo url, site url, handle)
    text: str = ""                     # the reduced source text the imbiber reads
    provenance: list[str] = field(default_factory=list)  # paths / urls actually read
    org_hint: dict = field(default_factory=dict)   # {name, kind, one_liner} best-effort
    ok: bool = True
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"channel": self.channel, "ref": self.ref, "ok": self.ok,
                "provenance": self.provenance, "org_hint": self.org_hint,
                "chars": len(self.text), "meta": self.meta}


# ─── GitHub ───────────────────────────────────────────────────────────────────
_MANIFESTS = ("package.json", "pyproject.toml", "Cargo.toml", "go.mod",
              "pubspec.yaml", "Gemfile", "composer.json", "requirements.txt",
              "wrangler.toml", "wrangler.jsonc")
_README_GLOBS = ("README.md", "README.MD", "Readme.md", "readme.md", "README")


def normalize_repo_ref(ref: str, *, mechanism: str = "ssh", token: Optional[str] = None) -> str:
    """Turn 'owner/repo', a github URL, or an ssh ref into a clone URL for the
    chosen mechanism."""
    ref = (ref or "").strip()
    # An ssh ref carries its own credential (the key) — never rewrite it.
    if ref.startswith(("git@", "ssh://")):
        return ref
    # A full https URL: clone as pasted, but a PAT must ride along — the
    # founder's natural input for a private repo IS the browser URL.
    if ref.startswith(("https://", "http://")):
        if mechanism == "pat" and token:
            return re.sub(r"^https?://", f"https://x-access-token:{token}@", ref, count=1)
        return ref
    m = re.match(r"^(?:github\.com[:/])?([\w.-]+)/([\w.-]+?)(?:\.git)?$", ref)
    owner_repo = f"{m.group(1)}/{m.group(2)}" if m else ref
    if mechanism == "pat" and token:
        return f"https://x-access-token:{token}@github.com/{owner_repo}.git"
    if mechanism == "public":
        return f"https://github.com/{owner_repo}.git"
    return f"git@github.com:{owner_repo}.git"


def probe_repo_visibility(ref: str, *, timeout: int = 10) -> dict:
    """Anonymously classify a repo ref BEFORE it is granted: 'public' (a stranger
    can clone it — any open-source repo, zero setup), 'private' (anonymous access
    refused; GitHub deliberately answers private and nonexistent the same),
    'ssh' (a git@/ssh:// ref — works where the founder's key lives, a local run),
    or 'unknown' (unparseable). Two hard rules: the raw ref is never handed to
    git (the URL is built here, https-only — no ext:: transports), and no
    credential helper is consulted — the verdict is what a stranger sees."""
    ref = (ref or "").strip()
    if ref.startswith(("git@", "ssh://")):
        return {"visibility": "ssh", "ref": ref}
    url = ""
    if " " not in ref:
        if ref.startswith("https://"):
            url = ref                      # probe exactly what the reader would clone
        else:
            m = re.match(r"^(?:github\.com[:/])?([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", ref)
            if m:
                url = f"https://github.com/{m.group(1)}/{m.group(2)}.git"
    if not url:
        return {"visibility": "unknown", "ref": ref}
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        subprocess.run(
            ["git", "-c", "credential.helper=", "ls-remote", url, "HEAD"],
            check=True, capture_output=True, text=True, timeout=timeout, env=env,
        )
        return {"visibility": "public", "ref": ref}
    except subprocess.CalledProcessError:
        return {"visibility": "private", "ref": ref}
    except (subprocess.TimeoutExpired, OSError):
        return {"visibility": "unknown", "ref": ref}


class GitHubSource:
    def __init__(self, mechanism: str = "ssh", token: Optional[str] = None) -> None:
        self.mechanism = mechanism
        self.token = token

    def read(self, ref: str, *, cap: int = REPO_CAP, timeout: int = 90) -> SourceBundle:
        clone_url = normalize_repo_ref(ref, mechanism=self.mechanism, token=self.token)
        tmp = tempfile.mkdtemp(prefix="saakshe_repo_")
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_SSH_COMMAND="ssh -o BatchMode=yes")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--single-branch", clone_url, tmp],
                check=True, capture_output=True, text=True, timeout=timeout, env=env,
            )
            text, prov, org = self._read_tree(Path(tmp))
            return SourceBundle(channel="repo", ref=ref, text=text[:cap],
                                provenance=prov, org_hint=org, ok=True,
                                meta={"clone": clone_url.split("@")[-1]})
        except subprocess.CalledProcessError as e:
            return SourceBundle(channel="repo", ref=ref, ok=False,
                                meta={"error": (e.stderr or str(e))[:300]})
        except (subprocess.TimeoutExpired, OSError) as e:
            return SourceBundle(channel="repo", ref=ref, ok=False, meta={"error": str(e)[:300]})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _read_tree(self, root: Path) -> tuple[str, list[str], dict]:
        parts: list[str] = []
        prov: list[str] = []
        org: dict = {}

        # README — the human description of the project.
        for name in _README_GLOBS:
            p = root / name
            if p.exists():
                body = _safe_read(p, 8000)
                parts.append(f"=== README ({name}) ===\n{body}")
                prov.append(name)
                org.setdefault("one_liner", _first_paragraph(body))
                h1 = _first_h1(body)
                if h1:
                    org.setdefault("name", h1)
                break

        # Manifests — the machine description (name, deps, what it is).
        for name in _MANIFESTS:
            p = root / name
            if p.exists():
                body = _safe_read(p, 4000)
                parts.append(f"=== {name} ===\n{body}")
                prov.append(name)
                if name == "package.json":
                    org.setdefault("name", _json_field(body, "name") or org.get("name", ""))
                    desc = _json_field(body, "description")
                    if desc:
                        org.setdefault("one_liner", desc)

        # Structure — the shape of the codebase (top two levels, code dirs only).
        tree = _tree(root)
        if tree:
            parts.append("=== STRUCTURE (top level) ===\n" + tree)
            prov.append("(directory structure)")

        # A couple of in-repo docs (docs/*.md, root *.md beyond README).
        for md in _pick_docs(root):
            rel = md.relative_to(root).as_posix()
            parts.append(f"=== doc: {rel} ===\n{_safe_read(md, 3000)}")
            prov.append(rel)

        org.setdefault("kind", "software product")
        return "\n\n".join(parts), prov, {k: v for k, v in org.items() if v}


# ─── Website ───────────────────────────────────────────────────────────────────
_LINK_HINTS = ("about", "pricing", "product", "features", "how-it-works", "manifesto",
               "company", "story")


class WebsiteSource:
    def read(self, url: str, *, cap: int = WEB_CAP, max_pages: int = 4,
             timeout: int = 15) -> SourceBundle:
        if httpx is None:
            return SourceBundle(channel="web", ref=url, ok=False, meta={"error": "httpx not available"})
        url = _norm_url(url)
        parts: list[str] = []
        prov: list[str] = []
        org: dict = {}
        try:
            from common import egress
            with httpx.Client(transport=egress.guarded_transport(), follow_redirects=True,
                              timeout=timeout,
                              headers={"user-agent": "saakshe-setu/1.0 (+manas ingestion)"}) as cli:
                home = cli.get(url)
                title, desc, body, links = _parse_html(home.text, base=str(home.url))
                images = _collect_images(home.text, base=str(home.url))
                if title:
                    org["name"] = _site_name(title)
                if desc:
                    org["one_liner"] = desc
                org.setdefault("kind", "company / product (website)")
                parts.append(f"=== {url} (home) ===\nTITLE: {title}\nDESCRIPTION: {desc}\n\n{body}")
                prov.append(url)
                # A few key internal pages.
                picked = _pick_links(links, url)[: max_pages - 1]
                for link in picked:
                    try:
                        r = cli.get(link)
                        _, _, b, _ = _parse_html(r.text, base=str(r.url))
                        if b.strip():
                            parts.append(f"=== {link} ===\n{b}")
                            prov.append(link)
                    except Exception:  # noqa: BLE001
                        continue
            meta = {"images": images} if images else {}  # key absent unless real images found
            return SourceBundle(channel="web", ref=url, text="\n\n".join(parts)[:cap],
                                provenance=prov, org_hint={k: v for k, v in org.items() if v},
                                ok=True, meta=meta)
        except Exception as e:  # noqa: BLE001
            return SourceBundle(channel="web", ref=url, ok=False, meta={"error": str(e)[:300]})


class DocsSource(WebsiteSource):
    """A docs/knowledge-base URL — same fetch+reduce, tagged as the docs channel."""

    def read(self, url: str, *, cap: int = DOCS_CAP, **kw) -> SourceBundle:  # type: ignore[override]
        b = super().read(url, cap=cap, **kw)
        b.channel = "docs"
        return b


# ─── HTML → text (no bs4 dependency) ──────────────────────────────────────────
def _parse_html(html: str, base: str = "") -> tuple[str, str, str, list[str]]:
    """(title, meta-description, visible-text, hrefs) — regex-based, dependency-free."""
    html = html or ""
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = _collapse(title_m.group(1)) if title_m else ""
    desc_m = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.I | re.S
    ) or re.search(
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']', html, re.I | re.S
    )
    desc = _collapse(desc_m.group(1)) if desc_m else ""
    hrefs = re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.I)
    # Strip script/style/noscript, then tags.
    cleaned = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = _unescape(cleaned)
    text = _collapse(cleaned)
    return title, desc, text[:8000], [_resolve(base, h) for h in hrefs]


def _collect_images(html: str, base: str = "") -> list[str]:
    """Discover brand-image URLs a page surfaces — og:image, <img src>, and the
    favicon — resolved to absolute URLs (the auto-extract input for the vault).
    Returns a de-duplicated, order-preserving list (empty when the page has none,
    so the bundle's meta stays free of an empty key)."""
    html = html or ""
    raw: list[str] = []
    for m in re.finditer(
        r'<meta[^>]+(?:property|name)=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I,
    ):
        raw.append(m.group(1))
    raw.extend(re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I))
    for m in re.finditer(
        r'<link[^>]+rel=["\'][^"\']*icon[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
        html, re.I,
    ):
        raw.append(m.group(1))
    out: list[str] = []
    seen: set[str] = set()
    for href in raw:
        href = (href or "").strip()
        if not href or href.startswith("data:"):
            continue
        abs_url = _resolve(base, href)
        if abs_url.startswith(("http://", "https://")) and abs_url not in seen:
            seen.add(abs_url)
            out.append(abs_url)
    return out


def _pick_links(links: list[str], base: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    host = _host(base)
    for link in links:
        if not link or _host(link) != host:
            continue
        low = link.lower()
        if any(h in low for h in _LINK_HINTS) and link not in seen:
            seen.add(link)
            out.append(link)
    return out


# ─── small deterministic helpers ──────────────────────────────────────────────
_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "coverage", ".next", "venv",
              ".venv", "__pycache__", "target", "vendor", ".turbo", "out"}


def _tree(root: Path, depth: int = 2) -> str:
    lines: list[str] = []

    def walk(d: Path, prefix: str, level: int) -> None:
        if level > depth:
            return
        try:
            entries = sorted([e for e in d.iterdir() if e.name not in _SKIP_DIRS and not e.name.startswith(".")],
                             key=lambda e: (e.is_file(), e.name))
        except OSError:
            return
        for e in entries[:40]:
            lines.append(f"{prefix}{e.name}{'/' if e.is_dir() else ''}")
            if e.is_dir():
                walk(e, prefix + "  ", level + 1)

    walk(root, "", 1)
    return "\n".join(lines[:120])


def _pick_docs(root: Path, limit: int = 3) -> list[Path]:
    out: list[Path] = []
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        out.extend(sorted(docs_dir.glob("*.md"))[:2])
    for md in sorted(root.glob("*.md")):
        if md.name.lower().startswith("readme"):
            continue
        out.append(md)
        if len(out) >= limit:
            break
    return out[:limit]


def _safe_read(p: Path, cap: int) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:cap]
    except OSError:
        return ""


def _first_paragraph(md: str) -> str:
    """First real prose paragraph of a README. Famous-repo READMEs often open
    with HTML banners / badge rows — strip tags, comments, and link/image
    syntax so markup never leaks into the org one-liner."""
    for block in re.split(r"\n\s*\n", md or ""):
        if block.lstrip().startswith(">"):                        # blockquotes / GitHub alerts
            continue                                              # ([!WARNING] etc.) aren't prose
        b = re.sub(r"<!--.*?-->", " ", block, flags=re.S)        # html comments
        b = re.sub(r"<[^>]+>", " ", b)                            # html tags
        b = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", b)          # md links/images → text
        b = re.sub(r"[#*`>_\-]", "", b).strip()
        if len(b) > 30:
            return _collapse(b)[:240]
    return ""


def _first_h1(md: str) -> str:
    m = re.search(r"^\s*#\s+(.+)$", md or "", re.M)
    return _collapse(m.group(1)) if m else ""


def _json_field(blob: str, field: str) -> str:
    m = re.search(rf'"{field}"\s*:\s*"([^"]*)"', blob or "")
    return m.group(1) if m else ""


def _site_name(title: str) -> str:
    # "example — decode & generate" → "example"
    return re.split(r"\s*[—\-|·:]\s*", title)[0].strip() if title else ""


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", _unescape(s or "")).strip()


def _unescape(s: str) -> str:
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                 ("&#39;", "'"), ("&nbsp;", " "), ("&rsquo;", "'"), ("&mdash;", "—")):
        s = s.replace(a, b)
    return s


def _norm_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _host(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return (m.group(1).lower() if m else "").removeprefix("www.")


def _resolve(base: str, href: str) -> str:
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/") and base:
        m = re.match(r"(https?://[^/]+)", base)
        return (m.group(1) + href) if m else href
    return href


def merge_org_hints(bundles: list[SourceBundle]) -> dict:
    """Best deterministic org profile from the channels. Repo name + site name +
    the richest one-liner — no LLM, so the company's identity is grounded in what
    its own sources literally say."""
    name = kind = one_liner = ""
    for b in bundles:
        h = b.org_hint or {}
        # Prefer a website's display name, then the repo's.
        if h.get("name") and (not name or b.channel == "web"):
            name = h["name"]
        if h.get("one_liner") and len(h["one_liner"]) > len(one_liner):
            one_liner = h["one_liner"]
        if h.get("kind") and not kind:
            kind = h["kind"]
    return {"name": name, "kind": kind or "the connected company", "one_liner": one_liner}
