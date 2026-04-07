"""
logs/logger.py
--------------
Loguru-based logger.
- Terminal  : coloured, DEBUG+
- File      : plain text, INFO+, daily rotation, 7-day retention
- Noisy third-party libs (urllib3, httpx, hypercorn, etc.) silenced to WARNING.
"""

import sys
import logging
from loguru import logger


# ── Intercept handler: routes standard logging → Loguru ──────────────────────

class _InterceptHandler(logging.Handler):
    """
    Redirect every record that comes through the standard logging system
    into Loguru so formatting and routing stay consistent.
    """
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Walk up the call stack to find the real caller (skip logging internals)
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# ── Noisy libs to silence ─────────────────────────────────────────────────────

_SILENCE = [
    "urllib3",
    "urllib3.connectionpool",
    "requests",
    "httpx",
    "httpcore",
    "aiohttp",
    "asyncio",
    "hypercorn",
    "hypercorn.access",
    "hypercorn.error",
    "quart",
    "quart.serving",
    "werkzeug",
]


# ── Public setup function ─────────────────────────────────────────────────────

def setup_logger(log_file: str = "logs/logs/app.log") -> None:
    """
    Call once at application startup (already called in app.py).
    """
    # Remove Loguru's default stderr sink
    logger.remove()

    # ── Terminal sink (coloured) ──────────────────────────────────────────────
    logger.add(
        sys.stderr,
        level="DEBUG",
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "<level>[{level}]</level> "
            "<cyan>{name}</cyan> — "
            "<level>{message}</level>"
        ),
    )

    # ── File sink (plain, rotated daily, kept 7 days) ─────────────────────────
    logger.add(
        log_file,
        level="INFO",
        colorize=False,
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {name} — {message}",
    )

    # ── Route standard logging → Loguru ──────────────────────────────────────
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    # ── Silence noisy third-party loggers ────────────────────────────────────
    for name in _SILENCE:
        logging.getLogger(name).setLevel(logging.WARNING)