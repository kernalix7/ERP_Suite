"""JSON log formatter for SIEM integration.

Outputs structured JSON log lines suitable for ingestion by Loki, ELK,
Splunk, or any JSON-aware log aggregator.
"""
import json
import logging
import traceback
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Output fields:
        timestamp, level, logger, message, module, funcName, lineno,
        and any extras passed via the `extra` dict.

    Exception info is included as `exception` when present.
    """

    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(
                record.created, tz=timezone.utc,
            ).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'funcName': record.funcName,
            'lineno': record.lineno,
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info),
            }

        # Include extra fields (skip standard LogRecord attributes)
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'relativeCreated',
            'exc_info', 'exc_text', 'stack_info', 'levelname', 'levelno',
            'pathname', 'filename', 'module', 'lineno', 'funcName',
            'thread', 'threadName', 'process', 'processName', 'message',
            'msecs', 'taskName',
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                try:
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        return json.dumps(log_entry, ensure_ascii=False, default=str)
