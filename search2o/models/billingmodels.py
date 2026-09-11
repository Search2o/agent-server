# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from enum import StrEnum, auto

from pydantic import BaseModel, Field, model_validator

from .schemaobjects import ServiceLevel


class InvoiceStatus(StrEnum):
    draft = auto()
    open = auto()
    paid = auto()
    pastDue = "pastDue"
    uncollectible = auto()
    void = auto()


class Discount(BaseModel):
    description: str = Field(max_length=200)
    percentOff: float | None = None
    amountOff: float | None = None        # dollars

    @model_validator(mode="after")
    def validate_discount(self) -> "Discount":
        if (self.percentOff is None) == (self.amountOff is None):
            raise ValueError("Exactly one of percentOff or amountOff must be specified")

        if self.percentOff is not None and not 0 < self.percentOff <= 100:
            raise ValueError("percentOff must be greater than 0 and at most 100")

        if self.amountOff is not None and self.amountOff <= 0:
            raise ValueError("amountOff must be greater than 0")

        return self


class RowKind(StrEnum):
    item = auto()
    subtotal = auto()
    total = auto()
    credit = auto()
    note = auto()
    heading = auto()


class InvoiceRow(BaseModel):
    kind: RowKind
    label: str
    detail: str = ""
    amount: str = ""
    indent: int = Field(default=0, ge=0)


class Invoice(BaseModel):
    heading: str
    currency: str
    billingName: str = ""
    rows: list[InvoiceRow]

    periodStart: int
    periodEnd: int

    serviceLevel: ServiceLevel | None = None
    pastPeriods: list[int] = Field(default_factory=list)
    invoiceId: str | None = None
    status: InvoiceStatus | None = None
    finalizedAt: int | None = None
