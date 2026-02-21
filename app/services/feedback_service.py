from __future__ import annotations

import uuid

from app.repositories.sqlite.feedback_repo import FeedbackRepository


class FeedbackService:
    def __init__(self, db_path: str) -> None:
        self.repo = FeedbackRepository(db_path)

    def add_feedback(
        self,
        *,
        run_id: str | None = None,
        thumb: str | None = None,
        note: str | None = None,
        citation_id: str | None = None,
    ) -> dict:
        feedback_id = str(uuid.uuid4())
        return self.repo.create(
            feedback_id=feedback_id,
            run_id=run_id,
            thumb=thumb,
            note=note,
            citation_id=citation_id,
        )

    def export_feedback(self, *, run_id: str) -> list[dict]:
        return self.repo.list_by_run(run_id)

