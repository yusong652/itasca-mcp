"""Unit tests for the PFC bridge bootstrap script (``addon.py``).

``addon.py`` runs inside PFC's embedded Python (3.6 on PFC 6/7), while this
suite runs on the MCP package's interpreter (3.10+). These tests therefore
guard the *control flow* of the bootstrap -- argument construction, the
index-fallback loop, pip entry-point resolution, and the install gate --
and deliberately do NOT exercise real pip behaviour or the in-PFC ``start()``
path. Confirming the bootstrap against an actual PFC interpreter stays a
manual step.
"""

import logging
import sys
import types

import pytest

import addon

# --- _build_install_args -------------------------------------------------


def test_build_install_args_core_structure():
    args = addon._build_install_args("https://example.test/simple/", ())

    assert args[0] == "install"
    assert "--user" in args
    assert "-U" in args
    # The package to install is always the final positional argument.
    assert args[-1] == addon.PACKAGE_NAME


def test_build_install_args_index_url_paired_with_value():
    url = "https://example.test/simple/"
    args = addon._build_install_args(url, ())

    assert args[args.index("--index-url") + 1] == url


def test_build_install_args_one_trusted_host_flag_per_host():
    hosts = ("a.example", "b.example", "c.example")
    args = addon._build_install_args("https://example.test/simple/", hosts)

    assert args.count("--trusted-host") == len(hosts)
    for host in hosts:
        # Every host value is introduced by its own --trusted-host flag.
        assert args[args.index(host) - 1] == "--trusted-host"


def test_build_install_args_no_trusted_host_when_empty():
    args = addon._build_install_args("https://example.test/simple/", ())

    assert "--trusted-host" not in args


def test_build_install_args_carry_no_progress_flags():
    # The quiet-output flags moved to _run_pip (_progress_flags), gated on
    # the pip version that will actually parse them -- not on the Python
    # version, and not baked into the static argument list.
    args = addon._build_install_args("https://example.test/simple/", ())

    assert "--no-warn-script-location" not in args
    assert "--progress-bar" not in args


# --- _progress_flags -------------------------------------------------------


def test_progress_flags_present_on_modern_pip(monkeypatch):
    modern_pip = types.ModuleType("pip")
    modern_pip.__version__ = "21.3.1"
    monkeypatch.setitem(sys.modules, "pip", modern_pip)

    assert addon._progress_flags() == ["--no-warn-script-location", "--progress-bar", "off"]


def test_progress_flags_empty_when_pip_unimportable(monkeypatch):
    monkeypatch.setitem(sys.modules, "pip", None)

    assert addon._progress_flags() == []


def test_progress_flags_empty_on_old_pip(monkeypatch):
    old_pip = types.ModuleType("pip")
    old_pip.__version__ = "9.0.1"
    monkeypatch.setitem(sys.modules, "pip", old_pip)

    assert addon._progress_flags() == []


# --- _resolve_pip_main ---------------------------------------------------


def test_resolve_pip_main_prefers_modern_entry_point(monkeypatch):
    # _resolve_pip_main returns the entry point opaquely, so a marker value
    # under the `.main` attribute is enough to assert which probe won.
    cli_mod = types.ModuleType("pip._internal.cli.main")
    cli_mod.main = "modern-entry-point"
    internal_mod = types.ModuleType("pip._internal")
    internal_mod.main = "legacy-internal-entry-point"
    monkeypatch.setitem(sys.modules, "pip._internal.cli.main", cli_mod)
    monkeypatch.setitem(sys.modules, "pip._internal", internal_mod)

    # Even with the older entry point also importable, the modern one wins.
    assert addon._resolve_pip_main() == "modern-entry-point"


def test_resolve_pip_main_returns_none_when_pip_absent(monkeypatch):
    # Force every probed import to fail: a None entry in sys.modules makes
    # `import pip` raise, and clearing the submodule cache stops an already
    # imported `pip._internal.*` from satisfying the import behind pip's back.
    monkeypatch.setitem(sys.modules, "pip", None)
    for name in ("pip._internal", "pip._internal.cli", "pip._internal.cli.main"):
        monkeypatch.delitem(sys.modules, name, raising=False)

    assert addon._resolve_pip_main() is None


# --- _run_pip ------------------------------------------------------------


def test_run_pip_passes_args_and_returns_code(monkeypatch):
    received = []

    def fake_pip_main(args):
        received.append(args)
        return 0

    monkeypatch.setattr(addon, "_resolve_pip_main", lambda: fake_pip_main)
    monkeypatch.setattr(addon, "_progress_flags", lambda: [])

    assert addon._run_pip(["install", "pkg"]) == 0
    assert received == [["install", "pkg"]]


def test_run_pip_appends_progress_flags(monkeypatch):
    received = []

    def fake_pip_main(args):
        received.append(args)
        return 0

    monkeypatch.setattr(addon, "_resolve_pip_main", lambda: fake_pip_main)
    monkeypatch.setattr(addon, "_progress_flags", lambda: ["--progress-bar", "off"])

    assert addon._run_pip(["install", "pkg"]) == 0
    assert received == [["install", "pkg", "--progress-bar", "off"]]


class _ChannelWithoutIsatty:
    """Mimics Itasca's RedirectstdChannel: write/flush only, no isatty."""

    def __init__(self):
        self.written = []

    def write(self, text):
        self.written.append(text)

    def flush(self):
        pass


def test_stream_proxy_reports_not_a_tty_when_isatty_missing():
    # The field crash: pip's progress bar calls file.isatty() on a GUI
    # console channel that doesn't have it.
    assert addon._StreamProxy(_ChannelWithoutIsatty()).isatty() is False


def test_stream_proxy_delegates_existing_isatty():
    class Tty:
        def isatty(self):
            return True

    assert addon._StreamProxy(Tty()).isatty() is True


def test_stream_proxy_delegates_write():
    channel = _ChannelWithoutIsatty()
    addon._StreamProxy(channel).write("hello")
    assert channel.written == ["hello"]


def test_run_pip_proxies_streams_while_pip_runs_and_restores(monkeypatch):
    channel = _ChannelWithoutIsatty()
    monkeypatch.setattr(sys, "stdout", channel)
    seen = {}

    def fake_resolve():
        # pip is first imported inside _resolve_pip_main and binds
        # sys.stdout to its progress-bar classes at import time, so the
        # proxy must already be installed here.
        seen["stdout_type"] = type(sys.stdout)
        seen["isatty"] = sys.stdout.isatty()
        return lambda args: 0

    monkeypatch.setattr(addon, "_resolve_pip_main", fake_resolve)
    monkeypatch.setattr(addon, "_progress_flags", lambda: [])

    assert addon._run_pip(["install", "pkg"]) == 0
    assert seen["stdout_type"] is addon._StreamProxy
    assert seen["isatty"] is False
    assert sys.stdout is channel  # restored


def test_run_pip_restores_streams_when_pip_raises(monkeypatch):
    channel = _ChannelWithoutIsatty()
    monkeypatch.setattr(sys, "stderr", channel)

    def boom(_args):
        raise RuntimeError("pip blew up")

    monkeypatch.setattr(addon, "_resolve_pip_main", lambda: boom)
    monkeypatch.setattr(addon, "_progress_flags", lambda: [])

    with pytest.raises(RuntimeError, match="blew up"):
        addon._run_pip(["install", "pkg"])

    assert sys.stderr is channel


# --- _manual_install_hint --------------------------------------------------


def test_manual_hint_names_the_engine_interpreter(monkeypatch):
    monkeypatch.setattr(
        addon,
        "_embedded_python",
        lambda: r"C:\Program Files\Itasca\PFC700\exe64\python36\python.exe",
    )

    hint = addon._manual_install_hint()
    assert (
        '"C:\\Program Files\\Itasca\\PFC700\\exe64\\python36\\python.exe" -m pip install --user -U itasca-mcp-bridge'
    ) in hint


def test_manual_hint_degrades_when_interpreter_unknown(monkeypatch):
    monkeypatch.setattr(addon, "_embedded_python", lambda: "")

    hint = addon._manual_install_hint()
    assert "<engine install dir>" in hint


def test_run_pip_raises_helpful_error_when_no_pip(monkeypatch):
    monkeypatch.setattr(addon, "_resolve_pip_main", lambda: None)

    with pytest.raises(RuntimeError, match="Could not locate pip"):
        addon._run_pip(["install", "pkg"])


def test_run_pip_restores_logging_raise_exceptions(monkeypatch):
    monkeypatch.setattr(addon, "_resolve_pip_main", lambda: lambda _args: 0)
    monkeypatch.setattr(logging, "raiseExceptions", True)

    addon._run_pip(["install", "pkg"])

    assert logging.raiseExceptions is True


def test_run_pip_restores_logging_even_on_failure(monkeypatch):
    def boom(_args):
        raise RuntimeError("pip blew up")

    monkeypatch.setattr(addon, "_resolve_pip_main", lambda: boom)
    monkeypatch.setattr(logging, "raiseExceptions", True)

    with pytest.raises(RuntimeError, match="blew up"):
        addon._run_pip(["install", "pkg"])

    assert logging.raiseExceptions is True


# --- _install_bridge -----------------------------------------------------


@pytest.fixture
def clean_pip_env(monkeypatch):
    """Neutralize the env vars `_install_bridge` reads and writes."""
    monkeypatch.delenv("ITASCA_MCP_PIP_INDEX_URL", raising=False)
    monkeypatch.delenv("PIP_DISABLE_PIP_VERSION_CHECK", raising=False)


def _stub_run_pip(monkeypatch, codes):
    """Stub `_run_pip` to yield `codes` in order; return the call log."""
    calls = []
    code_iter = iter(codes)

    def fake_run_pip(args):
        calls.append(args)
        return next(code_iter)

    monkeypatch.setattr(addon, "_run_pip", fake_run_pip)
    return calls


def test_install_bridge_returns_zero_on_first_index(monkeypatch, clean_pip_env):
    calls = _stub_run_pip(monkeypatch, [0])

    assert addon._install_bridge() == 0
    # Success on the primary index must not fall through to the mirror.
    assert len(calls) == 1


def test_install_bridge_falls_back_to_mirror(monkeypatch, clean_pip_env):
    calls = _stub_run_pip(monkeypatch, [2, 0])

    assert addon._install_bridge() == 0
    assert len(calls) == 2
    # The retry targets a different index than the failed first attempt.
    first_url = calls[0][calls[0].index("--index-url") + 1]
    second_url = calls[1][calls[1].index("--index-url") + 1]
    assert first_url != second_url


def test_install_bridge_returns_last_code_when_all_fail(monkeypatch, clean_pip_env):
    calls = _stub_run_pip(monkeypatch, [2, 3])

    assert addon._install_bridge() == 3
    assert len(calls) == len(addon.DEFAULT_INDEXES)


def test_install_bridge_honors_index_override(monkeypatch, clean_pip_env):
    monkeypatch.setenv("ITASCA_MCP_PIP_INDEX_URL", "https://override.test/simple/")
    calls = _stub_run_pip(monkeypatch, [0])

    assert addon._install_bridge() == 0
    # An explicit override collapses to a single index, no mirror fallback.
    assert len(calls) == 1
    assert "https://override.test/simple/" in calls[0]


# --- _should_install -----------------------------------------------------


def test_should_install_true_when_not_installed(monkeypatch):
    # Missing install -> always install, regardless of the AUTO_UPGRADE switch.
    monkeypatch.setattr(addon, "AUTO_UPGRADE", False)

    assert addon._should_install(None) is True


def test_should_install_true_when_auto_upgrade_on(monkeypatch):
    monkeypatch.setattr(addon, "AUTO_UPGRADE", True)

    assert addon._should_install("0.1.0") is True


def test_should_install_false_when_auto_upgrade_off(monkeypatch):
    # Pinning behaviour: an existing install with AUTO_UPGRADE off stays put.
    monkeypatch.setattr(addon, "AUTO_UPGRADE", False)

    assert addon._should_install("0.1.0") is False


# --- DEFAULT_INDEXES config ----------------------------------------------


def test_default_indexes_are_well_formed():
    assert addon.DEFAULT_INDEXES  # non-empty
    for index_url, trusted_hosts in addon.DEFAULT_INDEXES:
        assert index_url.startswith("https://")
        assert isinstance(trusted_hosts, tuple)
