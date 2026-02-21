from app.cli.commands.documents import build_documents_cli
from app.cli.commands.ingestions import build_ingestions_cli
from app.cli.commands.namespaces import build_namespaces_cli
from app.cli.commands.system import build_system_cli

__all__ = [
    "build_system_cli",
    "build_namespaces_cli",
    "build_documents_cli",
    "build_ingestions_cli",
]
