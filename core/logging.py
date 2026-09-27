import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit bounded metadata; never add request bodies or model/audio payloads."""

    def format(self, record):
        return json.dumps(
            {
                "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=False,
        )
