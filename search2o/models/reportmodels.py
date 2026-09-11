# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from enum import StrEnum

from pydantic import BaseModel, Field


class TrendInterval(StrEnum):
    hourly = "hourly"
    daily = "daily"


class AgentPerformanceTrendBucket(BaseModel):
    bucketStart: int = Field(..., title="Bucket start", description="Start of this bucket, in epoch milliseconds.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    failureCount: int = Field(default=0, title="Failures", description="Number of executions that ended in an error.")
    averageDuration: int = Field(default=0, title="Average duration", description="Mean execution time, in milliseconds.")
    p95Duration: int = Field(default=0, title="95th percentile duration", description="The time within which 95% of executions finished, in milliseconds.")
    distinctAgents: int = Field(default=0, description="Number of different agents executed.", title="Distinct agents")


class AgentPerformanceRow(BaseModel):
    agentName: str = Field(..., title="Agent name", description="The name of the agent.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    uniqueUsers: int = Field(default=0, title="Unique users", description="Number of different users.")
    successCount: int = Field(default=0, title="Successes", description="Number of executions that completed successfully.")
    failureCount: int = Field(default=0, title="Failures", description="Number of executions that ended in an error.")
    successRate: float = Field(default=0, description="Successful executions as a fraction of all executions.", title="Success rate")
    averageDuration: int = Field(default=0, title="Average duration", description="Mean execution time, in milliseconds.")
    p95Duration: int = Field(default=0, title="95th percentile duration", description="The time within which 95% of executions finished, in milliseconds.")
    lastExecutedAt: int = Field(default=0, title="Last executed", description="When the last execution happened, in epoch milliseconds.")


class AgentPerformanceReportModel(BaseModel):
    start: int = Field(..., title="Window start", description="Start of the reporting window, in epoch milliseconds.")
    end: int = Field(..., title="Window end", description="End of the reporting window, in epoch milliseconds.")
    trendInterval: TrendInterval = Field(..., title="Trend interval", description="Whether the trend buckets are hourly or daily. Windows of 48 hours or less are hourly.")
    bucketMs: int = Field(description="The length of each trend bucket, in milliseconds.", title="Bucket size")
    agents: list[AgentPerformanceRow] = Field(..., title="Agents", description="One row per agent.")
    trend: list[AgentPerformanceTrendBucket] = Field(default=[], title="Trend", description="Activity over the window, one entry per bucket.")


class AgentErrorsTrendBucket(BaseModel):
    bucketStart: int = Field(..., title="Bucket start", description="Start of this bucket, in epoch milliseconds.")
    errorCount: int = Field(default=0, title="Errors", description="Number of executions that ended in an error.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    uniqueUsers: int = Field(default=0, title="Unique users", description="Number of different users who hit an error.")
    distinctAgents: int = Field(default=0, title="Agents with errors", description="Number of different agents that had at least one error.")


class AgentErrorsRow(BaseModel):
    agentName: str = Field(..., title="Agent name", description="The name of the agent.")
    errorCount: int = Field(default=0, title="Errors", description="Number of executions that ended in an error.")
    executionCount: int = Field(default=0, title="Executions", description="Total executions in the window, errors included.")
    errorRate: float = Field(default=0, title="Error rate", description="Failed executions as a fraction of all executions.")
    uniqueUsers: int = Field(default=0, title="Users affected", description="Number of different users who hit an error.")
    distinctMessages: int = Field(default=0, title="Distinct messages", description="Number of different error messages.")
    firstOccurredAt: int = Field(default=0, title="First error", description="When the first error happened, in epoch milliseconds.")
    lastOccurredAt: int = Field(default=0, title="Last error", description="When the last error happened, in epoch milliseconds.")
    counts: dict[str, int] = Field(default_factory=dict, title="Failures by result code", description="How many times this agent failed with each result code. Only codes that occurred are present; successful codes are never included.")


class AgentErrorsReportModel(BaseModel):
    start: int = Field(..., title="Window start", description="Start of the reporting window, in epoch milliseconds.")
    end: int = Field(..., title="Window end", description="End of the reporting window, in epoch milliseconds.")
    trendInterval: TrendInterval = Field(..., title="Trend interval", description="Whether the trend buckets are hourly or daily. Windows of 48 hours or less are hourly.")
    bucketMs: int = Field(description="The length of each trend bucket, in milliseconds.", title="Bucket size")
    errorCount: int = Field(default=0, title="Errors", description="Total errors across every agent in the window.")
    agents: list[AgentErrorsRow] = Field(..., title="Agents", description="One row per agent that had at least one error. Open a row for that agent's error detail.")
    trend: list[AgentErrorsTrendBucket] = Field(default=[], title="Trend", description="Errors over the window, one entry per bucket.")


class AgentCostTrendBucket(BaseModel):
    bucketStart: int = Field(..., title="Bucket start", description="Start of this bucket, in epoch milliseconds.")
    totalLlmCost: float = Field(default=0, title="Total LLM cost", description="Total spend on LLM calls, in dollars.")
    averageLlmCost: float = Field(default=0, title="Average LLM cost", description="Mean LLM spend per execution, in dollars.")
    p95LlmCost: float = Field(default=0, title="95th percentile LLM cost", description="The cost below which 95% of executions fell, in dollars.")


class AgentCostRow(BaseModel):
    agentName: str = Field(..., title="Agent name", description="The name of the agent.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    uniqueUsers: int = Field(default=0, title="Unique users", description="Number of different users.")
    totalLlmCost: float = Field(default=0, title="Total LLM cost", description="Total spend on LLM calls, in dollars.")
    averageLlmCost: float = Field(default=0, title="Average LLM cost", description="Mean LLM spend per execution, in dollars.")
    maximumLlmCost: float = Field(default=0, title="Maximum LLM cost", description="The most any single execution spent, in dollars.")
    lastExecutedAt: int = Field(default=0, title="Last executed", description="When the last execution happened, in epoch milliseconds.")


class AgentCostReportModel(BaseModel):
    start: int = Field(..., title="Window start", description="Start of the reporting window, in epoch milliseconds.")
    end: int = Field(..., title="Window end", description="End of the reporting window, in epoch milliseconds.")
    trendInterval: TrendInterval = Field(..., title="Trend interval", description="Whether the trend buckets are hourly or daily. Windows of 48 hours or less are hourly.")
    bucketMs: int = Field(description="The length of each trend bucket, in milliseconds.", title="Bucket size")
    agents: list[AgentCostRow] = Field(..., title="Agents", description="One row per agent.")
    trend: list[AgentCostTrendBucket] = Field(default=[], title="Trend", description="Activity over the window, one entry per bucket.")


class UserUsageSortField(StrEnum):
    executionCount = "executionCount"
    distinctAgentsUsed = "distinctAgentsUsed"
    successCount = "successCount"
    failureCount = "failureCount"
    successRate = "successRate"
    totalLlmCost = "totalLlmCost"
    lastExecutedAt = "lastExecutedAt"


class UserUsageTrendBucket(BaseModel):
    bucketStart: int = Field(..., title="Bucket start", description="Start of this bucket, in epoch milliseconds.")
    userCount: int = Field(default=0, description="Number of users active in this bucket.", title="Users")
    totalDuration: int = Field(default=0, description="Total execution time, in milliseconds.", title="Total duration")


class UserUsageRow(BaseModel):
    userEmail: str = Field(..., title="User email", description="The user's email address.")
    userName: str = Field(..., title="User name", description="The user's name.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    distinctAgentsUsed: int = Field(default=0, title="Distinct agents used", description="Number of different agents this user ran.")
    successCount: int = Field(default=0, title="Successes", description="Number of executions that completed successfully.")
    failureCount: int = Field(default=0, title="Failures", description="Number of executions that ended in an error.")
    successRate: float = Field(default=0, description="Successful executions as a fraction of all executions.", title="Success rate")
    totalLlmCost: float = Field(default=0, title="Total LLM cost", description="Total spend on LLM calls, in dollars.")
    lastExecutedAt: int = Field(default=0, title="Last executed", description="When the last execution happened, in epoch milliseconds.")


class UserUsageReportModel(BaseModel):
    start: int = Field(..., title="Window start", description="Start of the reporting window, in epoch milliseconds.")
    end: int = Field(..., title="Window end", description="End of the reporting window, in epoch milliseconds.")
    page: int = Field(..., title="Page", description="The page of results returned, starting at 1.")
    pageSize: int = Field(..., title="Page size", description="The number of rows per page.")
    totalRows: int = Field(..., title="Total rows", description="The number of rows across all pages.")
    totalPages: int = Field(..., title="Total pages", description="The number of pages available.")
    trendInterval: TrendInterval = Field(..., title="Trend interval", description="Whether the trend buckets are hourly or daily. Windows of 48 hours or less are hourly.")
    bucketMs: int = Field(description="The length of each trend bucket, in milliseconds.", title="Bucket size")
    users: list[UserUsageRow] = Field(..., title="Users", description="One row per user.")
    trend: list[UserUsageTrendBucket] = Field(default=[], description="Activity over the window, one entry per bucket.", title="Trend")


class ErrorMessageGroup(BaseModel):
    errorMessage: str = Field(..., title="Error message", description="The error text that was reported.")
    path: str = Field(default="", title="Path", description="Where in the agent the error happened. The same message from two different paths is reported separately.")
    occurrenceCount: int = Field(default=0, title="Occurrences", description="How many times this message occurred.")
    uniqueUsers: int = Field(default=0, title="Unique users", description="Number of different users.")
    firstOccurredAt: int = Field(default=0, title="First occurred", description="When this error first occurred, in epoch milliseconds.")
    lastOccurredAt: int = Field(default=0, title="Last occurred", description="When this error last occurred, in epoch milliseconds.")


class VersionErrorGroup(BaseModel):
    resultCode: str = Field(..., title="Result code", description="How the execution ended.")
    errorCount: int = Field(default=0, title="Errors", description="Number of executions that ended with this result code.")
    uniqueUsers: int = Field(default=0, title="Unique users", description="Number of different users.")
    firstOccurredAt: int = Field(default=0, title="First occurred", description="When this error first occurred, in epoch milliseconds.")
    lastOccurredAt: int = Field(default=0, title="Last occurred", description="When this error last occurred, in epoch milliseconds.")
    distinctMessages: int = Field(default=0, description="Number of different error messages under this result code.", title="Distinct messages")
    messages: list[ErrorMessageGroup] = Field(default=[], title="Messages", description="The error messages grouped under this result code.")


class AgentErrorVersionRow(BaseModel):
    agentVersion: int = Field(..., title="Agent version", description="The published version of the agent, as an epoch millisecond timestamp.")
    errorCount: int = Field(default=0, title="Errors", description="Number of failed executions on this version.")
    errors: list[VersionErrorGroup] = Field(default=[], title="Errors", description="Failures grouped by result code.")


class AgentErrorDetailReportModel(BaseModel):
    agentName: str = Field(..., title="Agent name", description="The agent this report covers.")
    start: int = Field(..., title="Window start", description="Start of the reporting window, in epoch milliseconds.")
    end: int = Field(..., title="Window end", description="End of the reporting window, in epoch milliseconds.")
    errorCount: int = Field(default=0, title="Errors", description="Total failures across every version in the window.")
    versions: list[AgentErrorVersionRow] = Field(..., title="Versions", description="One entry per published version that had at least one failure, newest first.")


class AgentDetailTrendBucket(BaseModel):
    bucketStart: int = Field(..., title="Bucket start", description="Start of this bucket, in epoch milliseconds.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    averageDuration: int = Field(default=0, title="Average duration", description="Mean execution time, in milliseconds.")
    p95Duration: int = Field(default=0, title="95th percentile duration", description="The time within which 95% of executions finished, in milliseconds.")
    uniqueUsers: int = Field(default=0, title="Unique users", description="Number of different users.")


class AgentVersionDetailRow(BaseModel):
    agentVersion: int = Field(..., title="Agent version", description="The published version of the agent, as an epoch millisecond timestamp.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    uniqueUsers: int = Field(default=0, title="Unique users", description="Number of different users.")
    successCount: int = Field(default=0, title="Successes", description="Number of executions that completed successfully.")
    failureCount: int = Field(default=0, title="Failures", description="Number of executions that ended in an error.")
    successRate: float = Field(default=0, description="Successful executions as a fraction of all executions.", title="Success rate")
    averageDuration: int = Field(default=0, title="Average duration", description="Mean execution time, in milliseconds.")
    p95Duration: int = Field(default=0, title="95th percentile duration", description="The time within which 95% of executions finished, in milliseconds.")
    totalLlmCost: float = Field(default=0, title="Total LLM cost", description="Total spend on LLM calls, in dollars.")
    averageLlmCost: float = Field(default=0, title="Average LLM cost", description="Mean LLM spend per execution, in dollars.")
    firstExecutedAt: int = Field(default=0, title="First executed", description="When the first execution happened, in epoch milliseconds.")
    lastExecutedAt: int = Field(default=0, title="Last executed", description="When the last execution happened, in epoch milliseconds.")


class AgentDetailReportModel(BaseModel):
    agentName: str = Field(..., title="Agent name", description="The agent this report covers.")
    start: int = Field(..., title="Window start", description="Start of the reporting window, in epoch milliseconds.")
    end: int = Field(..., title="Window end", description="End of the reporting window, in epoch milliseconds.")
    trendInterval: TrendInterval = Field(..., title="Trend interval", description="Whether the trend buckets are hourly or daily. Windows of 48 hours or less are hourly.")
    bucketMs: int = Field(description="The length of each trend bucket, in milliseconds.", title="Bucket size")
    versions: list[AgentVersionDetailRow] = Field(..., title="Versions", description="One row per published version of the agent.")
    trend: list[AgentDetailTrendBucket] = Field(default=[], description="Activity over the window, one entry per bucket.", title="Trend")


class UserAgentUsageRow(BaseModel):
    agentName: str = Field(..., title="Agent name", description="The agent this user ran.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    successCount: int = Field(default=0, title="Successes", description="Number of executions that completed successfully.")
    failureCount: int = Field(default=0, title="Failures", description="Number of executions that ended in an error.")
    successRate: float = Field(default=0, description="Successful executions as a fraction of all executions.", title="Success rate")
    totalLlmCost: float = Field(default=0, title="Total LLM cost", description="Total spend on LLM calls, in dollars.")
    averageDuration: int = Field(default=0, title="Average duration", description="Mean execution time, in milliseconds.")
    lastExecutedAt: int = Field(default=0, title="Last executed", description="When the last execution happened, in epoch milliseconds.")


class UsageTrendBucket(BaseModel):
    bucketStart: int = Field(..., title="Bucket start", description="Start of this bucket, in epoch milliseconds.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    successCount: int = Field(default=0, title="Successes", description="Number of executions that completed successfully.")
    failureCount: int = Field(default=0, title="Failures", description="Number of executions that ended in an error.")
    llmCost: float = Field(default=0, title="LLM cost", description="LLM spend in this bucket, in dollars.")
    distinctAgents: int = Field(default=0, description="Number of different agents executed.", title="Distinct agents")
    totalDuration: int = Field(default=0, description="Total execution time, in milliseconds.", title="Total duration")


class UserErrorRow(BaseModel):
    resultCode: str = Field(..., title="Result code", description="How the execution ended.")
    errorCount: int = Field(default=0, title="Errors", description="Number of executions that ended with this result code.")
    lastOccurredAt: int = Field(default=0, title="Last occurred", description="When this error last occurred, in epoch milliseconds.")


class UserDetailReportModel(BaseModel):
    userEmail: str = Field(..., title="User email", description="The user this report covers.")
    userName: str = Field(..., title="User name", description="The name of the user this report covers.")
    start: int = Field(..., title="Window start", description="Start of the reporting window, in epoch milliseconds.")
    end: int = Field(..., title="Window end", description="End of the reporting window, in epoch milliseconds.")
    trendInterval: TrendInterval = Field(..., title="Trend interval", description="Whether the trend buckets are hourly or daily. Windows of 48 hours or less are hourly.")
    bucketMs: int = Field(description="The length of each trend bucket, in milliseconds.", title="Bucket size")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    distinctAgentsUsed: int = Field(default=0, title="Distinct agents used", description="Number of different agents this user ran.")
    successCount: int = Field(default=0, title="Successes", description="Number of executions that completed successfully.")
    failureCount: int = Field(default=0, title="Failures", description="Number of executions that ended in an error.")
    successRate: float = Field(default=0, title="Success rate", description="Successful executions as a fraction of all executions.")
    totalLlmCost: float = Field(default=0, title="Total LLM cost", description="Total spend on LLM calls, in dollars.")
    averageDuration: int = Field(default=0, title="Average duration", description="Mean execution time, in milliseconds.")
    activeDays: int = Field(default=0, description="Number of distinct days on which this user ran an agent.", title="Active days")
    firstExecutedAt: int = Field(default=0, title="First executed", description="When the first execution happened, in epoch milliseconds.")
    lastExecutedAt: int = Field(default=0, title="Last executed", description="When the last execution happened, in epoch milliseconds.")
    agents: list[UserAgentUsageRow] = Field(default=[], title="Agents", description="One row per agent this user ran.")
    trend: list[UsageTrendBucket] = Field(default=[], title="Trend", description="Activity over the window, one entry per bucket.")
    errors: list[UserErrorRow] = Field(default=[], title="Errors", description="Failures grouped by result code.")


class CostTrendBucket(BaseModel):
    bucketStart: int = Field(..., title="Bucket start", description="Start of this bucket, in epoch milliseconds.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    llmCost: float = Field(default=0, title="LLM cost", description="LLM spend in this bucket, in dollars.")
    averageLlmCost: float = Field(default=0, title="Average LLM cost", description="Mean LLM spend per execution, in dollars.")
    p95LlmCost: float = Field(default=0, title="95th percentile LLM cost", description="The cost below which 95% of executions fell, in dollars.")


class AgentCostVersionRow(BaseModel):
    agentVersion: int = Field(..., title="Agent version", description="The published version of the agent, as an epoch millisecond timestamp.")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    uniqueUsers: int = Field(default=0, title="Unique users", description="Number of different users.")
    totalLlmCost: float = Field(default=0, title="Total LLM cost", description="Total spend on LLM calls, in dollars.")
    averageLlmCost: float = Field(default=0, title="Average LLM cost", description="Mean LLM spend per execution, in dollars.")
    maximumLlmCost: float = Field(default=0, title="Maximum LLM cost", description="The most any single execution spent, in dollars.")
    firstExecutedAt: int = Field(default=0, title="First executed", description="When the first execution happened, in epoch milliseconds.")
    lastExecutedAt: int = Field(default=0, title="Last executed", description="When the last execution happened, in epoch milliseconds.")
    trend: list[CostTrendBucket] = Field(default=[], title="Trend", description="Cost over the window for this version, one entry per bucket.")


class AgentCostDetailReportModel(BaseModel):
    agentName: str = Field(..., title="Agent name", description="The agent this report covers.")
    start: int = Field(..., title="Window start", description="Start of the reporting window, in epoch milliseconds.")
    end: int = Field(..., title="Window end", description="End of the reporting window, in epoch milliseconds.")
    trendInterval: TrendInterval = Field(..., title="Trend interval", description="Whether the trend buckets are hourly or daily. Windows of 48 hours or less are hourly.")
    bucketMs: int = Field(description="The length of each trend bucket, in milliseconds.", title="Bucket size")
    executionCount: int = Field(default=0, title="Executions", description="Number of agent executions.")
    uniqueUsers: int = Field(default=0, title="Unique users", description="Number of different users.")
    totalLlmCost: float = Field(default=0, title="Total LLM cost", description="Total spend on LLM calls, in dollars.")
    averageLlmCost: float = Field(default=0, title="Average LLM cost", description="Mean LLM spend per execution, in dollars.")
    maximumLlmCost: float = Field(default=0, title="Maximum LLM cost", description="The most any single execution spent, in dollars.")
    firstExecutedAt: int = Field(default=0, title="First executed", description="When the first execution happened, in epoch milliseconds.")
    lastExecutedAt: int = Field(default=0, title="Last executed", description="When the last execution happened, in epoch milliseconds.")
    trend: list[CostTrendBucket] = Field(default=[], title="Trend", description="Activity over the window, one entry per bucket.")
    versions: list[AgentCostVersionRow] = Field(default=[], title="Versions", description="One row per published version of the agent.")
