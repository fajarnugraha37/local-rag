import os
import yaml
from dotenv import load_dotenv


def _parse_bool_env(value):
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    return None


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

    # Streaming/continuation defaults (feature 003)
    cfg.setdefault('enable_streaming', False)
    cfg.setdefault('enable_thinking_summary', False)
    cfg.setdefault('max_continuations', 2)
    cfg.setdefault('flush_interval_ms', 250)
    cfg.setdefault('provider_timeout_s', int(cfg.get('model_timeout', 120)))
    cfg.setdefault(
        'continuation_instruction',
        'Continue exactly where you left off. Do not repeat prior text.',
    )
    cfg.setdefault('per_call_max_tokens', int(cfg.get('chat_max_tokens', 4000)))

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
    parsed_enable_streaming = _parse_bool_env(os.getenv('ENABLE_STREAMING'))
    if parsed_enable_streaming is not None:
        cfg['enable_streaming'] = parsed_enable_streaming
    parsed_enable_thinking_summary = _parse_bool_env(os.getenv('ENABLE_THINKING_SUMMARY'))
    if parsed_enable_thinking_summary is not None:
        cfg['enable_thinking_summary'] = parsed_enable_thinking_summary
    if os.getenv('PER_CALL_MAX_TOKENS'):
        try:
            cfg['per_call_max_tokens'] = int(os.getenv('PER_CALL_MAX_TOKENS'))
        except ValueError:
            pass
    if os.getenv('MAX_CONTINUATIONS'):
        try:
            cfg['max_continuations'] = int(os.getenv('MAX_CONTINUATIONS'))
        except ValueError:
            pass
    if os.getenv('FLUSH_INTERVAL_MS'):
        try:
            cfg['flush_interval_ms'] = int(os.getenv('FLUSH_INTERVAL_MS'))
        except ValueError:
            pass
    if os.getenv('PROVIDER_TIMEOUT_S'):
        try:
            cfg['provider_timeout_s'] = int(os.getenv('PROVIDER_TIMEOUT_S'))
        except ValueError:
            pass
    if os.getenv('CONTINUATION_INSTRUCTION'):
        cfg['continuation_instruction'] = os.getenv('CONTINUATION_INSTRUCTION')

    # Nested ollama_api overrides
    if os.getenv('OLLAMA_API_BASE_URL'):
        cfg.setdefault('ollama_api', {})['base_url'] = os.getenv('OLLAMA_API_BASE_URL')
    if os.getenv('OLLAMA_API_KEY'):
        cfg.setdefault('ollama_api', {})['api_key'] = os.getenv('OLLAMA_API_KEY')

    return cfg


# Module-level config loaded on import
CONFIG = load_settings()
