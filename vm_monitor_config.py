from pathlib import Path

# LOG_DIR = Path("/var/log/system_monitor")
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "usage_peak.log"