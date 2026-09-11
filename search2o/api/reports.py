# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from fastapi import APIRouter, Request
from pydantic import Field

from search2o.common.rest_call import RestCall
from search2o.models.configtypes import AgentName
from search2o.models.apimodels import BaseResponseModel, ReportWindow
from search2o.models.reportmodels import AgentPerformanceReportModel, AgentErrorsReportModel, AgentCostReportModel, \
    AgentDetailReportModel, AgentErrorDetailReportModel, AgentCostDetailReportModel, UserUsageReportModel, \
    UserDetailReportModel, UserUsageSortField


reports_router = APIRouter(prefix="/api/reports", tags=["reports"])


class AgentPerformanceReportResponseModel(BaseResponseModel):
    report: AgentPerformanceReportModel


@reports_router.post("/getAgentPerformanceReport", response_model=AgentPerformanceReportResponseModel, summary="Get agent performance report", description="Report execution and latency stats for each agent")
async def getAgentPerformanceReport(item: ReportWindow, request: Request) -> AgentPerformanceReportResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return AgentPerformanceReportResponseModel.model_validate(ret)


class AgentErrorsReportResponseModel(BaseResponseModel):
    report: AgentErrorsReportModel


@reports_router.post("/getAgentErrorReport", response_model=AgentErrorsReportResponseModel, summary="Get agent error report", description="Report which agents failed, how often, and with which result codes")
async def getAgentErrorReport(item: ReportWindow, request: Request) -> AgentErrorsReportResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return AgentErrorsReportResponseModel.model_validate(ret)


class AgentCostReportResponseModel(BaseResponseModel):
    report: AgentCostReportModel


@reports_router.post("/getAgentCostReport", response_model=AgentCostReportResponseModel, summary="Get agent cost report", description="Report LLM cost stats for each agent")
async def getAgentCostReport(item: ReportWindow, request: Request) -> AgentCostReportResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return AgentCostReportResponseModel.model_validate(ret)


class GetAgentDetailReportModel(ReportWindow):
    agentName: AgentName


class AgentDetailReportResponseModel(BaseResponseModel):
    report: AgentDetailReportModel


@reports_router.post("/getAgentDetailReport", response_model=AgentDetailReportResponseModel, summary="Get an agent's detail report", description="Report per-version execution stats and trend for an agent")
async def getAgentDetailReport(item: GetAgentDetailReportModel, request: Request) -> AgentDetailReportResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return AgentDetailReportResponseModel.model_validate(ret)


class GetAgentErrorDetailReportModel(ReportWindow):
    agentName: AgentName


class AgentErrorDetailReportResponseModel(BaseResponseModel):
    report: AgentErrorDetailReportModel


@reports_router.post("/getAgentErrorDetailReport", response_model=AgentErrorDetailReportResponseModel, summary="Get an agent's error detail report", description="Report an agent's failures by version, result code and message")
async def getAgentErrorDetailReport(item: GetAgentErrorDetailReportModel, request: Request) -> AgentErrorDetailReportResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return AgentErrorDetailReportResponseModel.model_validate(ret)


class GetAgentCostDetailReportModel(ReportWindow):
    agentName: AgentName


class AgentCostDetailReportResponseModel(BaseResponseModel):
    report: AgentCostDetailReportModel


@reports_router.post("/getAgentCostDetailReport", response_model=AgentCostDetailReportResponseModel, summary="Get an agent's cost detail report", description="Report per-version LLM cost stats and cost trend for an agent")
async def getAgentCostDetailReport(item: GetAgentCostDetailReportModel, request: Request) -> AgentCostDetailReportResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return AgentCostDetailReportResponseModel.model_validate(ret)


class GetUserUsageReportModel(ReportWindow):
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=50, ge=1, le=1_000)
    sortBy: UserUsageSortField = UserUsageSortField.executionCount
    sortDescending: bool = True


class UserUsageReportResponseModel(BaseResponseModel):
    report: UserUsageReportModel


@reports_router.post("/getUserUsageReport", response_model=UserUsageReportResponseModel, summary="Get user usage report", description="Report usage stats for each user, paged and sortable")
async def getUserUsageReport(item: GetUserUsageReportModel, request: Request) -> UserUsageReportResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return UserUsageReportResponseModel.model_validate(ret)


class GetUserDetailReportModel(ReportWindow):
    email: str


class UserDetailReportResponseModel(BaseResponseModel):
    report: UserDetailReportModel


@reports_router.post("/getUserDetailReport", response_model=UserDetailReportResponseModel, summary="Get a user's detail report", description="Report a user's usage, per-agent stats, trend, and errors")
async def getUserDetailReport(item: GetUserDetailReportModel, request: Request) -> UserDetailReportResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return UserDetailReportResponseModel.model_validate(ret)
