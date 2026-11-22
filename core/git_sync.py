import os
import subprocess
import sys
import threading
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
_LOCK = threading.Lock()
_TIMER = None
_STARTED = False


def _run_git(*args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    git_paths = [
        r"C:\Program Files\Git\cmd",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd"),
    ]
    env["PATH"] = ";".join(git_paths) + ";" + env.get("PATH", "")
    return subprocess.run(
        ["git", *args],
        cwd=str(_BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )


def sync_with_github(reason: str = "Actualizacion automatica desde ERP local") -> None:
    if not (_BASE_DIR / ".git").exists():
        return
    with _LOCK:
        try:
            _run_git("add", "-A")
            status = _run_git("status", "--porcelain")
            if status.stdout.strip():
                _run_git("commit", "-m", reason)
            _run_git("pull", "--rebase", "-X", "ours", "origin", "main")
            _run_git("push", "origin", "main")
        except Exception:
            pass


def schedule_github_sync(reason: str = "Cambio registrado en ERP local", delay: float = 8.0) -> None:
    global _TIMER
    if "runserver" not in sys.argv:
        return
    if _TIMER is not None:
        _TIMER.cancel()
    _TIMER = threading.Timer(delay, sync_with_github, args=(reason,))
    _TIMER.daemon = True
    _TIMER.start()


def init_auto_git_sync() -> None:
    global _STARTED
    if _STARTED or "runserver" not in sys.argv:
        return
    _STARTED = True

    # Al arrancar localmente, traer primero cualquier cambio nuevo desde GitHub
    threading.Thread(
        target=sync_with_github,
        args=("Sincronizacion inicial con GitHub",),
        daemon=True,
    ).start()

    try:
        from django.db.models.signals import post_delete, post_save

        def _on_db_change(sender, **kwargs):
            label = getattr(sender, "_meta", None)
            model_name = label.label if label else "datos"
            if model_name.startswith(("sessions.", "admin.", "contenttypes.")):
                return
            schedule_github_sync(f"Sync automatico: {model_name}")

        post_save.connect(_on_db_change, weak=False)
        post_delete.connect(_on_db_change, weak=False)
    except Exception:
        pass
