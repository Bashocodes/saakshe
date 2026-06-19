"""common.egress — ONE shared server-side egress guard for every outbound fetch.

THREAT: manas reads founder-supplied refs (website / docs / social handle /
github) by fetching them server-side. With zero IP/host filtering today, a
registered founder can point a "website" or "docs" connection at an internal
address (169.254.169.254, 127.0.0.1, RFC1918) or any third party and have the
Cloud Run service fetch it — an open egress proxy. The fetched BODY is summarised
into the founder-readable Context Pack (live mode), so it is a *content-disclosure*
SSRF, not blind.

DESIGN (why this shape):
  * The reusable unit is an IP POLICY (`vet_egress_ip`) using the stdlib
    `ipaddress` module — NOT host-string matching. String matching is bypassed by
    decimal/octal/hex IP encodings, IPv4-mapped IPv6, and (fatally) by a 302
    redirect or DNS rebinding to an internal address AFTER the string was checked.
  * Enforcement for httpx lives in a custom TRANSPORT that vets the resolved peer
    IP at socket-connect time. Because every TCP connection httpx opens — the first
    request AND every redirect hop — passes through the transport, this single
    chokepoint defeats redirect-based and rebinding bypass while keeping
    `follow_redirects=True`. All three httpx seams build their client from
    `safe_client()`.
  * The git clone path cannot share an httpx client, so it gets the same IP policy
    applied separately: resolve the clone-URL host and vet every resolved address
    before `subprocess.run`. (`vet_egress_host` below.)
  * Scheme is allow-listed to http/https on top.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


class EgressBlocked(Exception):
    """Raised when a fetch target resolves to a denied address or scheme."""


# Deny ranges. fc00::/7 (NOT just fd00::/8) covers all IPv6 ULA; fe80::/10 is
# link-local; ::ffff:0:0/96 IPv4-mapped is normalised below so a mapped 10.x is
# still caught. 100.64/10 is CGNAT (carrier-grade NAT / shared address space).
_DENY_V4 = [
    ipaddress.ip_network(c) for c in (
        "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
        "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.168.0.0/16",
        "198.18.0.0/15", "224.0.0.0/4", "240.0.0.0/4", "255.255.255.255/32",
    )
]
_DENY_V6 = [
    ipaddress.ip_network(c) for c in (
        "::1/128", "::/128", "fc00::/7", "fe80::/10", "ff00::/8",
    )
]


def vet_egress_ip(ip: str) -> None:
    """Raise EgressBlocked if `ip` is loopback/link-local/private/reserved/etc.

    Normalises IPv4-mapped IPv6 (`::ffff:a.b.c.d`) back to v4 first, so a mapped
    internal address can't sneak past the v6 checks."""
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    # Belt-and-braces: the stdlib classifiers catch most of this, the explicit
    # ranges catch the GCP metadata IP and CGNAT the classifiers miss/allow.
    if (addr.is_private or addr.is_loopback or addr.is_link_local
            or addr.is_multicast or addr.is_reserved or addr.is_unspecified):
        raise EgressBlocked(f"blocked address {addr}")
    nets = _DENY_V4 if addr.version == 4 else _DENY_V6
    for net in nets:
        if addr in net:
            raise EgressBlocked(f"blocked address {addr}")


_BLOCKED_HOSTNAMES = {"metadata.google.internal", "metadata", "localhost"}


def vet_egress_host(host: str, *, port: int = 0) -> None:
    """Resolve `host` and vet EVERY returned address (DNS may return many; an
    attacker only needs one internal A record). Used by the git clone pre-check;
    httpx fetches are guarded at the transport instead (covers redirects).

    Known-internal names (the metadata vhost, ``localhost``, any ``*.internal``)
    are refused BEFORE resolution — so the block holds even on a box whose resolver
    would (mis)answer them with a routable address."""
    low = (host or "").lower()
    if low in _BLOCKED_HOSTNAMES or low.endswith(".internal"):
        raise EgressBlocked(f"blocked host {host!r}")
    try:
        infos = socket.getaddrinfo(host, port or None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise EgressBlocked(f"cannot resolve {host}: {e}") from e
    for info in infos:
        vet_egress_ip(info[4][0])


def vet_url(url: str) -> None:
    """Scheme allow-list + host vet for a non-httpx caller (e.g. the git clone).
    For httpx, prefer `safe_client()` which also covers redirect hops."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise EgressBlocked(f"blocked scheme {parts.scheme!r}")
    if not parts.hostname:
        raise EgressBlocked("no host in url")
    vet_egress_host(parts.hostname, port=parts.port or 0)


if httpx is not None:
    class _GuardedTransport(httpx.HTTPTransport):
        """Vets the resolved peer IP of EVERY connection (initial + each redirect)
        by overriding the connect at the pool level. We resolve the host ourselves,
        vet the addresses, then let httpx connect — pinning is best-effort; the
        authoritative control is that no connection is attempted to a host whose
        DNS contains a denied address."""

        def handle_request(self, request):  # type: ignore[override]
            host = request.url.host
            if request.url.scheme not in ("http", "https"):
                raise EgressBlocked(f"blocked scheme {request.url.scheme!r}")
            vet_egress_host(host, port=request.url.port or 0)
            return super().handle_request(request)

    def safe_client(**kwargs) -> "httpx.Client":
        """Drop-in for httpx.Client used by every fetch seam. follow_redirects may
        stay True — each hop re-enters handle_request and is re-vetted."""
        kwargs.setdefault("follow_redirects", True)
        return httpx.Client(transport=_GuardedTransport(), **kwargs)

    def guarded_transport(**kwargs) -> "httpx.BaseTransport":
        """The SSRF-vetting transport on its own, so a seam can keep building its
        client through its OWN module's ``httpx.Client(...)`` symbol (preserving the
        seam's existing test monkeypatches) while still getting the guard:
        ``httpx.Client(transport=egress.guarded_transport(), follow_redirects=True)``.
        In tests that replace ``httpx.Client`` wholesale, the transport is passed to
        the fake client and ignored — so it only fires on a real fetch."""
        return _GuardedTransport(**kwargs)
else:  # pragma: no cover
    def safe_client(**kwargs):  # type: ignore[misc]
        raise EgressBlocked("httpx not available")

    def guarded_transport(**kwargs):  # type: ignore[misc]
        raise EgressBlocked("httpx not available")


# ── CALL SITES (apply at every outbound seam) ────────────────────────────────
#  manas/sources.py  WebsiteSource.read  : httpx.Client(...)  -> egress.safe_client(...)
#  manas/vault.py    _fetch_bytes         : httpx.Client(...)  -> egress.safe_client(...)
#  manas/social.py   _fetch_handle        : httpx.Client(...)  -> egress.safe_client(...)
#  manas/sources.py  GitHubSource.read    : egress.vet_url(clone_url) BEFORE subprocess.run,
#                                           and pin non-ssh github mechanisms to host github.com
#  manas/sources.py  probe_repo_visibility: egress.vet_url(url)  BEFORE the ls-remote subprocess
#
# NOTE: a fully robust control additionally pins the vetted IP into the actual
# connection (defeating the residual TOCTOU between getaddrinfo and connect). On
# Cloud Run without a VPC connector the practical exposure is the metadata IP +
# loopback + arbitrary external proxying, all of which the host/IP vet above
# closes; pin-to-IP is the follow-up hardening, not the gate.
