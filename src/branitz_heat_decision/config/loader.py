import yaml
from pathlib import Path
from typing import Dict
from .schemas import AppConfig, CityConfig

class ConfigManager:
    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path(__file__).parent
        self._app_config: AppConfig = None
        self._city_configs: Dict[str, CityConfig] = {}
    
    def load_app_config(self) -> AppConfig:
        """Load main application settings"""
        if self._app_config is None:
            settings_file = self.config_dir / "settings.yaml"
            if settings_file.exists():
                with open(settings_file) as f:
                    data = yaml.safe_load(f)
            else:
                data = {}
            
            # Load all city configs
            cities_dir = self.config_dir / "cities"
            cities = {}
            for city_file in cities_dir.glob("*.yaml"):
                with open(city_file) as f:
                    city_data = yaml.safe_load(f)
                    city_name = city_file.stem
                    cities[city_name] = CityConfig(**city_data)
            
            data['cities'] = cities
            self._app_config = AppConfig(**data)
        
        return self._app_config
    
    def get_city_config(self, city_name: str) -> CityConfig:
        """Get specific city configuration"""
        config = self.load_app_config()
        if city_name not in config.cities:
            raise ValueError(f"City {city_name} not found. Available: {list(config.cities.keys())}")
        return config.cities[city_name]
    
    def get_economic_params(self, city_name: str = None):
        """Convenience method for economic calculations"""
        if city_name:
            return self.get_city_config(city_name).economic
        return self.load_app_config().cities[self._app_config.default_city].economic

# Global singleton instance
config_manager = ConfigManager()
