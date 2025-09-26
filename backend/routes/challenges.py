# routes/challenges.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from pydantic import BaseModel

from .. import crud, models, schemas
from ..database import get_db
from ..dependencies import get_current_user

# /api/challenges 경로로 설정
router = APIRouter(
    prefix="/api/challenges",
    tags=["Challenges"]
)

# 챌린지 참여 요청을 위한 Pydantic 모델
class ChallengeJoinRequest(BaseModel):
    pass

# 챌린지 완료 요청을 위한 Pydantic 모델
class ChallengeCompleteRequest(BaseModel):
    pass

@router.post("/{challenge_id}/join", response_model=schemas.ChallengeMember)
def join_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    challenge = db.query(models.Challenge).filter(models.Challenge.challenge_id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    existing_member = db.query(models.ChallengeMember).filter(models.ChallengeMember.user_id == current_user.user_id, models.ChallengeMember.challenge_id == challenge_id).first()
    if existing_member:
        raise HTTPException(status_code=400, detail="User already joined this challenge")

    new_member = models.ChallengeMember(user_id=current_user.user_id, challenge_id=challenge_id)
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    return new_member


@router.get("/", response_model=List[schemas.FrontendChallenge])
def get_challenges(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    사용자의 챌린지 목록과 참여 상태를 반환합니다.
    """
    user_id = current_user.user_id
    all_challenges = db.query(models.Challenge).order_by(models.Challenge.challenge_id).all()
    
    result = []
    for c in all_challenges:
        member_entry = db.query(models.ChallengeMember).filter(
            models.ChallengeMember.user_id == user_id,
            models.ChallengeMember.challenge_id == c.challenge_id
        ).first()

        is_joined = False
        is_completed_for_user = False
        progress = 0.0

        if member_entry:
            is_joined = True
            is_completed_for_user = member_entry.is_completed
            progress = crud.calculate_challenge_progress(db, user_id, c)

        result.append({
            "id": c.challenge_id,
            "title": c.title,
            "description": c.description,
            "progress": float(progress),
            "reward": c.reward,
            "is_joined": is_joined,
            "is_completed": is_completed_for_user,
            "status": c.status.value,
            "goal_type": c.goal_type.value,
            "goal_target_value": c.goal_target_value
        })
    return result


@router.get("/{challenge_id}/progress")
def get_challenge_progress(
    challenge_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    특정 챌린지에 대한 현재 사용자의 진행률을 계산하여 반환합니다.
    """
    user_id = current_user.user_id
    
    challenge = db.query(models.Challenge).filter(models.Challenge.challenge_id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    member = db.query(models.ChallengeMember).filter(
        models.ChallengeMember.challenge_id == challenge_id,
        models.ChallengeMember.user_id == user_id
    ).first()

    if not member:
        raise HTTPException(status_code=403, detail="User is not a member of this challenge")

    progress = crud.calculate_challenge_progress(db, user_id, challenge)
    
    return {"progress": progress}


@router.post("/{challenge_id}/complete")
def complete_challenge(
    challenge_id: int,
    request: ChallengeCompleteRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자가 개인 챌린지를 완료로 표시하고, 관련 업적을 생성합니다.
    """
    user_id = current_user.user_id

    challenge = db.query(models.Challenge).filter(models.Challenge.challenge_id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found")

    member_entry = db.query(models.ChallengeMember).filter(
        models.ChallengeMember.challenge_id == challenge_id,
        models.ChallengeMember.user_id == user_id
    ).first()
    if not member_entry:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not a member of this challenge")

    if member_entry.is_completed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge is already completed.")

    current_progress = crud.calculate_challenge_progress(db, user_id, challenge)

    if challenge.completion_type == models.ChallengeCompletionType.AUTO and current_progress < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Challenge not yet 100% completed. Current progress: {current_progress:.1f}%"
        )

    member_entry.is_completed = True
    db.add(member_entry)

    # 업적 생성 로직 추가
    achievement_title = f"{challenge.title} 완료"
    achievement_desc = f"'{challenge.title}' 챌린지를 성공적으로 완료했습니다!"
    
    # 1. 업적이 이미 존재하는지 확인
    existing_achievement = db.query(models.Achievement).filter(models.Achievement.title == achievement_title).first()
    if not existing_achievement:
        # 2. 없으면 새로 생성
        new_achievement = models.Achievement(
            code=f"CHALLENGE_COMPLETE_{challenge.challenge_id}",
            title=achievement_title,
            description=achievement_desc
        )
        db.add(new_achievement)
        db.flush() # 새 achievement의 ID를 얻기 위해 flush
        achievement_id = new_achievement.achievement_id
    else:
        achievement_id = existing_achievement.achievement_id

    # 3. 사용자에게 해당 업적이 이미 부여되었는지 확인
    user_has_achievement = db.query(models.UserAchievement).filter(
        models.UserAchievement.user_id == user_id,
        models.UserAchievement.achievement_id == achievement_id
    ).first()

    if not user_has_achievement:
        # 4. 부여되지 않았다면 새로 부여
        new_user_achievement = models.UserAchievement(
            user_id=user_id,
            achievement_id=achievement_id
        )
        db.add(new_user_achievement)

    if challenge.reward:
        try:
            reward_points = int("".join(filter(str.isdigit, challenge.reward)))
            if reward_points > 0:
                crud.add_credits(db, user_id, reward_points, f"챌린지 '{challenge.title}' 완료 보상")
        except (ValueError, TypeError):
            print(f"Warning: Could not parse reward points from '{challenge.reward}' for challenge {challenge.challenge_id}")

    db.commit()
    db.refresh(member_entry)

    return {"message": f"Challenge '{challenge.title}' completed successfully!", "challenge_id": challenge_id}


@router.get("/achievements", response_model=List[dict])
def get_achievements(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.user_id
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
        is_unlocked = bool(r[3])
        result.append({
            "id": int(r[0]),
            "name": r[1],
            "desc": r[2],
            "date": str(r[3]) if r[3] else None,
            "unlocked": is_unlocked,
            "progress": 100 if is_unlocked else 0,
        })
    return result
