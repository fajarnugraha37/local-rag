import os
import yaml
from dotenv import load_dotenv


def load_settings(config_file='config.yaml'):
    """Load settings from a YAML config file and override with environment variables (.env).

    Returns a dict of configuration values.
    """
    load_dotenv()

    cfg = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
        except Exception:
            cfg = {}

    # Ensure nested structure for ollama_api
    if 'ollama_api' not in cfg or cfg.get('ollama_api') is None:
        cfg['ollama_api'] = {}

    # Override with environment variables (if present)
    if os.getenv('VAULT_FILE'):
        cfg['vault_file'] = os.getenv('VAULT_FILE')
    if os.getenv('EMBEDDINGS_FILE'):
        cfg['embeddings_file'] = os.getenv('EMBEDDINGS_FILE')
    if os.getenv('OLLAMA_MODEL'):
        cfg['ollama_model'] = os.getenv('OLLAMA_MODEL')
    if os.getenv('TOP_K'):
        try:
            cfg['top_k'] = int(os.getenv('TOP_K'))
        except ValueError:
            pass
    if os.getenv('SYSTEM_MESSAGE'):
        cfg['system_message'] = os.getenv('SYSTEM_MESSAGE')

    # Nested ollama_api overrides
    if os.getenv('OLLAMA_API_BASE_URL'):
        cfg.setdefault('ollama_api', {})['base_url'] = os.getenv('OLLAMA_API_BASE_URL')
    if os.getenv('OLLAMA_API_KEY'):
        cfg.setdefault('ollama_api', {})['api_key'] = os.getenv('OLLAMA_API_KEY')

    return cfg


# Module-level config loaded on import
CONFIG = load_settings()
