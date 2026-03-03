import yaml
from pathlib import Path
from typing import Dict, Any

class BrandingManager:
    def __init__(self, config_path: str = "src/branitz_heat_decision/config/branding.yaml"):
        self.config_path = Path(config_path)
        self._config = None
    
    def load(self) -> Dict[str, Any]:
        if self._config is None:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    self._config = yaml.safe_load(f)
            else:
                self._config = self._default_config()
        return self._config
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "branding": {
                "app_name": "Heat Planning Tool",
                "organization": "Research Institution",
                "theme": {"primary": "#007BFF"},
                "features": {"show_powered_by": True}
            }
        }
    
    def get(self, key: str, default=None):
        keys = key.split('.')
        value = self.load()
        for k in keys:
            value = value.get(k, {})
        return value if value != {} else default

branding = BrandingManager()
