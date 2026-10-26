"""Which repositories the dashboard tracks, and with which branch and tags (config/repos.json)."""
from .config import ConfigError, load
from .resolve import resolve
