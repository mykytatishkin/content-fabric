"""Centralized logging configuration with structured JSON output."""

from __future__ import annotations

import logging
import os
import sys


def setup_logging(service_name: str = "cff") -> None:
    """Configure logging for the application.

    Uses JSON format when LOG_FORMAT=json (production), plain text otherwise.
    """
    level_name = os.environ.get("LOG_LEVEL", "DEBUG" if os.environ.get("DEBUG") == "1" else "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)
    use_json = os.environ.get("LOG_FORMAT", "").lower() == "json"

    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if use_json:
        try:
            from pythonjsonlogger import jsonlogger

            formatter = jsonlogger.JsonFormatter(
                fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
                rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
            )
            formatter.default_msec_format = "%s.%03d"
        except ImportError:
            formatter = logging.Formatter(
                fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Quiet noisy libraries
    for name in ("urllib3", "sqlalchemy.engine", "googleapiclient", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger(service_name).info("Logging initialized: level=%s json=%s service=%s", level_name, use_json, service_name)
