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
    cfg.setdefault('enable_streaming', True)
    cfg.setdefault('enable_thinking_summary', True)
    cfg.setdefault('max_continuations', 2)
    cfg.setdefault('flush_interval_ms', 250)
    cfg.setdefault('provider_timeout_s', 300)
    cfg.setdefault(
        'continuation_instruction',
        'Continue exactly where you left off. Do not repeat prior text.',
    )
    cfg.setdefault('per_call_max_tokens', int(cfg.get('chat_max_tokens', 4000)))
    cfg.setdefault('citations', True)
    cfg.setdefault('citations_mode', 'inline+sources')
    cfg.setdefault('citation_max_sources', int(cfg.get('top_k', 6)))
    cfg.setdefault('citation_max_snippet_chars', 240)
    cfg.setdefault('vector_db_provider', 'chroma')
    cfg.setdefault('vector_db_persist_dir', 'data/chroma')
    cfg.setdefault('vector_db_collection', 'easy_local_rag')
    cfg.setdefault('vector_db_batch_size', 64)
    cfg.setdefault('vector_db_timeout_s', 30)
    cfg.setdefault('embedding_dim', 1024)
    cfg.setdefault('ingest_max_bytes', 8 * 1024 * 1024)
    cfg.setdefault('ingest_max_rows', 2000)
    cfg.setdefault('ingest_max_objects', 2000)
    cfg.setdefault('ingest_max_pages', 200)
    cfg.setdefault('ingest_max_slides', 300)
    cfg.setdefault('ingest_max_sheets', 50)
    cfg.setdefault('ingest_timeout_s', 30)
    cfg.setdefault('ingest_zip_max_entries', 10000)
    cfg.setdefault('ingest_zip_max_uncompressed_bytes', 128 * 1024 * 1024)
    cfg.setdefault('ingest_enable_parquet', True)
    cfg.setdefault('ingest_enable_legacy_office', True)
    cfg.setdefault('ingest_state_path', 'data/ingest_state.json')
    cfg.setdefault('doc_registry_path', 'data/doc_registry.json')

    # Override with environment variables (if present)
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
    parsed_citations = _parse_bool_env(os.getenv('CITATIONS'))
    if parsed_citations is not None:
        cfg['citations'] = parsed_citations
    if os.getenv('CITATIONS_MODE'):
        mode = os.getenv('CITATIONS_MODE', '').strip().lower()
        if mode in {'inline', 'inline+sources', 'none'}:
            cfg['citations_mode'] = mode
    if os.getenv('CITATION_MAX_SOURCES'):
        try:
            cfg['citation_max_sources'] = max(0, int(os.getenv('CITATION_MAX_SOURCES')))
        except ValueError:
            pass
    if os.getenv('CITATION_MAX_SNIPPET_CHARS'):
        try:
            cfg['citation_max_snippet_chars'] = max(0, int(os.getenv('CITATION_MAX_SNIPPET_CHARS')))
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
    if os.getenv('VECTOR_DB_PROVIDER'):
        cfg['vector_db_provider'] = os.getenv('VECTOR_DB_PROVIDER')
    if os.getenv('VECTOR_DB_PERSIST_DIR'):
        cfg['vector_db_persist_dir'] = os.getenv('VECTOR_DB_PERSIST_DIR')
    if os.getenv('VECTOR_DB_COLLECTION'):
        cfg['vector_db_collection'] = os.getenv('VECTOR_DB_COLLECTION')
    if os.getenv('VECTOR_DB_BATCH_SIZE'):
        try:
            cfg['vector_db_batch_size'] = int(os.getenv('VECTOR_DB_BATCH_SIZE'))
        except ValueError:
            pass
    if os.getenv('VECTOR_DB_TIMEOUT_S'):
        try:
            cfg['vector_db_timeout_s'] = int(os.getenv('VECTOR_DB_TIMEOUT_S'))
        except ValueError:
            pass
    if os.getenv('EMBEDDING_DIM'):
        try:
            cfg['embedding_dim'] = int(os.getenv('EMBEDDING_DIM'))
        except ValueError:
            pass
    if os.getenv('INGEST_MAX_BYTES'):
        try:
            cfg['ingest_max_bytes'] = int(os.getenv('INGEST_MAX_BYTES'))
        except ValueError:
            pass
    if os.getenv('INGEST_MAX_ROWS'):
        try:
            cfg['ingest_max_rows'] = int(os.getenv('INGEST_MAX_ROWS'))
        except ValueError:
            pass
    if os.getenv('INGEST_MAX_OBJECTS'):
        try:
            cfg['ingest_max_objects'] = int(os.getenv('INGEST_MAX_OBJECTS'))
        except ValueError:
            pass
    if os.getenv('INGEST_MAX_PAGES'):
        try:
            cfg['ingest_max_pages'] = int(os.getenv('INGEST_MAX_PAGES'))
        except ValueError:
            pass
    if os.getenv('INGEST_MAX_SLIDES'):
        try:
            cfg['ingest_max_slides'] = int(os.getenv('INGEST_MAX_SLIDES'))
        except ValueError:
            pass
    if os.getenv('INGEST_MAX_SHEETS'):
        try:
            cfg['ingest_max_sheets'] = int(os.getenv('INGEST_MAX_SHEETS'))
        except ValueError:
            pass
    if os.getenv('INGEST_TIMEOUT_S'):
        try:
            cfg['ingest_timeout_s'] = int(os.getenv('INGEST_TIMEOUT_S'))
        except ValueError:
            pass
    if os.getenv('INGEST_ZIP_MAX_ENTRIES'):
        try:
            cfg['ingest_zip_max_entries'] = int(os.getenv('INGEST_ZIP_MAX_ENTRIES'))
        except ValueError:
            pass
    if os.getenv('INGEST_ZIP_MAX_UNCOMPRESSED_BYTES'):
        try:
            cfg['ingest_zip_max_uncompressed_bytes'] = int(os.getenv('INGEST_ZIP_MAX_UNCOMPRESSED_BYTES'))
        except ValueError:
            pass
    parsed_ingest_enable_parquet = _parse_bool_env(os.getenv('INGEST_ENABLE_PARQUET'))
    if parsed_ingest_enable_parquet is not None:
        cfg['ingest_enable_parquet'] = parsed_ingest_enable_parquet
    parsed_ingest_enable_legacy_office = _parse_bool_env(os.getenv('INGEST_ENABLE_LEGACY_OFFICE'))
    if parsed_ingest_enable_legacy_office is not None:
        cfg['ingest_enable_legacy_office'] = parsed_ingest_enable_legacy_office
    if os.getenv('INGEST_STATE_PATH'):
        cfg['ingest_state_path'] = os.getenv('INGEST_STATE_PATH')
    if os.getenv('DOC_REGISTRY_PATH'):
        cfg['doc_registry_path'] = os.getenv('DOC_REGISTRY_PATH')

    # Nested ollama_api overrides
    if os.getenv('OLLAMA_API_BASE_URL'):
        cfg.setdefault('ollama_api', {})['base_url'] = os.getenv('OLLAMA_API_BASE_URL')
    if os.getenv('OLLAMA_API_KEY'):
        cfg.setdefault('ollama_api', {})['api_key'] = os.getenv('OLLAMA_API_KEY')

    return cfg


# Module-level config loaded on import
CONFIG = load_settings()
