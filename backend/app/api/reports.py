from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.engine.reports import compare_reports
from app.models import Report, TestRun, User
from app.schemas import ComparisonResponse, ReportOut

router = APIRouter(prefix="/api/reports", tags=["reports"])


async def _get_owned_report(report_id: int, user: User, db: AsyncSession) -> Report:
    report = await db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    run = await db.get(TestRun, report.test_run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return report


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(
    report_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await _get_owned_report(report_id, user, db)


@router.get("/{report_id}/compare/{other_report_id}", response_model=ComparisonResponse)
async def compare_two_reports(
    report_id: int,
    other_report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    baseline = await _get_owned_report(report_id, user, db)
    candidate = await _get_owned_report(other_report_id, user, db)
    return compare_reports(baseline.summary, candidate.summary)
