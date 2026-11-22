try:
    from .git_sync import init_auto_git_sync as _init_auto_git_sync
    _init_auto_git_sync()
except Exception:
    pass
