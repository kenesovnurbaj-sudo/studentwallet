from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


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


class SplitItem(BaseModel):
    """Позиция из чека: что заказали, сколько стоит и кто это ел."""

    name: str = Field(default="", max_length=80)
    price: float = Field(gt=0)
    eaters: list[str] = Field(min_length=1, max_length=21)  # "me" или email друга


class SplitParticipant(BaseModel):
    email: EmailStr
    amount: float | None = Field(default=None, gt=0)  # нужна только в режиме custom


class SplitIn(BaseModel):
    mode: Literal["equal", "custom", "items"]
    participants: list[SplitParticipant] = Field(min_length=1, max_length=20)  # только друзья
    items: list[SplitItem] = Field(default_factory=list, max_length=50)
    tip_percent: float = Field(default=0, ge=0, le=100)  # обслуживание, % к чеку


def _amount_required(amount: float | None, split: "SplitIn | None") -> None:
    # В режиме «по блюдам» сумма считается из позиций, в остальных случаях она обязательна.
    if amount is None and (split is None or split.mode != "items"):
        raise ValueError("amount is required")


class ExpenseCreate(BaseModel):
    amount: float | None = Field(default=None, gt=0)  # при делении счёта это весь чек
    category_id: int
    type: Literal["expense", "income"] = "expense"
    note: str = Field(default="", max_length=255)
    spent_at: date = Field(default_factory=date.today)
    source: Literal["web", "siri"] = "web"
    split: SplitIn | None = None  # если указано, вы заплатили за друзей

    @model_validator(mode="after")
    def _check_amount(self):
        _amount_required(self.amount, self.split)
        return self


class SplitPreviewIn(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    split: SplitIn

    @model_validator(mode="after")
    def _check_amount(self):
        _amount_required(self.amount, self.split)
        return self


class SplitLine(BaseModel):
    email: str
    name: str
    amount: float
    found: bool  # есть ли друг среди пользователей сайта


class SplitPreviewOut(BaseModel):
    total: float
    service: float = 0  # сколько из total составляет обслуживание
    my_share: float
    lines: list[SplitLine]


class ExpenseUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    category_id: int | None = None
    type: Literal["expense", "income"] | None = None
    note: str | None = Field(default=None, max_length=255)
    spent_at: date | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: float
    category_id: int
    type: str
    note: str
    spent_at: date
    source: str
    paid_total: float | None = None  # весь чек, если вы платили за друзей (amount тогда ваша доля)


class UserBrief(BaseModel):
    id: int
    name: str
    email: str


class ShareOut(BaseModel):
    id: int
    amount: float
    status: Literal["pending", "marked_paid", "settled"]
    note: str  # описание траты
    spent_at: date  # дата траты
    paid_total: float | None
    payer: UserBrief
    debtor: UserBrief
    created_at: datetime
    marked_at: datetime | None
    settled_at: datetime | None


class MarkPaidIn(BaseModel):
    category_id: int  # в какую категорию записать этот расход в вашем бюджете


class DebtSummary(BaseModel):
    owed_to_me: float  # сколько друзья ещё должны вам
    i_owe: float  # сколько должны вы
    to_confirm: int  # сколько возвратов ждут вашего подтверждения


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


class BudgetSummary(BaseModel):
    month: str
    limit: float
    spent: float
    remaining: float
    percent_used: float
    days_left: int
    daily_limit: float
