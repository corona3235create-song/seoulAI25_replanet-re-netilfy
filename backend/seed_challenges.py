from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .database import SessionLocal, engine
from . import crud, schemas, models

# Ensure tables are created
models.Base.metadata.create_all(bind=engine)

def seed_challenges(db: Session):

    now = datetime.utcnow()
    # Admin user ID (assuming admin user is created with ID 1)
    admin_user_id = 1 

    challenges_to_create = [
        schemas.ChallengeCreate(
            title="대중교통 이용 챌린지",
            description="이번 주 대중교통으로 5kg CO₂ 절감하기",
            scope=schemas.ChallengeScope.PERSONAL,
            completion_type=schemas.ChallengeCompletionType.AUTO,
            target_mode=schemas.TransportMode.ANY,
            goal_type=schemas.ChallengeGoalType.CO2_SAVED,
            goal_target_value=5000.0, # 5kg
            start_at=now,
            end_at=now + timedelta(days=7),
            reward="에코 크레딧 200P + 뱃지",
            created_by=None
        ),
        schemas.ChallengeCreate(
            title="자전거 출퇴근 챌린지",
            description="한 달간 자전거로 50km 이동하기",
            scope=schemas.ChallengeScope.PERSONAL,
            completion_type=schemas.ChallengeCompletionType.AUTO,
            target_mode=schemas.TransportMode.BIKE,
            goal_type=schemas.ChallengeGoalType.DISTANCE_KM,
            goal_target_value=50.0, # 50km
            start_at=now,
            end_at=now + timedelta(days=30),
            reward="에코 크레딧 150P + 뱃지",
            created_by=None
        ),
        schemas.ChallengeCreate(
            title="도보 생활 챌린지",
            description="일주일간 10km 도보 이동하기",
            scope=schemas.ChallengeScope.PERSONAL,
            completion_type=schemas.ChallengeCompletionType.AUTO,
            target_mode=schemas.TransportMode.WALK,
            goal_type=schemas.ChallengeGoalType.DISTANCE_KM,
            goal_target_value=10.0, # 10km
            start_at=now,
            end_at=now + timedelta(days=7),
            reward="에코 크레딧 100P",
            created_by=None
        ),
        schemas.ChallengeCreate(
            title="친환경 이동 30일",
            description="30일 연속 친환경 교통수단 이용하기 (총 10회 이상)",
            scope=schemas.ChallengeScope.PERSONAL,
            completion_type=schemas.ChallengeCompletionType.AUTO,
            target_mode=schemas.TransportMode.ANY,
            goal_type=schemas.ChallengeGoalType.TRIP_COUNT,
            goal_target_value=10.0, # 10 trips
            start_at=now,
            end_at=now + timedelta(days=30),
            reward="에코 크레딧 300P + 특별 뱃지",
            created_by=None
        )
    ]

    for challenge_data in challenges_to_create:
        existing_challenge = db.query(models.Challenge).filter_by(title=challenge_data.title).first()
        if existing_challenge:
            # Update existing challenge
            crud.update_challenge(db=db, challenge_id=existing_challenge.challenge_id, challenge=challenge_data)
            print(f"Updated challenge: {challenge_data.title}")
        else:
            # Create new challenge
            crud.create_challenge(db=db, challenge=challenge_data)
            print(f"Created challenge: {challenge_data.title}")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_challenges(db)
        print("Default challenges seeded successfully!")
    except Exception as e:
        print(f"Error seeding challenges: {e}")
    finally:
        db.close()
