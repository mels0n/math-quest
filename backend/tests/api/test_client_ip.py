import pytest

from mathquest.api.clientip import client_ip, parse_networks
from mathquest.api.ratelimit import RateLimiter, rate_bucket
from mathquest.shared.errors import RateLimited
from tests.conftest import FakeClock

TRUSTED = parse_networks(["10.0.0.0/24", "fd00::/8"])


def test_untrusted_peer_ignores_forwarded_for() -> None:
    assert client_ip("203.0.113.7", ["1.2.3.4"], TRUSTED) == "203.0.113.7"
    assert client_ip("203.0.113.7", ["1.2.3.4"], ()) == "203.0.113.7"


def test_trusted_peer_uses_rightmost_untrusted() -> None:
    assert client_ip("10.0.0.5", ["198.51.100.9"], TRUSTED) == "198.51.100.9"
    # A client-supplied left entry cannot displace the address the proxy appended.
    assert client_ip("10.0.0.5", ["6.6.6.6, 198.51.100.9"], TRUSTED) == "198.51.100.9"
    assert client_ip("10.0.0.5", ["6.6.6.6", "198.51.100.9, 10.0.0.9"], TRUSTED) == "198.51.100.9"


def test_trusted_peer_without_usable_header_falls_back_to_peer() -> None:
    assert client_ip("10.0.0.5", [], TRUSTED) == "10.0.0.5"
    assert client_ip("10.0.0.5", ["10.0.0.7, 10.0.0.8"], TRUSTED) == "10.0.0.5"
    assert client_ip("10.0.0.5", ["not-an-ip"], TRUSTED) == "10.0.0.5"
    assert client_ip("10.0.0.5", ["1.2.3.4, garbage"], TRUSTED) == "10.0.0.5"


def test_ipv6_and_mapped_addresses() -> None:
    assert client_ip("fd00::1", ["2001:db8::5"], TRUSTED) == "2001:db8::5"
    assert client_ip("::ffff:10.0.0.5", ["198.51.100.9"], TRUSTED) == "198.51.100.9"


def test_missing_or_unparsable_peer() -> None:
    assert client_ip(None, ["1.2.3.4"], TRUSTED) == "0.0.0.0"
    assert client_ip("testclient", ["1.2.3.4"], TRUSTED) == "0.0.0.0"


def test_parse_networks_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_networks(["not a network"])


def test_rate_bucket_groups_ipv6_by_64() -> None:
    assert rate_bucket("2001:db8:1:2:aaaa:bbbb:cccc:dddd") == rate_bucket("2001:db8:1:2::1")
    assert rate_bucket("2001:db8:1:2::1") != rate_bucket("2001:db8:1:3::1")
    assert rate_bucket("198.51.100.9") == "198.51.100.9"
    assert rate_bucket("198.51.100.9") != rate_bucket("198.51.100.10")
    assert rate_bucket("unknown") == "unknown"


def test_limiter_window_and_retry_after() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock)
    for _ in range(3):
        limiter.hit("s", "k", limit=3, window_s=100)
    clock.advance(40)
    with pytest.raises(RateLimited) as err:
        limiter.hit("s", "k", limit=3, window_s=100)
    assert err.value.retry_after_s == 60
    limiter.hit("s", "other", limit=3, window_s=100)
    limiter.hit("t", "k", limit=3, window_s=100)
    clock.advance(60)
    limiter.hit("s", "k", limit=3, window_s=100)


def test_limiter_sweeps_expired_slots_on_a_cadence() -> None:
    clock = FakeClock()
    limiter = RateLimiter(clock)
    for n in range(50):
        limiter.hit("s", f"k{n}", limit=1, window_s=10)
    clock.advance(61)
    limiter.hit("s", "fresh", limit=1, window_s=10)
    assert len(limiter._hits) == 1  # pyright: ignore[reportPrivateUsage]
