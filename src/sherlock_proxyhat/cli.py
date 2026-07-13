"""``sherlock-proxyhat`` — a thin launcher that runs Sherlock through ProxyHat residential proxies.

Sherlock (https://github.com/sherlock-project/sherlock) is an OSINT *app*, not a
library: it hunts a username across hundreds of sites and accepts a single
``--proxy <url>`` for all of them. Firing that many requests from one datacenter
IP gets rate-limited and blocked fast, so this launcher resolves a ProxyHat
residential gateway URL and invokes the real ``sherlock`` executable with
``--proxy <url>`` prepended, passing every other argument (usernames + flags)
straight through.

Because Sherlock reuses the one proxy for the whole run, we build a **rotating**
gateway username by default — the ProxyHat gateway then hands out a fresh
residential IP per connection, spreading the hundreds of site checks across many
IPs. Pass ``--proxyhat-sticky`` to pin one IP instead.

This is deliberately a wrapper around Sherlock's existing ``--proxy`` flag, not a
fork. A native ``--proxyhat`` flag upstream is a planned follow-up (see README).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence

from proxyhat import build_connection_url

from sherlock_proxyhat._resolve import ProxyHatConfigError, resolve_credentials

# Sherlock makes one proxy serve the entire multi-site run, so the sensible
# default is to rotate: a fresh residential IP per connection spreads the load
# and dodges per-IP rate limits. sticky is opt-in via --proxyhat-sticky.
DEFAULT_STICKY: bool | str | None = None


def proxyhat_proxy_url(
    *,
    api_key: str | None = None,
    username: str | None = None,
    password: str | None = None,
    sub_user: str | None = None,
    country: str | None = None,
    region: str | None = None,
    city: str | None = None,
    sticky: bool | str | None = DEFAULT_STICKY,
    filter: str | None = None,
    protocol: str = "http",
) -> str:
    """Return a full ProxyHat gateway proxy URL for Sherlock's ``--proxy``.

    Resolves credentials (``api_key``/``PROXYHAT_API_KEY`` auto-picks an active
    sub-user, or pass ``username``/``password``) then builds a connection URL like
    ``http://<user>-country-us:<pass>@gate.proxyhat.com:8080`` (or ``socks5://…:1080``)
    via the official ``proxyhat`` SDK's targeting grammar.

    Rotating by default (``sticky=None``): the gateway hands out a fresh
    residential IP per connection. Pass ``sticky="30m"`` (or ``True``) to pin one
    IP for the whole run. Geo/quality: ``country`` (ISO code or ``"any"``),
    ``region``, ``city``, ``filter`` (AI IP-quality tier). ``protocol`` is
    ``"http"`` or ``"socks5"``.
    """
    user, pw = resolve_credentials(
        api_key=api_key,
        username=username,
        password=password,
        sub_user=sub_user,
    )
    return build_connection_url(
        username=user,
        password=pw,
        country=country,
        region=region,
        city=city,
        sticky=sticky,
        filter=filter,
        protocol=protocol,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Parser for the ``--proxyhat-*`` options this launcher owns.

    Everything else (usernames and all of Sherlock's own flags) is left for
    ``parse_known_args`` to return untouched, so we never have to track Sherlock's
    argument surface.
    """
    parser = argparse.ArgumentParser(
        prog="sherlock-proxyhat",
        description=(
            "Run Sherlock through ProxyHat residential proxies. All arguments other than "
            "--proxyhat-* are passed straight through to the `sherlock` executable."
        ),
        add_help=False,  # let --help fall through to sherlock; use --proxyhat-help for ours
        # Never abbreviation-match: a bare `--proxy` (Sherlock's own flag) must fall
        # through to passthrough, not be swallowed as a prefix of `--proxyhat-*`.
        allow_abbrev=False,
    )
    g = parser.add_argument_group("proxyhat options (stripped before forwarding to sherlock)")
    g.add_argument("--proxyhat-help", action="help", help="show this launcher's proxyhat options and exit")
    g.add_argument("--proxyhat-api-key", metavar="KEY", help="ProxyHat API key (or env PROXYHAT_API_KEY)")
    g.add_argument("--proxyhat-username", metavar="USER", help="explicit gateway proxy_username (or PROXYHAT_USERNAME)")
    g.add_argument("--proxyhat-password", metavar="PASS", help="explicit gateway proxy_password (or PROXYHAT_PASSWORD)")
    g.add_argument("--proxyhat-sub-user", metavar="ID", help="pick a sub-user by uuid or name (or PROXYHAT_SUBUSER)")
    g.add_argument("--proxyhat-country", metavar="ISO", help='country ISO code, or "any" (default)')
    g.add_argument("--proxyhat-region", metavar="NAME", help="region/state to target")
    g.add_argument("--proxyhat-city", metavar="NAME", help="city to target")
    g.add_argument("--proxyhat-filter", metavar="TIER", help="AI IP-quality tier (e.g. high)")
    g.add_argument("--proxyhat-protocol", choices=("http", "socks5"), default="http", help="gateway protocol")
    # Two flags rather than one optional-value flag: a bare `--proxyhat-sticky VALUE`
    # would greedily swallow the following positional username as its value, so
    # stickiness is a plain switch and the lifetime is a separate option.
    g.add_argument(
        "--proxyhat-sticky",
        action="store_true",
        help="pin one residential IP for the whole run (default: rotating — a fresh IP per connection)",
    )
    g.add_argument(
        "--proxyhat-sticky-ttl",
        metavar="TTL",
        help='sticky session lifetime like "30m"/"2h" (implies --proxyhat-sticky; default 30m)',
    )
    return parser


def _resolve_sticky(*, sticky: bool, ttl: str | None) -> bool | str | None:
    """Fold the two sticky flags into the SDK's ``sticky`` argument.

    A TTL implies sticky and sets the lifetime; a bare ``--proxyhat-sticky`` pins
    with the SDK default (30m); neither means rotating.
    """
    if ttl:
        return ttl
    if sticky:
        return True
    return DEFAULT_STICKY


def _has_user_proxy(passthrough: Sequence[str]) -> bool:
    """True if the user already supplied Sherlock's own --proxy/-p flag."""
    return any(a == "--proxy" or a == "-p" or a.startswith("--proxy=") for a in passthrough)


def build_command(argv: Sequence[str]) -> list[str]:
    """Resolve the ProxyHat proxy and build the full ``sherlock`` command line.

    Returns ``[sherlock_exe, "--proxy", <url>, *passthrough]``. If the caller
    already passed Sherlock's own ``--proxy``/``-p``, that wins and no ProxyHat URL
    is injected (a note goes to stderr). Raises ``ProxyHatConfigError`` if
    credentials can't be resolved and ``FileNotFoundError`` if ``sherlock`` isn't
    installed.
    """
    ns, passthrough = _build_parser().parse_known_args(list(argv))

    sherlock_exe = shutil.which("sherlock")
    if sherlock_exe is None:
        raise FileNotFoundError(
            "sherlock-proxyhat: the `sherlock` executable was not found on PATH. "
            "Install it with `pip install sherlock-proxyhat[sherlock]` or `pip install sherlock-project`."
        )

    if _has_user_proxy(passthrough):
        print(
            "sherlock-proxyhat: a --proxy/-p flag was supplied explicitly; using it and skipping the ProxyHat proxy.",
            file=sys.stderr,
        )
        return [sherlock_exe, *passthrough]

    url = proxyhat_proxy_url(
        api_key=ns.proxyhat_api_key,
        username=ns.proxyhat_username,
        password=ns.proxyhat_password,
        sub_user=ns.proxyhat_sub_user,
        country=ns.proxyhat_country,
        region=ns.proxyhat_region,
        city=ns.proxyhat_city,
        sticky=_resolve_sticky(sticky=ns.proxyhat_sticky, ttl=ns.proxyhat_sticky_ttl),
        filter=ns.proxyhat_filter,
        protocol=ns.proxyhat_protocol,
    )
    return [sherlock_exe, "--proxy", url, *passthrough]


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``sherlock-proxyhat`` console script.

    Builds the command and hands off to the real ``sherlock`` via subprocess,
    returning its exit code.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        command = build_command(argv)
    except (ProxyHatConfigError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    completed = subprocess.run(command)
    return completed.returncode


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
