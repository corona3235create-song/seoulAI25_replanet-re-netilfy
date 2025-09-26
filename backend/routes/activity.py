# backend/routes/activity.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime
from .. import database, models
from ..dependencies import get_current_user
from ..services.mobility_service import MobilityService
from .. import schemas

router = APIRouter(prefix="/activity", tags=["activity"])

# 📌 활동 기록 요청 스키마
class ActivityLogRequest(BaseModel):
    user_id: int
    activity_type: str  # "subway", "bike", "bus", "walk"
    distance_km: float = 0.0
    description: str = ""
    start_point: str | None = None
    end_point: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None

# 📌 활동 타입별 설정
ACTIVITY_CONFIG = {
    "subway": {
        "co2_saved_per_km": 151,  # g CO2/km 절약
        "points_per_km": 20,      # 포인트/km
        "name": "지하철"
    },
    "bike": {
        "co2_saved_per_km": 80,   # g CO2/km 절약
        "points_per_km": 25,      # 포인트/km
        "name": "자전거"
    },
    "bus": {
        "co2_saved_per_km": 87,   # g CO2/km 절약
        "points_per_km": 15,      # 포인트/km
        "name": "버스"
    },
    "walk": {
        "co2_saved_per_km": 80,   # g CO2/km 절약 (자동차 대비)
        "points_per_km": 30,      # 포인트/km
        "name": "도보"
    }
}


# 💡 request 대신 current_user를 받도록 시그니처 수정
def log_activity(
    request: ActivityLogRequest, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    활동 기록 API
    - 교통수단별 CO2 절약량과 포인트 계산
    - mobility_logs 테이블에 기록
    - 챌린지 진행률 자동 업데이트
    - 업데이트된 대시보드 데이터 반환
    """
    
    # 💡 요청의 user_id 대신, 로그인 토큰에서 가져온 user_id를 사용 (보안 강화)
    user_id = current_user.user_id

    # 활동 타입 검증
    if request.activity_type not in ACTIVITY_CONFIG:
        raise HTTPException(status_code=400, detail="지원하지 않는 활동 타입입니다.")
    
    # Create a MobilityLogCreate object
    log_data = schemas.MobilityLogCreate(
        mode=schemas.TransportMode(request.activity_type),
        distance_km=request.distance_km,
        description=request.description,
        start_point=request.start_point,
        end_point=request.end_point,
        started_at=request.started_at or datetime.now(),
        ended_at=request.ended_at or datetime.now(),
    )

    try:
        # Log the mobility activity using the service
        MobilityService.log_mobility(db, log_data, current_user)

        # 업데이트된 대시보드 데이터 반환
        return get_updated_dashboard_data(user_id, db) # 💡 토큰에서 가져온 user_id 사용
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"활동 기록 중 오류가 발생했습니다: {str(e)}")

def get_updated_dashboard_data(user_id: int, db: Session) -> Dict[str, Any]:
    """업데이트된 대시보드 데이터 반환"""
    
    # 오늘 절약량
    today_query = """
        SELECT IFNULL(SUM(co2_saved_g), 0) AS saved_today
        FROM mobility_logs
        WHERE user_id = :user_id AND DATE(created_at) = CURDATE()
    """
    today_row = db.execute(today_query, {"user_id": user_id}).fetchone()
    co2_saved_today = float(today_row[0]) if today_row else 0.0
    
    # 누적 절약량
    total_query = """
        SELECT IFNULL(SUM(co2_saved_g), 0) AS total_saved
        FROM mobility_logs
        WHERE user_id = :user_id
    """
    total_row = db.execute(total_query, {"user_id": user_id}).fetchone()
    total_saved = float(total_row[0]) if total_row else 0.0
    
    # 누적 포인트
    points_query = """
        SELECT IFNULL(SUM(points_earned), 0) AS total_points
        FROM mobility_logs
        WHERE user_id = :user_id
    """
    points_row = db.execute(points_query, {"user_id": user_id}).fetchone()
    total_points = int(points_row[0]) if points_row else 0
    
    # 최근 7일 절감량
    daily_query = """
        SELECT DATE(created_at) AS ymd, SUM(co2_saved_g) AS saved_g
        FROM mobility_logs
        WHERE user_id = :user_id
          AND created_at >= CURDATE() - INTERVAL 7 DAY
        GROUP BY DATE(created_at)
        ORDER BY ymd ASC
    """
    daily_rows = db.execute(daily_query, {"user_id": user_id}).fetchall()
    last7days = [{"date": str(row[0]), "saved_g": float(row[1])} for row in daily_rows]
    
    # 교통수단별 절감 비율
    mode_query = """
        SELECT mode, SUM(co2_saved_g) AS saved_g
        FROM mobility_logs
        WHERE user_id = :user_id
        GROUP BY mode
    """
    mode_rows = db.execute(mode_query, {"user_id": user_id}).fetchall()
    modeStats = [{"mode": row[0], "saved_g": float(row[1])} for row in mode_rows]
    
    # 정원 레벨 계산 (100g당 레벨 1)
    garden_level = int(total_saved // 100)
    
    # 오늘 획득 포인트
    today_points_query = """
        SELECT IFNULL(SUM(points_earned), 0) AS today_points
        FROM mobility_logs
        WHERE user_id = :user_id AND DATE(created_at) = CURDATE()
    """
    today_points_row = db.execute(today_points_query, {"user_id": user_id}).fetchone()
    eco_credits_earned = int(today_points_row[0]) if today_points_row else 0
    
    # 챌린지 진행 상황
    challenge = {
        "goal": 100,  # 100kg 목표
        "progress": total_saved / 1000  # g → kg 변환
    }
    
    return {
        "user_id": user_id,
        "co2_saved_today": co2_saved_today,
        "eco_credits_earned": eco_credits_earned,
        "garden_level": garden_level,
        "total_saved": total_saved / 1000,  # g → kg 변환
        "total_points": total_points,
        "last7days": last7days,
        "modeStats": modeStats,
        "challenge": challenge
    }

@router.get("/types")
def get_activity_types() -> Dict[str, Any]:
    """지원하는 활동 타입 목록 반환"""
    return {
        "activity_types": list(ACTIVITY_CONFIG.keys()),
        "configs": ACTIVITY_CONFIG
    }
