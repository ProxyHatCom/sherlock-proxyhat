# sherlock-proxyhat

Run [Sherlock](https://github.com/sherlock-project/sherlock) — the OSINT username hunter — through [ProxyHat](https://proxyhat.com?utm_source=github&utm_medium=readme&utm_campaign=sherlock) residential proxies. Rotating residential IPs by default (a fresh IP per connection across the hundreds of sites Sherlock checks), plus geo-targeting and anonymity, so you get rate-limited and blocked far less.

[![CI](https://github.com/ProxyHatCom/sherlock-proxyhat/actions/workflows/ci.yml/badge.svg)](https://github.com/ProxyHatCom/sherlock-proxyhat/actions/workflows/ci.yml)
[![Compatible with sherlock latest](https://github.com/ProxyHatCom/sherlock-proxyhat/actions/workflows/compat.yml/badge.svg)](https://github.com/ProxyHatCom/sherlock-proxyhat/actions/workflows/compat.yml)
[![PyPI](https://img.shields.io/pypi/v/sherlock-proxyhat)](https://pypi.org/project/sherlock-proxyhat/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> [!TIP]
> **Recommended proxies — [ProxyHat](https://proxyhat.com?utm_source=github&utm_medium=readme&utm_campaign=sherlock&utm_content=callout) residential IPs.** Every feature in this package is tested end-to-end against ProxyHat and works great. First-class integration; also works with any proxy, or none.


## What this is

Sherlock is an **app**, not a library: you run `sherlock <username>` and it checks that name across 400+ sites, accepting a single `--proxy <url>` for all of them. Hammering that many sites from one datacenter IP gets throttled and blocked fast.

`sherlock-proxyhat` is a **thin launcher**. It resolves a ProxyHat residential gateway URL, then runs the real `sherlock` executable with `--proxy <url>` prepended — every other argument (usernames and Sherlock's own flags) passes straight through. No fork, no patched Sherlock: it just wires ProxyHat into the `--proxy` flag Sherlock already has.

## Install

```bash
pip install sherlock-proxyhat sherlock-project
```

`sherlock-project` (which provides the `sherlock` command) is an optional dependency — this launcher shells out to the `sherlock` executable, so any install works (pip, pipx, system package). To pull it in with the launcher:

```bash
pip install "sherlock-proxyhat[sherlock]"
```

## Quick start

```bash
# An API key auto-selects an active residential sub-user:
export PROXYHAT_API_KEY=ph_xxx

# Same arguments as sherlock — just run it through the launcher:
sherlock-proxyhat johndoe

# Geo-target and add sherlock's own flags; everything after is passed through:
sherlock-proxyhat --proxyhat-country us johndoe janedoe --timeout 30 --csv
```

Get an API key at [proxyhat.com](https://proxyhat.com?utm_source=github&utm_medium=readme&utm_campaign=sherlock).

Anything that isn't a `--proxyhat-*` option is forwarded to `sherlock` verbatim, so every Sherlock flag (`--timeout`, `--site`, `--nsfw`, `--csv`, `-o`, …) works unchanged.

## Credentials

Pass them as `--proxyhat-*` flags or via environment variables — flags win over env:

| Flag | Env var | Notes |
|---|---|---|
| `--proxyhat-api-key` | `PROXYHAT_API_KEY` | Auto-selects an active sub-user with remaining traffic |
| `--proxyhat-sub-user` | `PROXYHAT_SUBUSER` | Pick a specific sub-user by uuid or name (with an API key) |
| `--proxyhat-username` | `PROXYHAT_USERNAME` | Explicit gateway `proxy_username` (skips the API) |
| `--proxyhat-password` | `PROXYHAT_PASSWORD` | Explicit gateway `proxy_password` |

## Targeting

All targeting lives on `--proxyhat-*` flags, which are stripped before the command reaches `sherlock`:

```bash
sherlock-proxyhat \
  --proxyhat-protocol http \      # or socks5
  --proxyhat-country us \         # ISO code or "any" (default)
  --proxyhat-region california \
  --proxyhat-city los_angeles \
  --proxyhat-filter high \        # AI IP-quality tier
  johndoe
```

### Rotating IPs by default

Sherlock reuses one proxy for the whole run, so this launcher builds a **rotating** gateway username by default: the ProxyHat gateway hands out a fresh residential IP on every connection, spreading the hundreds of per-site checks across many IPs — exactly what you want to dodge per-IP rate limits during a scan.

Want to pin a single IP for the whole run instead? Add `--proxyhat-sticky` (optionally with a lifetime via `--proxyhat-sticky-ttl`):

```bash
sherlock-proxyhat --proxyhat-sticky johndoe               # one pinned IP, 30m default
sherlock-proxyhat --proxyhat-sticky-ttl 2h johndoe        # one pinned IP, 2h lifetime
```

### Bring your own proxy

If you pass Sherlock's own `--proxy`/`-p` (or `--tor`) yourself, the launcher steps aside: it forwards your arguments unchanged and does not inject a ProxyHat URL.

### Credentials never hit your logs

Sherlock prints the full `--proxy` URL on startup (`Using the proxy: http://user:pass@gate.proxyhat.com:8080`), which would otherwise leak your ProxyHat `proxy_username`/`proxy_password` into the terminal and any captured logs. Because the launcher builds that URL, it knows the exact secret strings and redacts them: it pipes Sherlock's output and streams it line by line (nothing is buffered — long scans stream normally), masking the credentials to `http://***:***@gate.proxyhat.com:8080` before anything reaches your stdout. Sherlock's result lines pass through unchanged.

## Using the URL builder directly

Need the gateway URL in your own script or a different tool? Import the helper:

```python
from sherlock_proxyhat import proxyhat_proxy_url

url = proxyhat_proxy_url(api_key="ph_xxx", country="us")
# -> "http://<user>-country-us:<pass>@gate.proxyhat.com:8080"
```

Rotating by default (`sticky=None`); pass `sticky="30m"` (or `True`) to pin one IP.

## How it works

The launcher parses out its `--proxyhat-*` options, resolves your gateway credentials via the official [`proxyhat`](https://pypi.org/project/proxyhat/) SDK (an API key auto-picks an active sub-user, or pass `username`/`password`), and builds a connection URL carrying ProxyHat's targeting grammar (`http://<user>-country-us:<pass>@gate.proxyhat.com:8080`, or `socks5://…:1080`). It then finds the `sherlock` executable on your `PATH` and runs `sherlock --proxy <url> <your other args>` as a subprocess, returning Sherlock's exit code. A rotating username makes the gateway hand out a fresh residential IP per connection; `--proxyhat-sticky` pins one.

## Roadmap

This launcher wraps Sherlock's existing `--proxy` flag on purpose — it's the honest, low-friction way to ship today. A **planned follow-up** is an upstream PR to Sherlock adding a native `--proxyhat` flag (resolve credentials and geo-target from within Sherlock itself, no wrapper), so ProxyHat becomes a first-class option in the tool. Until that lands, this package is the supported path.

## License

MIT © [ProxyHat](https://proxyhat.com)
