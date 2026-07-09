# -*- coding: utf-8 -*-
"""
Itasca Bridge bootstrap script.

Use it inside the Itasca engine (PFC/FLAC/3DEC/…) in either of these ways:
1. Copy the file contents into the engine's IPython console and run them
2. Or save/download this file and execute it in the engine GUI

What it does:
1. Detects the currently installed `itasca-mcp-bridge`, if any
2. Installs or upgrades `itasca-mcp-bridge` according to `AUTO_UPGRADE`
3. Ensures the user site-packages directory is importable
4. Imports `itasca_mcp_bridge`
5. Starts the bridge

Set `AUTO_UPGRADE = False` near the top if you want to pin the locally
installed version and skip the network call on every start.
"""

import importlib
import logging
import os
import sys


PACKAGE_NAME = "itasca-mcp-bridge"
PORT = 9001  # Change this to run multiple bridges on different ports
AUTO_UPGRADE = True  # Set False to keep the locally installed version

# Index URLs tried in order. Mirrors act as a fallback when the primary
# is unreachable (corporate proxies, slow international routes).
DEFAULT_INDEXES = [
    ("https://pypi.org/simple/", ("pypi.org", "files.pythonhosted.org")),
    ("https://pypi.tuna.tsinghua.edu.cn/simple/", ("pypi.tuna.tsinghua.edu.cn",)),
]


def _ensure_user_site_on_path():
    try:
        import site

        user_site = site.getusersitepackages()
    except Exception:
        return

    if isinstance(user_site, str) and user_site and user_site not in sys.path:
        sys.path.append(user_site)


def _build_install_args(index_url, trusted_hosts):
    args = [
        "install",
        "--user",
        "-U",
        "--disable-pip-version-check",
        "--default-timeout", "120",
        "--retries", "5",
        "--index-url", index_url,
    ]
    for host in trusted_hosts:
        args += ["--trusted-host", host]
    args.append(PACKAGE_NAME)
    return args


def _embedded_python():
    """Path to the engine's bundled Python interpreter, or "".

    Inside the GUI `sys.executable` is the engine binary itself
    (e.g. `pfc2d700_gui.exe`), which cannot run `-m pip`. The real
    interpreter lives under `sys.exec_prefix` (`.../exe64/python36`).
    """
    prefixes = (sys.exec_prefix, getattr(sys, "base_prefix", ""))
    candidates = ("python.exe", os.path.join("bin", "python3"), os.path.join("bin", "python"))
    for prefix in prefixes:
        if not prefix:
            continue
        for relative in candidates:
            candidate = os.path.join(os.path.normpath(prefix), relative)
            if os.path.isfile(candidate):
                return candidate
    return ""


def _manual_install_hint():
    python_path = _embedded_python()
    if not python_path:
        python_path = "<engine install dir>/python.exe"
    return (
        "You can also install manually and re-run this script -- in a "
        "terminal, with the engine's own Python (a plain 'python' would "
        "install into the system interpreter instead):\n"
        '    "{}" -m pip install --user -U {}'.format(python_path, PACKAGE_NAME)
    )


class _StreamProxy(object):
    """File-like proxy guaranteeing the attributes pip's progress bar probes.

    Some engine GUI consoles install a stdout/stderr replacement (e.g.
    Itasca's RedirectstdChannel) that has write/flush but no isatty. pip's
    download progress bar calls ``file.isatty()`` unconditionally during
    construction -- the AttributeError aborts the download and therefore
    the whole install. Affects every pip that vendors ``progress`` (stock
    pip 9 on PFC 6/7, reproduced up to pip 21). Delegates everything else
    to the wrapped stream.
    """

    def __init__(self, stream):
        self._stream = stream

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def isatty(self):
        try:
            return bool(self._stream.isatty())
        except Exception:
            return False

    def flush(self):
        try:
            self._stream.flush()
        except Exception:
            pass


def _progress_flags():
    """Extra install args to silence pip's progress bar where supported.

    Both flags exist since pip 10. On older pip the isatty=False reported
    by _StreamProxy already keeps the vendored progress bar silent.
    """
    try:
        import pip

        major = int(str(pip.__version__).split(".")[0])
    except Exception:
        return []
    if major >= 10:
        return ["--no-warn-script-location", "--progress-bar", "off"]
    return []


def _resolve_pip_main():
    """Locate pip's callable entry point.

    There is no single stable location. `pip.main` exists in pip <= 9
    (what PFC 6.0 ships), was removed in pip 10.0, and was later restored
    as an internal-only shim; `pip._internal.main` covers pip 10 .. 19.2;
    `pip._internal.cli.main.main` covers pip >= 19.3. The embedded engine
    Python may carry any pip version, so probe each location in turn
    rather than guessing from the pip or Python version.
    """
    try:
        from pip._internal.cli.main import main as pip_main  # pip >= 19.3

        return pip_main
    except Exception:
        pass
    try:
        from pip._internal import main as pip_main  # pip 10 .. 19.2

        return pip_main
    except Exception:
        pass
    try:
        from pip import main as pip_main  # pip <= 9 (PFC 6.0)

        return pip_main
    except Exception:
        pass
    return None


def _run_pip(args):
    # Swap in the isatty-safe proxies BEFORE pip is first imported: pip
    # binds ``file = sys.stdout`` on its progress-bar classes at import
    # time, so a later swap would not reach them.
    previous_streams = (sys.stdout, sys.stderr)
    if sys.stdout is not None:
        sys.stdout = _StreamProxy(sys.stdout)
    if sys.stderr is not None:
        sys.stderr = _StreamProxy(sys.stderr)

    # The engine runs pip inside an IPython host; temporarily suppress logging
    # handler tracebacks that don't reflect actual installation failures.
    previous_raise_exceptions = logging.raiseExceptions
    logging.raiseExceptions = False
    try:
        pip_main = _resolve_pip_main()
        if pip_main is None:
            raise RuntimeError(
                "Could not locate pip's Python entry point in this engine "
                "interpreter. " + _manual_install_hint()
            )
        return pip_main(list(args) + _progress_flags())
    finally:
        logging.raiseExceptions = previous_raise_exceptions
        sys.stdout, sys.stderr = previous_streams


def _install_bridge():
    os.environ["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    override = os.environ.get("ITASCA_MCP_PIP_INDEX_URL")
    if override:
        indexes = [(override, ())]
    else:
        indexes = DEFAULT_INDEXES

    last_code = 1
    for attempt, (index_url, trusted_hosts) in enumerate(indexes, start=1):
        if attempt > 1:
            print("Primary index failed, retrying with mirror: {}".format(index_url))
        last_code = _run_pip(_build_install_args(index_url, trusted_hosts))
        if last_code == 0:
            return 0
    return last_code


def _load_installed_bridge():
    _ensure_user_site_on_path()
    importlib.invalidate_caches()

    if "itasca_mcp_bridge" in sys.modules:
        del sys.modules["itasca_mcp_bridge"]

    try:
        import itasca_mcp_bridge
    except Exception:
        return None

    return itasca_mcp_bridge


def _import_bridge():
    _ensure_user_site_on_path()
    importlib.invalidate_caches()

    if "itasca_mcp_bridge" in sys.modules:
        del sys.modules["itasca_mcp_bridge"]

    import itasca_mcp_bridge

    return itasca_mcp_bridge


def _should_install(current_version):
    if current_version is None:
        print("{} is not installed. Installing the latest version ...".format(PACKAGE_NAME))
        return True

    print("Installed itasca-mcp-bridge:", current_version)
    if AUTO_UPGRADE:
        print("AUTO_UPGRADE is on. Checking for a newer version ...")
        return True
    print("AUTO_UPGRADE is off. Keeping the current installation.")
    return False


def main():
    print("=" * 60)
    print("Itasca MCP Bridge Bootstrap")
    print("=" * 60)
    print("Python:", sys.version.split()[0])

    installed_bridge = _load_installed_bridge()
    installed_version = None
    if installed_bridge is not None:
        installed_version = getattr(installed_bridge, "__version__", "unknown")

    if _should_install(installed_version):
        code = _install_bridge()
        if code != 0:
            raise RuntimeError(
                "Bridge installation failed (pip exit code {}). The real pip "
                "error is in the output above this message -- read that, not "
                "this line. Common causes: no network route to PyPI, or a "
                "corporate proxy/firewall blocking the index. ".format(code)
                + _manual_install_hint()
            )

    itasca_mcp_bridge = _import_bridge()

    print("Using itasca-mcp-bridge:", getattr(itasca_mcp_bridge, "__version__", "unknown"))
    print("Starting bridge on port {} ...".format(PORT))

    # This script already handled install/upgrade above; tell start() to skip
    # its own update check. The env var works across bridge versions, unlike
    # the start(auto_upgrade=...) kwarg which older bridges don't accept.
    os.environ["ITASCA_MCP_BRIDGE_AUTO_UPGRADE"] = "0"

    itasca_mcp_bridge.start(port=PORT)


if __name__ == "__main__":
    main()
