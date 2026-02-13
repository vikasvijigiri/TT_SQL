"""
Pipeline Configuration Loader
Loads and validates the pipeline configuration from YAML
"""
import yaml
import os
from typing import Dict, List, Any
from pathlib import Path


class PipelineConfig:
    """Loads and manages pipeline configuration"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to config/pipeline_config.yaml in the package
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "config",
                "pipeline_config.yaml"
            )
        
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Pipeline config not found at: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in pipeline config: {e}")
    
    def get_execution_order(self) -> List[Dict[str, Any]]:
        """Get the ordered list of agents to execute"""
        return self.config.get('pipeline', {}).get('execution_order', [])
    
    def get_enabled_agents(self) -> List[str]:
        """Get list of enabled agent names"""
        agents = []
        for agent_config in self.get_execution_order():
            if agent_config.get('enabled', True):
                agents.append(agent_config['agent'])
        return agents
    
    def get_agent_settings(self, agent_name: str) -> Dict[str, Any]:
        """Get settings for a specific agent"""
        return self.config.get('agent_settings', {}).get(agent_name, {})
    
    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if an agent is enabled"""
        for agent_config in self.get_execution_order():
            if agent_config['agent'] == agent_name:
                return agent_config.get('enabled', True)
        return False
    
    def get_logging_settings(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.config.get('logging', {})
    
    def reload(self):
        """Reload configuration from file"""
        self.config = self._load_config()
