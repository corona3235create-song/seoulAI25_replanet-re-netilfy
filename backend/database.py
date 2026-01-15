import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 현재 파일(database.py)의 디렉토리 경로를 기준으로 데이터베이스 경로 설정
# 이렇게 하면 실행 위치에 상관없이 항상 올바른 경로를 유지할 수 있습니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "ecoooo.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 데이터베이스 디렉토리 존재 여부 확인 및 생성
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


# SQLAlchemy 엔진 생성
# connect_args는 SQLite 사용 시 멀티스레드 환경에서 필요합니다.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,  # 개발 중 SQL 쿼리를 보려면 True로 설정
    pool_pre_ping=True,
    pool_recycle=300,
)

# 데이터베이스 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 모델 클래스들의 기반이 될 Base 클래스
Base = declarative_base()

def get_db():
    """
    요청마다 독립적인 데이터베이스 세션을 생성하고,
    요청 처리가 끝나면 세션을 닫는 의존성 함수입니다.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    데이터베이스 테이블을 생성하고 초기 데이터를 삽입하는 함수입니다.
    서버 시작 시 호출될 수 있습니다.
    """
    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    # 초기 데이터 시딩
    from seed_admin_user import seed_admin_user
    from seed_challenges import seed_challenges
    from seed_garden_levels import seed_garden_levels

    db = SessionLocal()
    try:
        # 여기에 필요한 초기 데이터 생성 로직을 추가할 수 있습니다.
        # 예: 기본 그룹 생성 등
        seed_admin_user(db)
        seed_challenges(db)
        seed_garden_levels(db)
        print("Database seeding completed successfully.")
    except Exception as e:
        print(f"An error occurred during database seeding: {e}")
    finally:
        db.close()