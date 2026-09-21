import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "server": {
        "host": "0.0.0.0",
        "port": 7860,
        "ssl_enabled": True,
        "ssl_certfile": "certs/cert.pem",
        "ssl_keyfile": "certs/key.pem"
    },
    "comfyui": {
        "url": "http://127.0.0.1:8188"
    },
    "active_project_path": "E:\\Projects\\Manhwa Cinema Lab\\He_Gains_Attributes_Recap",
    "projects": [
        {
            "name": "Manhwa Cinema Lab (Recap)",
            "path": "E:\\Projects\\Manhwa Cinema Lab\\He_Gains_Attributes_Recap",
            "type": "manhwa"
        },
        {
            "name": "Manhwa Cinema Lab (Root)",
            "path": "E:\\Projects\\Manhwa Cinema Lab",
            "type": "manhwa"
        },
        {
            "name": "BHRS - Youtube",
            "path": "E:\\Projects\\BHRS-Youtube",
            "type": "documentary"
        },
        {
            "name": "Bible Hidden Secrets Revealed",
            "path": "C:\\Projects\\Bible Hidden Secrets Revealed",
            "type": "documentary"
        },
        {
            "name": "Bible Hidden Secrets Revealed (E:)",
            "path": "E:\\Projects\\Bible Hidden Secrets Revealed",
            "type": "documentary"
        }
    ],
    "social": {
        "dry_run": True,
        "auto_publish_on_approve": True,
        "webhook_url": "",
        "youtube": {
            "enabled": True,
            "privacy_status": "unlisted",
            "client_secrets_file": "",
            "credentials_file": ""
        },
        "facebook": {
            "enabled": True,
            "page_id": "",
            "page_access_token": ""
        },
        "tiktok": {
            "enabled": True,
            "access_token": ""
        },
        "x": {
            "enabled": True,
            "api_key": "",
            "api_secret": "",
            "access_token": "",
            "access_token_secret": ""
        },
        "instagram": {
            "enabled": True,
            "account_id": "",
            "access_token": ""
        }
    }
}

class ConfigManager:
    def __init__(self, config_path: Path = CONFIG_FILE):
        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge with default config to ensure missing keys exist
                    merged = DEFAULT_CONFIG.copy()
                    for k, v in data.items():
                        if isinstance(v, dict) and k in merged:
                            merged[k] = {**merged[k], **v}
                        else:
                            merged[k] = v
                    return merged
            except Exception as e:
                print(f"[Config] Error loading {self.config_path}: {e}. Using defaults.")
        self._save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    def _save_config(self, cfg: Dict[str, Any]):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def get_all(self) -> Dict[str, Any]:
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value
        self._save_config(self._config)

    def get_active_project(self) -> str:
        # If the active path does not exist on disk, fallback to one that does
        active = self._config.get("active_project_path", "")
        if active and Path(active).exists():
            return active
        for p in self._config.get("projects", []):
            if Path(p["path"]).exists():
                self.set_active_project(p["path"])
                return p["path"]
        return active

    def set_active_project(self, project_path: str):
        self._config["active_project_path"] = project_path
        self._save_config(self._config)

    def add_project(self, name: str, path: str, project_type: str = "custom") -> Dict[str, Any]:
        projects = self._config.get("projects", [])
        for p in projects:
            if p["path"].lower() == path.lower():
                p["name"] = name
                p["type"] = project_type
                self._save_config(self._config)
                return p
        new_proj = {"name": name, "path": path, "type": project_type}
        projects.append(new_proj)
        self._config["projects"] = projects
        self._save_config(self._config)
        return new_proj

    def update_project(self, old_path: str, name: str, new_path: str, project_type: str = "custom") -> Optional[Dict[str, Any]]:
        """Updates project name, folder location (path) and type in configuration."""
        projects = self._config.get("projects", [])
        target = None
        for p in projects:
            if p["path"].lower() == old_path.lower():
                target = p
                p["name"] = name
                p["path"] = new_path
                p["type"] = project_type
                break
        if target:
            if self._config.get("active_project_path", "").lower() == old_path.lower():
                self._config["active_project_path"] = new_path
            self._save_config(self._config)
        return target

    def remove_project(self, project_path: str) -> bool:
        """Removes project entry from configuration list only. Never touches or deletes files on disk."""
        projects = self._config.get("projects", [])
        initial_len = len(projects)
        self._config["projects"] = [p for p in projects if p["path"].lower() != project_path.lower()]
        removed = len(self._config["projects"]) < initial_len

        # If we removed the active project, switch to another available project
        if self._config.get("active_project_path", "").lower() == project_path.lower():
            next_active = ""
            for p in self._config.get("projects", []):
                if not p.get("hidden", False) and Path(p["path"]).exists():
                    next_active = p["path"]
                    break
            if not next_active and self._config.get("projects"):
                next_active = self._config["projects"][0]["path"]
            self._config["active_project_path"] = next_active

        self._save_config(self._config)
        return removed

    def toggle_hide_project(self, project_path: str, hidden: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        """Toggles or sets the hidden status of a project entry. Never deletes files on disk."""
        projects = self._config.get("projects", [])
        target = None
        for p in projects:
            if p["path"].lower() == project_path.lower():
                target = p
                if hidden is None:
                    p["hidden"] = not p.get("hidden", False)
                else:
                    p["hidden"] = hidden
                break

        if target:
            # If hiding active project, try to switch active to another non-hidden project
            if target.get("hidden", False) and self._config.get("active_project_path", "").lower() == project_path.lower():
                for p in projects:
                    if not p.get("hidden", False) and Path(p["path"]).exists():
                        self._config["active_project_path"] = p["path"]
                        break
            self._save_config(self._config)
        return target

    def update_social_config(self, social_data: Dict[str, Any]):
        current = self._config.get("social", {})
        current.update(social_data)
        self._config["social"] = current
        self._save_config(self._config)

config_manager = ConfigManager()
