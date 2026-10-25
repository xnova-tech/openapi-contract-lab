"""Typed request and response models."""

from enum import StrEnum

from pydantic import BaseModel, Field


class OrderStatus(StrEnum):
    NEW = "new"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class CreateOrder(BaseModel):
    external_id: str = Field(min_length=1)
    quantity: int = Field(gt=0, strict=True)


class ChangeStatus(BaseModel):
    status: OrderStatus


class Order(BaseModel):
    id: int
    external_id: str
    quantity: int
    status: OrderStatus


class ErrorBody(BaseModel):
    code: str
    message: str
