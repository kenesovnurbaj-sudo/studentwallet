from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, field_validator

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


class ExpenseCreate(BaseModel):
    amount: Money
    category_id: int
    type: Literal["expense", "income"] = "expense"
    note: str = Field(default="", max_length=255)
    spent_at: date = Field(default_factory=today)
    source: Literal["web", "siri"] = "web"

    @field_validator("spent_at")
    @classmethod
    def date_not_in_future(cls, value: date | None) -> date | None:
        return _not_in_future(value)


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
    limit_amount: Money
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
