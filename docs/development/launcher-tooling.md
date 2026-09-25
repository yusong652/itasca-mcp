# Advanced: Starting the Bridge Automatically

> **This is an advanced path, not a recommended one.**
>
> The supported way to start the bridge is [Step 4 of the bootstrap
> guide](../agentic/itasca-mcp-bootstrap.md#step-4---start-the-engine-gui): open the engine's
> IPython console and type two lines. That path writes nothing into the product's installation,
> needs no cleanup, and cannot surprise anyone.
>
> Read this page only if you are building **launcher tooling** — something that starts an engine
> and then expects a bridge to already be listening — and the two approaches below have already
> ruled out the simple version.

## What this is not

Not a feature of `itasca-mcp` or `itasca-mcp-bridge`. Neither package has an `autostart()`, and the
bridge does not know the hook described here exists. What follows is a recipe: one file that you
write, install into the product, and remove yourself. Everything it can do wrong, it can do wrong
to somebody's running project, which is why it belongs here and not behind a supported flag.

## Two approaches that do not work

Both are the obvious first guess, and both were measured rather than reasoned about.

### `exe64/addon.py`

The filename suggests an extension point. Nothing reads it. Measured with a marker-file probe at the
top of that file, with the GUI fully initialised and a project loaded: the marker never appears, and
`addon.py` occurs **0 times** in the GUI executables (`pfc2d*_gui.exe`, `pfc3d*_gui.exe`,
`flac2d*_gui.exe`, `flac3d*_gui.exe`, `3dec*_gui.exe`). The name is misleading; there is no hook
there.

### A thread that waits for readiness, then calls `start()`

This kills the process. Filed as [#166](https://github.com/yusong652/itasca-mcp/issues/166),
guarded in bridge 0.6.0 — the guard is described under [constraint
2](#2-a-hop-back-to-the-gui-thread), because it changes which of the three traps still bite.

## What works: `sitecustomize.py`

CPython's `site` module imports a module named `sitecustomize` at every interpreter startup. Put one
in the product's embedded Python and it really does run — unlike `addon.py`, this one is loaded.

```
<itasca_path>/exe64/python36/Lib/site-packages/sitecustomize.py   # PFC/FLAC 6.0, 7.0
<itasca_path>/exe64/python310/Lib/site-packages/sitecustomize.py  # 9.0
```

Two consequences worth stating before the code:

- **It runs in every process that uses that interpreter.** The GUI, the `*_console.exe` builds, and
  the plain `python.exe` that the bridge's own self-upgrade runs `-m pip` with. It has to be correct
  in all three, or harmless in the two it does not care about.
- **It runs before the product exists.** At `sitecustomize` time there is no engine, no Qt
  application and no event loop. That is the root of all three constraints below.

## The three constraints

### 1. Deferred readiness

Calling `start()` at `sitecustomize` time raises `AttributeError: module 'itasca' has no attribute
'command'`. The reason is in the bridge's own source: `runtime.start()` ends with

```python
try:
    import itasca as it
except ImportError as e:
    raise RuntimeError("itasca module not available; ...") from e

it.command("python-reset-state false")
```

Importing `itasca` succeeds early — the module is on the path before the bindings are wired up — but
the attributes arrive later. So `import itasca` is not the readiness test; `hasattr(itasca,
"command")` is.

The second precondition is Qt: `start()` attaches a `QTimer` to the application object, and
`QCoreApplication.instance()` is `None` until the product has constructed its application.

Poll for both, on a daemon thread, with a deadline.

### 2. A hop back to the GUI thread

A `QTimer` ticks on the thread that owns it. `start()` reached from the polling thread installs a
timer in a thread with no event loop: it never ticks, so `/health` answers `200` while every
submitted task times out — the failure mode that looks like success. That was issue [#165][];

[#166][] is the same mistake without the guard, which takes the process down instead.

The hop is `QObject.moveToThread(app.thread())` followed by
`QMetaObject.invokeMethod(obj, "go", Qt.QueuedConnection)`. `QueuedConnection` is what puts the call
on the GUI thread's event loop; a direct call from the polling thread is the bug.

**Since 0.6.0 this one is enforced, and that matters for what follows.** `runtime.start()` now opens
with `_preflight_qt_pump_thread()`, which refuses an off-thread `auto`/`gui` start before it binds a
port or configures anything:

```
RuntimeError: start() must run on the Qt application's thread: the task pump is a
QTimer, and a QTimer only ticks on the thread that owns it. Called from thread
'...', which does not own the application. ...
```

So on 0.6.0 and later, forgetting the hop is a loud startup error rather than a dead process. The hop
is still required — you cannot skip it and catch the error — but you no longer have to be right on
the first try to avoid losing somebody's unsaved model. [Constraint 3](#3-a-module-level-reference-to-the-qobject)
has no such guard.

### 3. A module-level reference to the `QObject`

If the object you call `invokeMethod` on is a local, it is garbage-collected when the polling
function returns, and the queued call is then **silently dropped** while `invokeMethod` still returns
`True`. Keep it at module level. This is the same hazard as the note at the top of `runtime.py`
("Keep global references to avoid Qt timer/callback garbage collection"), and it has no guard,
because the bridge is never called and so has nothing to refuse.

## Gate on the interpreter's basename

`sys.executable` is the only thing distinguishing the three kinds of process above, and the test has
to be on its **basename**:

```python
name = os.path.basename(sys.executable).lower()
if not any(h in name for h in ("itasca", "pfc", "flac", "3dec", "mpoint", "massflow")):
    return
```

The trap: a substring test against the **full path** also matches
`<itasca_path>/exe64/python36/python.exe`, because that interpreter sits inside a product directory.
That is the interpreter the bridge's self-upgrade launches for `-m pip`, so a full-path test arms the
watcher in a throwaway process that is about to exit — spending its whole two-minute deadline
polling for an engine that is never going to appear. Basename only.

## The hook

Self-contained; nothing here imports anything that is not in the product or the bridge package. It
uses two private names, `runtime._import_qtcore` and `runtime._is_qt_gui_app`, deliberately: the
second is a metaobject walk that is easy to reimplement wrongly (PySide2 does not downcast the
product's own application object, so `type(app)` and `isinstance(app, QGuiApplication)` both
misreport a real GUI as a console), and both are present in every released version. If a future
release moves them, the check to fall back on is that `start()` with `mode="gui"` refuses loudly
rather than starting something broken.

```python
# -*- coding: utf-8 -*-
"""Start itasca-mcp-bridge whenever an ITASCA product starts.

Advanced path -- see docs/development/launcher-tooling.md for the reasoning,
the two approaches that do not work, and what is measured vs. assumed.
"""
import logging
import os
import socket
import sys
import threading
import time

logger = logging.getLogger("itasca-mcp-bridge")

HOST = os.environ.get("ITASCA_MCP_BRIDGE_AUTOSTART_HOST", "localhost")
PORT = int(os.environ.get("ITASCA_MCP_BRIDGE_AUTOSTART_PORT", "9001"))
TIMEOUT_S = float(os.environ.get("ITASCA_MCP_BRIDGE_AUTOSTART_TIMEOUT", "120"))
POLL_S = 0.5

# Basename only. A full-path test also matches
# "<itasca_path>/exe64/python36/python.exe", which the bridge's self-upgrade
# runs `-m pip` with -- polling there wastes the whole deadline in a process
# that is about to exit.
ENGINE_HINTS = ("itasca", "pfc", "flac", "3dec", "mpoint", "massflow")

# Module level on purpose: a local QObject is collected when the function
# that made it returns, and the queued call is then dropped silently while
# invokeMethod still reports True.
_boot = None


def _log(message):
    """Append one line to the autostart log.

    A file rather than the logger alone: sitecustomize runs before anything
    configures logging, so a hook that only logs leaves no trace at all on
    the machine it failed on.
    """
    import datetime
    import tempfile

    path = os.environ.get(
        "ITASCA_MCP_BRIDGE_AUTOSTART_LOG",
        os.path.join(tempfile.gettempdir(), "itasca_mcp_bridge_autostart.log"),
    )
    try:
        with open(path, "a") as handle:
            handle.write("{}  {}\n".format(datetime.datetime.now().isoformat(), message))
    except Exception:
        pass


def _is_engine_interpreter():
    name = os.path.basename(sys.executable or "").lower()
    return bool(name) and any(hint in name for hint in ENGINE_HINTS)


def _port_in_use():
    """Whether something is already listening. Cheap, and never raises."""
    sock = socket.socket()
    sock.settimeout(0.3)
    try:
        return sock.connect_ex((HOST, PORT)) == 0
    except Exception:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _gui_application():
    """The GUI QApplication, or None while it does not exist yet."""
    from itasca_mcp_bridge import runtime

    QtCore = runtime._import_qtcore()
    if QtCore is None:
        return None
    try:
        app = QtCore.QCoreApplication.instance()
    except Exception:
        return None
    if app is None:
        return None
    # Not "app is not None": the console builds construct a bare
    # QCoreApplication and never run an event loop, and a QTimer hung on one
    # never ticks -- HTTP answers, no task is ever pumped.
    return app if runtime._is_qt_gui_app(app) else None


def _ready():
    """The GUI application, once the engine bindings are complete too."""
    try:
        import itasca
    except Exception:
        return None
    if not hasattr(itasca, "command"):
        return None
    return _gui_application()


def _start_on_gui_thread():
    """Runs on the GUI thread, with its event loop alive. Never raises."""
    try:
        from itasca_mcp_bridge import start

        _log("starting the bridge on {}:{}".format(HOST, PORT))
        # mode="gui", not "auto": auto falls back to the blocking pump when
        # the Qt test fails, and a blocking pump on the GUI thread freezes
        # the product. "gui" refuses instead, and returns the refusal here.
        start(host=HOST, port=PORT, mode="gui")
        _log("start() returned")
    except Exception as exc:
        _log("start() failed: {!r}".format(exc))


def _watch():
    """Poll for readiness on a daemon thread, then hop to the GUI thread."""
    global _boot

    from itasca_mcp_bridge import runtime

    deadline = time.time() + TIMEOUT_S
    while time.time() < deadline:
        try:
            if _port_in_use():
                _log("{}:{} is already in use; not starting a second bridge".format(HOST, PORT))
                return
            app = _ready()
            if app is None:
                time.sleep(POLL_S)
                continue

            QtCore = runtime._import_qtcore()
            if QtCore is None:
                _log("engine is ready but no Qt binding is importable; giving up")
                return

            class _Boot(QtCore.QObject):
                @QtCore.Slot()
                def go(self):
                    _start_on_gui_thread()

            _boot = _Boot()
            _boot.moveToThread(app.thread())
            queued = QtCore.QMetaObject.invokeMethod(_boot, "go", QtCore.Qt.QueuedConnection)
            _log("engine and Qt are ready; invokeMethod returned {!r}".format(queued))
            return
        except Exception as exc:
            _log("watcher error: {!r}".format(exc))
            time.sleep(POLL_S)
    _log("gave up waiting for the engine and Qt after {:.0f}s".format(TIMEOUT_S))


def _boot_bridge():
    """Arm the watcher. Never raises, never blocks."""
    try:
        if not _is_engine_interpreter():
            return
        _log("sitecustomize ran; interpreter={}".format(sys.executable))

        try:
            import itasca_mcp_bridge  # noqa: F401
        except Exception as exc:
            _log("the bridge package is not importable here: {!r}".format(exc))
            return

        if _port_in_use():
            _log("{}:{} is already in use; not starting a second bridge".format(HOST, PORT))
            return

        thread = threading.Thread(target=_watch, name="mcp-bridge-autostart")
        thread.daemon = True
        thread.start()
    except Exception as exc:
        try:
            _log("autostart could not arm: {!r}".format(exc))
        except Exception:
            pass


_boot_bridge()
```

Four things in there are load-bearing and easy to drop:

- `mode="gui"` rather than `"auto"`. `auto` falls back to the blocking pump when the Qt test fails,
  and the blocking pump never returns — on the GUI thread that freezes the product window with no
  way back but killing it. `"gui"` refuses instead, and the refusal is a log line.
- The port probe **before** arming and again in the poll loop. `itasca-mcp` talks to one bridge, so
  one bridge per machine is the intended limit; a second hook that finds the port busy stands down
  instead of fighting for it.
- The whole thing never raises into the product. A launcher that breaks the engine's startup is
  worse than no launcher.
- `thread.daemon = True`, so a watcher that never finds its precondition cannot hold the process
  open.

## Install, verify, remove

Copy the file to each product's embedded `Lib/site-packages/`. If a `sitecustomize.py` is already
there, it belongs to something else — back it up rather than overwriting it. There is no installer
for this, by design.

Verify from the bridge's side, not from the log:

1. Start the engine GUI. Nothing needs typing.
2. `itasca_list_tasks` from your MCP client answers.
3. `itasca_execute_code` returning `sys.executable` ends in `_gui.exe` — that confirms the bridge is
   inside the GUI process and not a console build.
4. `GET /health` reports `runtime_mode: "gui"`. A `"console"` there means the wrong pump was chosen,
   which is the failure described under [constraint 2](#2-a-hop-back-to-the-gui-thread).

If nothing happens, read `%TEMP%\itasca_mcp_bridge_autostart.log`. Every branch above writes a line,
including the ones that give up; that file is the only reason a silent hook is diagnosable.

To remove it, delete the file. To disable it without deleting it, set
`ITASCA_MCP_BRIDGE_AUTOSTART_TIMEOUT=0` — the watcher arms and gives up on its first pass.

## What is measured, and what is not

Measured, on PFC 2D 7.00.161 with embedded Python 3.6.1 and PySide2 5.11.0, Windows 11: this hook,
installed for PFC700, FLAC3D700 and 3DEC700, starts the bridge with nothing typed. `/health` reports
`runtime_mode: "gui"` and `itasca_execute_code` returns `sys.executable` = `pfc2d700_gui.exe`. The
`addon.py` measurement and the `_qt_event_loop_running` behaviour are as cited in [#165][] and
[#166][]; the `RuntimeError` text above is quoted from bridge 0.6.0's `runtime.py`.

Not measured: 9.0 products. The paths and the Qt binding differ (`python310`, PySide6), and
`runtime._is_qt_gui_app` has its own notes about the two. The hook's readiness test is written
against what `runtime.start()` itself checks rather than against a particular Qt version, but
"written against" is not "run on" — try it on a 9.0 install before you rely on it.

[#165]: https://github.com/yusong652/itasca-mcp/issues/165
[#166]: https://github.com/yusong652/itasca-mcp/issues/166
