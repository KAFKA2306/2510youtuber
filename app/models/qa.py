"""Media quality assurance data models."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field

MetricValue = Union[int, float, str]


class CheckStatus(str, Enum):
    """Status for individual QA checks."""

    PASSED = "passed"
    FAILED = "failed"
    WARN = "warn"
    SKIPPED = "skipped"


class MediaCheckResult(BaseModel):
    """Result of a single QA check."""

    name: str
    status: CheckStatus
    blocking: bool = True
    message: Optional[str] = None
    metrics: Dict[str, MetricValue] = Field(default_factory=dict)
    detail: Optional[str] = None


class QualityGateReport(BaseModel):
    """Aggregated QA report persisted for traceability."""

    run_id: str
    mode: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    checks: List[MediaCheckResult] = Field(default_factory=list)
    report_path: Optional[str] = None

    def add_check(self, check: MediaCheckResult) -> None:
        self.checks.append(check)

    @property
    def passed(self) -> bool:
        return all(
            check.status != CheckStatus.FAILED or not check.blocking
            for check in self.checks
        )

    def blocking_failures(self) -> List[MediaCheckResult]:
        return [check for check in self.checks if check.blocking and check.status == CheckStatus.FAILED]

    def warnings(self) -> List[MediaCheckResult]:
        return [check for check in self.checks if check.status == CheckStatus.WARN]

    def dict(self, **kwargs) -> Dict[str, Union[str, Dict[str, MetricValue], bool, List[str]]]:
        payload = super().dict(**kwargs)
        payload["created_at"] = self.created_at.isoformat()
        payload["passed"] = self.passed
        payload["blocking_failures"] = [check.name for check in self.blocking_failures()]
        return payload
