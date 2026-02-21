from app.cli.commands.documents import build_documents_cli
from app.cli.commands.feedback import build_feedback_cli
from app.cli.commands.ingestions import build_ingestions_cli
from app.cli.commands.namespaces import build_namespaces_cli
from app.cli.commands.query import register_query_commands
from app.cli.commands.retrieve import register_retrieval_commands
from app.cli.commands.runs import build_runs_cli
from app.cli.commands.system import build_system_cli

__all__ = [
    "build_system_cli",
    "build_namespaces_cli",
    "build_documents_cli",
    "build_feedback_cli",
    "build_ingestions_cli",
    "register_query_commands",
    "register_retrieval_commands",
    "build_runs_cli",
]
