# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from typing import Any

from fastapi import APIRouter, Request
from pydantic import EmailStr, Field

from search2o.common.rest_call import RestCall
from search2o.models.apimodels import BaseResponseModel, EmptyRequestModel, RequestModel
from search2o.models.billingmodels import Invoice
from search2o.models.schemaobjects import ServiceLevel

owner_router = APIRouter(prefix="/api/owner", tags=["owner"])


class InvoiceResponseModel(BaseResponseModel):
    invoice: Invoice | None = Field(default=None, title="Invoice", description="The invoice as an ordered list of rows to display, plus the fields a client acts on.")

class PastInvoiceModel(RequestModel):
    periodStart: int = Field(..., ge=0, title="Period start", description="The billing period to fetch, as one of the values getCurrentInvoice returned in pastPeriods.")


@owner_router.post("/getCurrentInvoice", response_model=InvoiceResponseModel,
                   summary="Get the current invoice",
                   description="The invoice for the billing period in progress, as rows to display, with the past periods that can be fetched with getPastInvoice.")
async def getCurrentInvoice(item: EmptyRequestModel, request: Request) -> InvoiceResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return InvoiceResponseModel.model_validate(ret)


@owner_router.post("/getPastInvoice", response_model=InvoiceResponseModel,
                   summary="Get a past invoice",
                   description="A finalized invoice for a past billing period, identified by a periodStart from getCurrentInvoice's pastPeriods.")
async def getPastInvoice(item: PastInvoiceModel, request: Request) -> InvoiceResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return InvoiceResponseModel.model_validate(ret)


class AccountModel(BaseResponseModel):
    accountName: str = Field(default="", description="Name of this account. The UI may show a previous name until the agent server is restarted.")
    billingEmail: str | None = Field(default=None, title="Billing email", description="Where invoices and billing notices for this account are sent.")
    accountContactEmail: str | None = Field(default=None, title="Account contact email", description="Who Search2o contacts about this account.")
    billingName: str | None = Field(default=None, title="Billing name", description="The name the payment provider knows this account by. Set when the account is registered and not changed here.")
    serviceLevel: ServiceLevel = Field(default=ServiceLevel.individual, title="Service level", description="What this account is entitled to. It is set by Search2o and cannot be changed here.")
    upgradePending: bool = Field(default=False, title="Upgrade pending", description="True from the moment an upgrade is requested until Search2o has dealt with it.")
    createdAt: int = Field(..., description="Account creation date in epoch milliseconds.", json_schema_extra={"format": "int64"})

@owner_router.post("/getAccount", response_model=AccountModel,
                  summary="Get account details",
                  description="Details of this Search2o account: the account name, the billing and contact emails, and when the account was created.")
async def getAccount(request: Request) -> AccountModel:
    ret = await RestCall.passthrough(request)
    return AccountModel.model_validate(ret)



class UpdateAccountModel(RequestModel):
    accountName: str = Field(..., min_length=3, max_length=32, description="Name of this account. The UI may show a previous name until the agent server is restarted.")
    billingEmail: EmailStr | None = Field(default=None, title="Billing email", description="Where invoices and billing notices for this account are sent. Left unchanged when omitted.")
    accountContactEmail: EmailStr | None = Field(default=None, title="Account contact email", description="Who Search2o contacts about this account. Left unchanged when omitted.")


@owner_router.post("/updateAccount", response_model=BaseResponseModel,
                  summary="Update account details",
                  description="Updates the account name and, when supplied, the billing and account contact emails. An email that is omitted is left as it is.")
async def updateAccount(item:UpdateAccountModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class RequestEvaluationModel(RequestModel):
    data: dict[str, Any] = Field(..., title="Evaluation form answers", description="The answers collected by the evaluation request form, keyed by question. At most 30 entries.")


@owner_router.post("/requestEvaluation", response_model=BaseResponseModel,
                  summary="Request an evaluation plan",
                  description="Asks Search2o for an evaluation plan, sending the answers collected by the request form. Until the request is dealt with, getAccount shows upgradePending as true.")
async def requestEvaluation(item: RequestEvaluationModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


@owner_router.post("/startPaidService", response_model=BaseResponseModel,
                  summary="Start paid service",
                  description="Moves this account onto a paid plan. It takes no parameters: the plan follows from the account's own service level, shown by getAccount.")
async def startPaidService(item: EmptyRequestModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class DeleteAccountModel(RequestModel):
    haveBackedUpData: bool = Field(..., title="Data backed up", description="Must be true to confirm the account's data has been backed up. The account cannot be recovered after deletion.")


@owner_router.post("/deleteAccount", response_model=BaseResponseModel,
                  summary="Delete this account",
                  description="Suspends this account immediately and deletes it in a few days. This cannot be undone, so it requires haveBackedUpData to be true.")
async def deleteAccount(item: DeleteAccountModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)
