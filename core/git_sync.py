import os
import subprocess
import sys
import threading
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
_LOCK = threading.Lock()
_TIMER = None
_STARTED = False


def _is_sync_enabled() -> bool:
    if not (_BASE_DIR / ".git").exists():
        return False
    if "runserver" in sys.argv:
        return True
    return bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("AUTO_GIT_SYNC"))


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


def _configure_remote_with_token() -> None:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        return
    res = _run_git("remote", "get-url", "origin")
    url = (res.stdout or "").strip()
    if url.startswith("https://github.com/") and "@" not in url:
        authed = url.replace("https://github.com/", f"https://x-access-token:{token}@github.com/")
        _run_git("remote", "set-url", "origin", authed)


def sync_with_github(reason: str = "Sincronizacion automatica ERP Dandelion Star") -> None:
    if not _is_sync_enabled():
        return
    with _LOCK:
        try:
            _configure_remote_with_token()
            _run_git("add", "-A")
            media_dir = _BASE_DIR / "media"
            if media_dir.exists():
                _run_git("add", "-f", "media")
            status = _run_git("status", "--porcelain")
            if status.stdout.strip():
                _run_git("commit", "-m", reason)
            _run_git("pull", "--rebase", "-X", "ours", "origin", "main")
            _run_git("push", "origin", "main")
        except Exception:
            pass


def schedule_github_sync(reason: str = "Cambio registrado en ERP", delay: float = 6.0) -> None:
    global _TIMER
    if not _is_sync_enabled():
        return
    if _TIMER is not None:
        _TIMER.cancel()
    _TIMER = threading.Timer(delay, sync_with_github, args=(reason,))
    _TIMER.daemon = True
    _TIMER.start()


def init_auto_git_sync() -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True

    try:
        from django.db.models import FileField
        from django.db.models.signals import post_delete, post_save, pre_save

        def _normalize_media_paths(sender, instance, **kwargs):
            for field in sender._meta.get_fields():
                if isinstance(field, FileField):
                    file_val = getattr(instance, field.name, None)
                    if file_val and getattr(file_val, "name", None):
                        fixed = str(file_val.name).replace("\\", "/")
                        if fixed != file_val.name:
                            file_val.name = fixed

        def _on_db_change(sender, **kwargs):
            label = getattr(sender, "_meta", None)
            model_name = label.label if label else "datos"
            if model_name.startswith(("sessions.", "admin.", "contenttypes.")):
                return
            schedule_github_sync(f"Sync automatico: {model_name}")

        pre_save.connect(_normalize_media_paths, weak=False)
        post_save.connect(_on_db_change, weak=False)
        post_delete.connect(_on_db_change, weak=False)
    except Exception:
        pass

    if _is_sync_enabled():
        threading.Thread(
            target=sync_with_github,
            args=("Sincronizacion inicial con GitHub",),
            daemon=True,
        ).start()
