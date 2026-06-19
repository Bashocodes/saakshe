"""The SSRF egress guard — the deny policy that wraps every founder-supplied
outbound fetch (website / docs / social / brand-image). Offline: every case uses
a literal IP or a known-internal hostname, so no real DNS is done."""
import ipaddress

import pytest

from common import egress


# ── the IP policy: the metadata IP, loopback, and every private range are denied ──
@pytest.mark.parametrize("ip", [
    "169.254.169.254",       # GCP/AWS metadata server — the headline target
    "127.0.0.1", "127.0.0.53",  # loopback
    "10.1.2.3", "172.16.5.6", "192.168.1.1",  # RFC-1918
    "100.64.0.1",            # CGNAT / shared address space
    "0.0.0.0",               # unspecified
    "::1",                   # IPv6 loopback
    "fe80::1",               # IPv6 link-local
    "fd00::1", "fc00::1",    # IPv6 ULA (fc00::/7, not just fd00::/8)
    "::ffff:169.254.169.254",  # IPv4-mapped IPv6 must be unwrapped + denied
    "::ffff:10.0.0.1",
])
def test_internal_addresses_are_blocked(ip):
    with pytest.raises(egress.EgressBlocked):
        egress.vet_egress_ip(ip)


@pytest.mark.parametrize("ip", ["1.1.1.1", "8.8.8.8", "140.82.121.3", "2606:4700:4700::1111"])
def test_public_addresses_pass(ip):
    egress.vet_egress_ip(ip)          # must not raise
    ipaddress.ip_address(ip)          # sanity: these are valid


# ── url-level: scheme allow-list + literal-internal-host short-circuit ──────────
def test_non_http_schemes_blocked():
    for url in ("file:///etc/passwd", "gopher://x/", "ftp://h/", "ssh://git@h/r"):
        with pytest.raises(egress.EgressBlocked):
            egress.vet_url(url)


def test_literal_internal_host_blocked_without_dns():
    # A literal IP needs no resolution — these must fail purely on the IP policy.
    for url in ("http://169.254.169.254/computeMetadata/v1/",
                "http://127.0.0.1:8080/admin",
                "https://[::1]/",
                "http://10.0.0.5/"):
        with pytest.raises(egress.EgressBlocked):
            egress.vet_url(url)


def test_internal_hostnames_blocked():
    for url in ("http://metadata.google.internal/computeMetadata/v1/token",
                "http://localhost/", "http://anything.internal/"):
        with pytest.raises(egress.EgressBlocked):
            egress.vet_url(url)


def test_guarded_transport_is_constructible():
    # The seams build clients with this transport; it must instantiate (no network).
    t = egress.guarded_transport()
    assert t is not None
