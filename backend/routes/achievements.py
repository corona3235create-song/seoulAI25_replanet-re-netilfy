from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List

from .. import crud, models, schemas
from ..database import get_db
from ..dependencies import get_current_user # Import get_current_user

router = APIRouter(
    prefix="/api/achievements", # Change prefix to include /api
    tags=["Achievements"],
)

@router.get("/", response_model=List[dict]) # Change path to "/" and add response_model
def get_achievements(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)): # Get user from dependency
    user_id = current_user.user_id # Get user_id from current_user
    query = text(
        """
        SELECT a.achievement_id, a.title, a.description, ua.granted_at
        FROM achievements a
        LEFT JOIN user_achievements ua
          ON ua.achievement_id = a.achievement_id AND ua.user_id = :uid
        ORDER BY a.achievement_id
        """
    )
    rows = db.execute(query, {"uid": user_id}).fetchall()
    result = []
    for r in rows:
        is_unlocked = bool(r[3]) # granted_at이 있으면 잠금 해제
        result.append({
            "id": int(r[0]),
            "name": r[1],
            "desc": r[2],
            "date": str(r[3]) if r[3] else None,
            "unlocked": is_unlocked,
            "progress": 100 if is_unlocked else 0,  # 잠금 해제 여부에 따라 100 또는 0
        })
    return result
