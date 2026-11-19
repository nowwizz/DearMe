import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
load_dotenv(ROOT / '.env')


def setting(name, default=''):
    return os.getenv(name, default).strip()


def integer_setting(name, default, low, high):
    try:
        return min(high, max(low, int(setting(name, str(default)))))
    except ValueError:
        return default


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')
