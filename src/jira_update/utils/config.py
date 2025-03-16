"""
Configuration module for JIRA Update Hook.
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
import keyring

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "config.yaml"


class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass


class Config:
    """Configuration handler for JIRA Update Hook."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration from YAML file.
        
        Args:
            config_path: Path to the configuration file. If None, uses default path.
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config = self._load_config()
        self._validate_config()
        self._setup_credentials()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.
        
        Returns:
            Dict containing configuration settings.
            
        Raises:
            ConfigError: If the configuration file cannot be loaded.
        """
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.debug(f"Loaded configuration from {self.config_path}")
                return config
        except FileNotFoundError:
            raise ConfigError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parsing configuration file: {e}")

    def _validate_config(self):
        """
        Validate the configuration.
        
        Raises:
            ConfigError: If the configuration is invalid.
        """
        # Check for required sections
        required_sections = ['jira', 'project', 'git']
        for section in required_sections:
            if section not in self.config:
                raise ConfigError(f"Missing required configuration section: {section}")

        # Validate JIRA configuration
        jira_config = self.config['jira']
        if 'url' not in jira_config:
            raise ConfigError("Missing JIRA URL in configuration")

        auth_method = jira_config.get('auth_method', 'basic')
        if auth_method == 'basic':
            if 'username' not in jira_config:
                raise ConfigError("Missing JIRA username in configuration")
        elif auth_method == 'oauth':
            if 'oauth' not in jira_config:
                raise ConfigError("Missing OAuth configuration for JIRA")
            oauth_config = jira_config['oauth']
            required_oauth_fields = ['access_token', 'access_token_secret', 'consumer_key', 'key_cert']
            for field in required_oauth_fields:
                if field not in oauth_config:
                    raise ConfigError(f"Missing OAuth field in configuration: {field}")
        else:
            raise ConfigError(f"Unsupported JIRA authentication method: {auth_method}")

        # Validate project configuration
        project_config = self.config['project']
        if 'keys' not in project_config:
            raise ConfigError("Missing project keys in configuration")
        if not isinstance(project_config['keys'], list):
            raise ConfigError("Project keys must be a list")

        logger.debug("Configuration validation successful")

    def _setup_credentials(self):
        """
        Set up credentials, potentially using secure storage.
        """
        use_keyring = self.config.get('advanced', {}).get('use_keyring', False)
        
        if use_keyring:
            jira_config = self.config['jira']
            auth_method = jira_config.get('auth_method', 'basic')
            
            if auth_method == 'basic':
                # Try to get password from keyring
                username = jira_config['username']
                password = keyring.get_password('jira_update', username)
                
                if password:
                    jira_config['password'] = password
                    logger.debug(f"Retrieved JIRA password from keyring for {username}")
                elif 'password' not in jira_config:
                    raise ConfigError("No JIRA password found in configuration or keyring")
            
            # Similar handling could be added for OAuth tokens if needed

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            section: Configuration section name.
            key: Configuration key within the section. If None, returns the entire section.
            default: Default value to return if the key is not found.
            
        Returns:
            Configuration value or default.
        """
        if section not in self.config:
            return default
        
        if key is None:
            return self.config[section]
        
        return self.config[section].get(key, default)

    def set_credential(self, username: str, password: str):
        """
        Store a credential securely in the keyring.
        
        Args:
            username: Username or identifier.
            password: Password or token to store.
        """
        use_keyring = self.config.get('advanced', {}).get('use_keyring', False)
        
        if use_keyring:
            keyring.set_password('jira_update', username, password)
            logger.debug(f"Stored JIRA password in keyring for {username}")
        else:
            logger.warning("Keyring storage is disabled in configuration")


# Singleton instance
_config_instance = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    Get the configuration singleton instance.
    
    Args:
        config_path: Optional path to configuration file.
        
    Returns:
        Config instance.
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance 