import os


def _required_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def _optional_int_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


# Required secrets
TELEGRAM_TOKEN = _required_env("TELEGRAM_TOKEN")
DISCORD_BOT_TOKEN = _required_env("DISCORD_BOT_TOKEN")
DISCORD_WEBHOOK_URL = _required_env("DISCORD_WEBHOOK_URL")

# Optional settings
DISCORD_CHANNEL_ID = _optional_int_env("DISCORD_CHANNEL_ID")
DB_NAME = os.getenv("DB_NAME", "insults.db")

# Discord ID -> Telegram nickname
PARTICIPANTS = {
    "507127176202813440": "devil1oy",
    "519171642719600650": "SXLDE",
    "468826629913968653": "IoNaTao",
    "477215625836756994": "DOGGI337",
    "517779961663324170": "makclightning",
}
