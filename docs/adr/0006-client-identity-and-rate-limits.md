# 0006. Derive client identity conservatively and run a single replica

- Status: accepted
- Date: 2026-10-13

## Context
Rate limits and lockouts (ADR-0007) need to know which client a request came from.
In production the app sits behind a reverse proxy, which makes the socket peer the
proxy for every request. `X-Forwarded-For` carries the real client but is supplied
by whoever sent the request, so believing it blindly lets anyone pick their own
identity and dodge every limit.

## Decision
- The client address is the socket peer, unless the peer is in the configured list of
  trusted proxies (`TRUSTED_PROXIES`). Only then is `X-Forwarded-For` read, and the
  right-most entry that is not itself a trusted proxy is used. A malformed entry
  reached first, or no untrusted entry, falls back to the peer. A peer that is
  missing or not an IP becomes the fixed address `0.0.0.0`.
- IPv4-mapped IPv6 addresses are treated as IPv4. Rate limits and lockouts bucket
  IPv6 addresses by /64, since one household typically holds a whole /64.
- The server container starts uvicorn with `--no-proxy-headers`, so the server never
  rewrites the peer from forwarding headers behind the app's back.
- The rate limiter (`api/ratelimit.py`) is an in-process sliding window per scope and
  bucket, with a periodic sweep of idle entries. Because its counters live in one
  process, the app must run as a single replica; this is stated in the deployment
  notes.

## Alternatives rejected
- **Trust `X-Forwarded-For` always.** Any client could rotate the header and avoid
  every limit and lockout.
- **Uvicorn's proxy-header handling.** It would work, but it spreads the trust
  decision across server flags and app code. Keeping it in one tested function makes
  the rule visible and testable.
- **A shared store such as Redis for counters.** It would allow several replicas but
  adds a service to run and secure before a second replica is needed. If the app
  needs to scale out, replacing the limiter is a contained change behind the same
  interface.

## Consequences
Behind a proxy that is not listed in `TRUSTED_PROXIES`, every request is attributed
to the proxy and limits collapse into one shared bucket, so the setting is part of
deployment. Scaling to more than one replica multiplies the effective limits and
requires a shared counter store first.
