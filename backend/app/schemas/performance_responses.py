"""Validated public response shapes for Phase 4 reads and commands."""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Response(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Progress(Response):
    state: Literal["Configured", "No Target"]
    achieved: str
    achievementPercentage: str | None


class EmployeeProgress(Progress):
    activeOnEndDate: bool


class Summary(Response):
    createdCaseCount: int
    bookedCaseCount: int
    completedCaseCount: int
    rejectedCaseCount: int
    inProgressCaseCount: int
    inProgressByStage: dict[str, int]
    delayedCaseCount: int | None
    delayedMetricState: Literal["Available", "Holiday calendar unavailable"]
    achievedCCPoints: str
    achievedPFAed: str
    targetProgress: Mapping[Literal["CC", "PF"], Progress]


class EmployeeIdentity(Response):
    employeeName: str | None = None
    systemEmployeeCode: str | None = None
    companyEmployeeCode: str | None = None
    designation: str | None = None
    branchName: str | None = None
    departmentName: str | None = None
    avatarFileId: UUID | None = None


class EmployeeMetrics(Summary, EmployeeIdentity):
    employeeId: UUID
    startDate: date
    endDate: date
    targetProgress: dict[Literal["CC", "PF"], EmployeeProgress]


class EmployeePage(Response):
    items: list[EmployeeMetrics]
    summary: Summary | None = None
    total: int
    page: int
    pageSize: int


class TeamPage(EmployeePage):
    teamId: UUID
    summary: Summary


class TrendProductValues(Response):
    createdCaseCount: int
    bookedCaseCount: int
    completedCaseCount: int
    achieved: str
    achievementPercentage: str | None


class TrendMonth(Response):
    start: date
    end: date
    label: str
    CC: TrendProductValues | None
    PF: TrendProductValues | None


class EmployeeTrend(Response):
    employeeId: UUID
    startDate: date
    endDate: date
    items: list[TrendMonth]


class ComparisonItem(Summary):
    id: UUID
    name: str


class ComparisonPage(Response):
    groupBy: Literal["branch", "department"]
    items: list[ComparisonItem]
    total: int
    page: int
    pageSize: int


class CoordinatorMetrics(EmployeeIdentity):
    employeeId: UUID
    handledCases: int
    submittedBookedCases: int
    stageUpdatedCases: int


class PeerAverages(Response):
    handledCases: str | None
    submittedBookedCases: str | None
    stageUpdatedCases: str | None


class PeerAggregate(Response):
    peerCount: int
    average: PeerAverages


class CoordinatorOwnMetrics(CoordinatorMetrics):
    peerAggregate: PeerAggregate


class CoordinatorPage(Response):
    items: list[CoordinatorMetrics]
    total: int
    page: int
    pageSize: int


class RankingItem(Response):
    employeeId: UUID
    employeeName: str
    achievementPercentage: str
    completedCaseCount: int
    achievedValue: str
    rank: int


class RankingPage(Response):
    items: list[RankingItem]
    total: int
    page: int
    pageSize: int
    winnerEmployeeId: UUID | None
    decisionState: Literal[
        "No eligible employees", "Confirmed", "Owner decision pending", "Automatic"
    ]
    tiedCandidateIds: list[UUID]
    confirmedByEmployeeId: UUID | None
    confirmedAt: datetime | None


class RankingConfirmation(Response):
    winnerEmployeeId: UUID
    decisionState: Literal["Confirmed"]
    confirmedAt: datetime


class HolidayDate(Response):
    id: UUID
    holidayDate: date
    applicableYear: int
    name: str
    sourceReference: str


class HolidayDatePage(Response):
    items: list[HolidayDate]
    total: int
    page: int
    pageSize: int


class HolidayYear(Response):
    applicableYear: int
    sourceReference: str
    certifiedAt: datetime


class HolidayYearPage(Response):
    items: list[HolidayYear]


class HolidayYearCertification(Response):
    id: UUID
    applicableYear: int
    sourceReference: str
    holidayDateCount: int
