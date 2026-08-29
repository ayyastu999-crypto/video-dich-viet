import os
import yaml
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    """Nap bien moi truong tu file .env (khong can thu vien ngoai)."""
    f = Path(path)
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def resolve_secrets(cfg: dict) -> dict:
    """Lay API key tu bien moi truong khi config de trong.

    Uu tien bien moi truong -> khong bao gio phai ghi key vao source.
    """
    rv = cfg.get("revid", {})
    if not rv.get("api_key"):
        rv["api_key"] = os.getenv("REVIDAPI_KEY", "")
        cfg["revid"] = rv

    tr = cfg.get("translation", {})
    if not tr.get("api_key"):
        provider = tr.get("provider", "gemini")
        env_name = {"gemini": "GEMINI_API_KEY",
                    "openai": "OPENAI_API_KEY",
                    "deepseek": "DEEPSEEK_API_KEY"}.get(provider, "GEMINI_API_KEY")
        tr["api_key"] = os.getenv(env_name, "")
        cfg["translation"] = tr
    return cfg


def load_config(config_path: str = "config/default.yaml") -> dict:
    """Load YAML config file and return as dict."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    load_dotenv()
    with open(path, "r", encoding="utf-8") as f:
        return resolve_secrets(yaml.safe_load(f))


def merge_config(base: dict, overrides: dict) -> dict:
    """Deep merge overrides into base config."""
    result = base.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    return result
