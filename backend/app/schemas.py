from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    currency: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    icon: str = Field(default="", max_length=16)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    icon: str
    user_id: int | None


class ExpenseCreate(BaseModel):
    amount: float = Field(gt=0)
    category_id: int
    type: Literal["expense", "income"] = "expense"
    note: str = Field(default="", max_length=255)
    spent_at: date = Field(default_factory=date.today)
    source: Literal["web", "siri"] = "web"


class ExpenseUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    category_id: int | None = None
    type: Literal["expense", "income"] | None = None
    note: str | None = Field(default=None, max_length=255)
    spent_at: date | None = None


class BulkCategoryChange(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=1000)
    category_id: int


class BulkCategoryResult(BaseModel):
    updated: int


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: float
    category_id: int
    type: str
    note: str
    spent_at: date
    source: str


class BudgetSet(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    limit_amount: float = Field(gt=0)
    category_id: int | None = None  # None = общий лимит


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    month: str
    limit_amount: float
    category_id: int | None


class SplitItemIn(BaseModel):
    category_id: int
    limit_amount: float = Field(gt=0)


class BudgetSplitSet(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    items: list[SplitItemIn] = Field(min_length=1, max_length=30)


class BudgetSplitSaved(BaseModel):
    saved: int


class BudgetSummary(BaseModel):
    month: str
    limit: float
    spent: float
    remaining: float
    percent_used: float
    days_left: int
    daily_limit: float
