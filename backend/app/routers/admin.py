from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import User
from ..routers.auth import user_out
from ..schemas import UserOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.query(User).order_by(User.id).all()]


@router.patch("/users/{user_id}/block", response_model=UserOut)
def set_blocked(
    user_id: int,
    blocked: bool = True,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    user.is_blocked = blocked
    db.commit()
    db.refresh(user)
    return user_out(user)
