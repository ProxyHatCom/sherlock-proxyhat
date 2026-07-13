"""Tests for the launcher wiring.

Sherlock is a separate executable, so instead of installing it we fake
``shutil.which`` (to pretend ``sherlock`` is on PATH) and ``subprocess.run`` (to
capture the exact command line without running anything). Credentials are passed
explicitly so no network or SDK call is made. These assert the built ``--proxy``
URL reflects geo/rotation, that ``--proxyhat-*`` flags are stripped, and that all
other args reach ``sherlock`` untouched.
"""

from __future__ import annotations

import pytest

from sherlock_proxyhat import build_command, cli, main


@pytest.fixture
def fake_sherlock(monkeypatch):
    """Pretend `sherlock` is installed at a fixed path and capture subprocess.run."""
    captured = {}

    def fake_run(command, *args, **kwargs):
        captured["command"] = command

        class Completed:
            returncode = 0

        return Completed()

    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/sherlock" if name == "sherlock" else None)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    return captured


CREDS = ["--proxyhat-username", "ph-1", "--proxyhat-password", "pw"]


@pytest.fixture
def fake_which(monkeypatch):
    """Pretend `sherlock` is installed at a fixed path (build_command needs it on PATH)."""
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/sherlock" if name == "sherlock" else None)


@pytest.mark.usefixtures("fake_which")
class TestBuildCommand:
    def test_injects_proxy_and_passes_through_args(self):
        cmd = build_command([*CREDS, "johndoe", "janedoe", "--timeout", "30"])
        assert cmd[0].endswith("sherlock")
        assert cmd[1] == "--proxy"
        url = cmd[2]
        assert url.startswith("http://ph-1-country-any:pw@gate.proxyhat.com:8080")
        # Usernames and sherlock's own flags pass through in order, proxyhat flags stripped.
        assert cmd[3:] == ["johndoe", "janedoe", "--timeout", "30"]
        assert not any(a.startswith("--proxyhat-") for a in cmd)

    def test_rotating_by_default(self):
        cmd = build_command([*CREDS, "johndoe"])
        assert "-sid-" not in cmd[2] and "-ttl-" not in cmd[2]

    def test_geo_and_sticky_ttl_reflected_in_url(self):
        cmd = build_command([*CREDS, "--proxyhat-country", "de", "--proxyhat-sticky-ttl", "2h", "johndoe"])
        url = cmd[2]
        assert "ph-1-country-de" in url
        assert "-ttl-2h" in url
        assert cmd[3:] == ["johndoe"]

    def test_sticky_bare_flag_pins_ip_without_eating_username(self):
        # The sticky switch must not swallow the following positional username.
        cmd = build_command([*CREDS, "--proxyhat-sticky", "johndoe"])
        assert "-sid-" in cmd[2] and "-ttl-30m" in cmd[2]
        assert cmd[3:] == ["johndoe"]

    def test_socks5_protocol(self):
        cmd = build_command([*CREDS, "--proxyhat-protocol", "socks5", "johndoe"])
        assert cmd[2].startswith("socks5://ph-1-country-any:pw@gate.proxyhat.com:1080")

    def test_user_supplied_proxy_wins(self, capsys):
        cmd = build_command([*CREDS, "johndoe", "--proxy", "socks5://127.0.0.1:9050"])
        # No ProxyHat proxy injected; the user's own args are forwarded verbatim.
        assert cmd[1:] == ["johndoe", "--proxy", "socks5://127.0.0.1:9050"]
        assert "skipping the ProxyHat proxy" in capsys.readouterr().err

    def test_missing_sherlock_raises(self, monkeypatch):
        monkeypatch.setattr(cli.shutil, "which", lambda name: None)
        with pytest.raises(FileNotFoundError):
            build_command([*CREDS, "johndoe"])


class TestMain:
    def test_main_runs_sherlock_and_returns_code(self, fake_sherlock):
        rc = main([*CREDS, "--proxyhat-country", "us", "johndoe"])
        assert rc == 0
        command = fake_sherlock["command"]
        assert command[0] == "/usr/bin/sherlock"
        assert command[1] == "--proxy"
        assert command[2].startswith("http://ph-1-country-us:pw@")
        assert command[3] == "johndoe"

    def test_main_missing_sherlock_returns_2(self, monkeypatch):
        monkeypatch.setattr(cli.shutil, "which", lambda name: None)
        assert main([*CREDS, "johndoe"]) == 2

    def test_main_bad_credentials_returns_2(self, fake_sherlock, monkeypatch):
        for var in ("PROXYHAT_API_KEY", "PROXYHAT_USERNAME", "PROXYHAT_PASSWORD", "PROXYHAT_SUBUSER"):
            monkeypatch.delenv(var, raising=False)
        assert main(["johndoe"]) == 2
