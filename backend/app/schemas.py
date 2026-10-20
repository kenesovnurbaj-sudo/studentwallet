from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, field_validator, model_validator

from .clock import today
from .security import BCRYPT_MAX_BYTES, password_too_long

# Деньги: строго больше нуля, не больше 2 знаков после запятой и с верхней границей.
# Раньше был float: 0.001 проходил проверку gt=0, а в Numeric(12, 2) сохранялся как 0.
MAX_AMOUNT = Decimal("100000000")  # 100 млн KZT, с запасом для студенческого бюджета


def _drop_float_noise(value):
    """JS присылает 0.1 + 0.2 как 0.30000000000000004. Такой шум округляем до копеек,
    а настоящие лишние знаки (0.001) оставляем, чтобы их отклонила проверка decimal_places."""
    if isinstance(value, float):
        exact = Decimal(repr(value))
        rounded = round(exact, 2)
        if abs(exact - rounded) < Decimal("1e-9"):
            return rounded
        return exact
    return value


Money = Annotated[
    Decimal,
    BeforeValidator(_drop_float_noise),
    Field(gt=0, le=MAX_AMOUNT, max_digits=12, decimal_places=2),
]


def _not_in_future(value: date | None) -> date | None:
    if value is not None and value > today():
        raise ValueError("Date cannot be in the future")
    return value


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(default="", max_length=120)

    @field_validator("password")
    @classmethod
    def password_rules(cls, value: str) -> str:
        # Требования из User Story 1: минимум 8 символов, хотя бы 1 буква и 1 цифра.
        # Пароль из одних пробелов теперь не пройдёт.
        if password_too_long(value):
            raise ValueError(f"Password is too long (max {BCRYPT_MAX_BYTES} bytes, Cyrillic letters take 2)")
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("Password must contain at least one letter and one digit")
        return value

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


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
    name: str = Field(max_length=60)
    icon: str = Field(default="", max_length=16)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = " ".join(value.split())  # убираем пробелы по краям и двойные пробелы
        if not value:
            raise ValueError("Category name cannot be blank")
        return value


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


GUEST_PREFIX = "name:"


class SplitParticipant(BaseModel):
    """Друг с аккаунтом (email) или гость без аккаунта (имя). Нужно указать что-то одно."""

    email: EmailStr | None = None
    name: str | None = Field(default=None, max_length=60)
    amount: float | None = Field(default=None, gt=0)  # нужна только в режиме custom

    @model_validator(mode="after")
    def _email_or_name(self):
        name = " ".join((self.name or "").split())
        if "@" in name:
            raise ValueError("A guest name cannot contain @. Use the email field for registered friends")
        if (self.email is None) == (not name):
            raise ValueError("Give either an email or a name")
        self.name = name or None
        return self

    @property
    def key(self) -> str:
        """Так участник обозначается в расчётах и в позициях: email или «name:имя»."""
        return self.email.lower() if self.email else GUEST_PREFIX + (self.name or "").lower()


class SplitIn(BaseModel):
    mode: Literal["equal", "custom", "items"]
    participants: list[SplitParticipant] = Field(min_length=1, max_length=20)  # только друзья
    items: list[SplitItem] = Field(default_factory=list, max_length=50)
    tip_percent: float = Field(default=0, ge=0, le=100)  # чаевые, % к чеку
    i_participate: bool = True  # False: вы платили только за других и сами не ели


def _amount_required(amount: float | None, split: "SplitIn | None") -> None:
    # В режиме «по блюдам» сумма считается из позиций, в остальных случаях она обязательна.
    if amount is None and (split is None or split.mode != "items"):
        raise ValueError("amount is required")


class ExpenseCreate(BaseModel):
    amount: Money | None = None  # при делении счёта это весь чек
    category_id: int
    type: Literal["expense", "income"] = "expense"
    note: str = Field(default="", max_length=255)
    spent_at: date = Field(default_factory=today)
    source: Literal["web", "siri"] = "web"
    split: SplitIn | None = None  # если указано, вы заплатили за друзей

    @field_validator("spent_at")
    @classmethod
    def date_not_in_future(cls, value: date | None) -> date | None:
        return _not_in_future(value)

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
    key: str  # email или «name:имя»
    email: str | None
    name: str
    amount: float
    found: bool  # есть ли друг среди пользователей сайта (для гостей всегда True)
    guest: bool = False  # друг без аккаунта


class SplitPreviewOut(BaseModel):
    total: float
    service: float = 0  # сколько из total составляют чаевые
    my_share: float
    lines: list[SplitLine]


class ExpenseUpdate(BaseModel):
    amount: Money | None = None
    category_id: int | None = None
    type: Literal["expense", "income"] | None = None
    note: str | None = Field(default=None, max_length=255)
    spent_at: date | None = None

    @field_validator("spent_at")
    @classmethod
    def date_not_in_future(cls, value: date | None) -> date | None:
        return _not_in_future(value)


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
    debtor: UserBrief | None  # None, если друг без аккаунта
    debtor_name: str  # имя должника: пользователя сайта или гостя
    guest: bool = False
    reminded_at: datetime | None = None
    remind_count: int = 0
    created_at: datetime
    marked_at: datetime | None
    settled_at: datetime | None


class MarkPaidIn(BaseModel):
    category_id: int  # в какую категорию записать этот расход в вашем бюджете


class DebtSummary(BaseModel):
    owed_to_me: float  # сколько друзья ещё должны вам
    i_owe: float  # сколько должны вы
    to_confirm: int  # сколько возвратов ждут вашего подтверждения
    reminded: int = 0  # сколько ваших долгов вам уже напомнили


class BudgetSet(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    limit_amount: Money
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


class CategoryBalance(BaseModel):
    category_id: int
    category: str
    icon: str
    limit: float | None  # None = лимит на категорию не задан
    spent: float
    remaining: float | None
    percent_used: float | None
    status: str  # ok | watch | over | no_limit


class AlertOut(BaseModel):
    code: str
    level: str
    message: str


class ForecastOut(BaseModel):
    month: str
    limit: float
    spent: float
    days_in_month: int
    days_elapsed: int
    daily_average: float | None
    projected_total: float | None
    run_out_date: date | None
    days_early: int | None
    safe_daily_limit: float | None
    level: str
    alerts: list[AlertOut]
