from __future__ import annotations

from app.repositories.sqlite.runs_repo import RunsRepository


class RunService:
    def __init__(self, db_path: str) -> None:
        self.repo = RunsRepository(db_path)

    def get_run(self, run_id: str) -> dict | None:
        return self.repo.get(run_id)

    def get_steps(self, run_id: str) -> list[dict]:
        return self.repo.list_steps(run_id)

    def get_events(self, run_id: str, limit: int = 1000) -> list[dict]:
        return self.repo.list_events(run_id, limit=limit)
