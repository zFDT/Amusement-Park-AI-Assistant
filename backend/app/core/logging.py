"""应用统一日志配置。

同时输出到控制台和本地文件：
- backend/logs/app.log：通用应用日志
- backend/logs/ai.log：AI 交互与提炼相关日志
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


_CONFIGURED = False


def _build_formatter() -> logging.Formatter:
    return logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")


def _build_file_handler(path: Path, level: int) -> logging.Handler:
    handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(_build_formatter())
    handler._youyuan_handler = True  # type: ignore[attr-defined]
    return handler


def _build_console_handler(level: int) -> logging.Handler:
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(_build_formatter())
    handler._youyuan_handler = True  # type: ignore[attr-defined]
    return handler


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root/app.ai loggers once.

    Safe to call multiple times.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    backend_root = Path(__file__).resolve().parents[2]
    log_dir = backend_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    has_console = any(getattr(handler, "_youyuan_handler", False) for handler in root.handlers)
    if not has_console:
        root.addHandler(_build_console_handler(level))

    has_app_file = any(
        isinstance(handler, RotatingFileHandler)
        and Path(getattr(handler, "baseFilename", "")).name == "app.log"
        for handler in root.handlers
    )
    if not has_app_file:
        root.addHandler(_build_file_handler(log_dir / "app.log", level))

    ai_logger = logging.getLogger("app.ai")
    ai_logger.setLevel(level)
    ai_logger.propagate = True
    has_ai_file = any(
        isinstance(handler, RotatingFileHandler)
        and Path(getattr(handler, "baseFilename", "")).name == "ai.log"
        for handler in ai_logger.handlers
    )
    if not has_ai_file:
        ai_logger.addHandler(_build_file_handler(log_dir / "ai.log", level))

    # uvicorn access log → access.log（记录前端→后端每条 HTTP 请求，方便排查交互问题）
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.setLevel(level)
    access_logger.propagate = False  # 不重复写到 app.log
    has_access_file = any(
        isinstance(handler, RotatingFileHandler)
        and Path(getattr(handler, "baseFilename", "")).name == "access.log"
        for handler in access_logger.handlers
    )
    if not has_access_file:
        access_logger.addHandler(_build_file_handler(log_dir / "access.log", level))

    # uvicorn error/startup log → app.log（已由 root logger 捕获，确保 uvicorn logger 不重复）
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(level)
    uvicorn_logger.propagate = True

    _CONFIGURED = True
