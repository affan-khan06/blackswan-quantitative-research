from __future__ import annotations

from typing import Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.database.models import BacktestRecord, ExperimentRecord, StressTestRecord


class ExperimentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, record: ExperimentRecord) -> ExperimentRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update(self, record: ExperimentRecord) -> ExperimentRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get(self, exp_id: str) -> Optional[ExperimentRecord]:
        return self.db.get(ExperimentRecord, exp_id)

    def list_all(self, limit: int = 50) -> list[ExperimentRecord]:
        stmt = select(ExperimentRecord).order_by(desc(ExperimentRecord.created_at)).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_latest_completed(self) -> Optional[ExperimentRecord]:
        stmt = (
            select(ExperimentRecord)
            .where(ExperimentRecord.status == "COMPLETED")
            .order_by(desc(ExperimentRecord.created_at))
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def delete(self, exp_id: str) -> bool:
        rec = self.get(exp_id)
        if not rec:
            return False
        self.db.delete(rec)
        self.db.commit()
        return True


class BacktestRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, record: BacktestRecord) -> BacktestRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_recent(self, limit: int = 10) -> list[BacktestRecord]:
        stmt = select(BacktestRecord).order_by(desc(BacktestRecord.created_at)).limit(limit)
        return list(self.db.scalars(stmt).all())


class StressTestRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, record: StressTestRecord) -> StressTestRecord:
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_recent(self, limit: int = 20) -> list[StressTestRecord]:
        stmt = select(StressTestRecord).order_by(desc(StressTestRecord.created_at)).limit(limit)
        return list(self.db.scalars(stmt).all())
