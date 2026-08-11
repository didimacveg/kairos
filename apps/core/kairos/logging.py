"""Logging estructurado en JSON a stdout.

Los logs operativos van a stdout (efimeros, para depurar). Los hechos que
importan para la auditoria van a la tabla audit_log (ver kairos/audit).
No confundir ambos: stdout se pierde, la auditoria no.
"""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(env: str) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
            if env == "production"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
