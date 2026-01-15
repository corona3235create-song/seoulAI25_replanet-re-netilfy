import openai
import json
import os
import requests
import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

# --- 애플리케이션 모듈 임포트 ---
# 프로젝트 구조에 맞게 경로가 설정되어 있는지 확인 필요
from routes.ai_challenge_router import AICallengeCreateRequest, create_and_join_ai_challenge
from routes.dashboard import get_dashboard
import schemas
from models import User, TransportMode
from database import get_db

# --- 설정 ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")

# --- OpenAI 클라이언트 초기화 ---
if not OPENAI_API_KEY:
    print("[경고] OPENAI_API_KEY가 설정되지 않았습니다. AI 기능이 제한될 수 있습니다.")
    openai_client = None
else:
    try:
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        print("[알림] OpenAI 클라이언트가 성공적으로 초기화되었습니다.")
    except Exception as e:
        print(f"[오류] OpenAI 클라이언트 생성 중 오류가 발생했습니다: {e}")
        openai_client = None

router = APIRouter(
    prefix="/chat",
    tags=["Chatbot"]
)

# --- 데이터 모델 ---
class ChatRequest(BaseModel):
    user_id: int
    message: str

class RouterDecision(BaseModel):
    action: str
    query: Optional[str] = None
    user_intent: Optional[str] = None
    answer: Optional[str] = None
    dashboard_field: Optional[str] = None

# --- 공통 함수 ---
def invoke_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """OpenAI LLM 호출 함수"""
    if not openai_client:
        print("[오류] OpenAI 클라이언트가 초기화되지 않았습니다.")
        return "죄송합니다, AI 서비스가 현재 연결되어 있지 않습니다. 잠시 후 다시 시도해주세요."
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL_NAME,
            messages=messages,
            max_tokens=2048
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[오류] OpenAI 모델 호출 중 오류가 발생했습니다: {e}")
        return None

def perform_web_search(query: str) -> str:
    """Google Custom Search API를 사용한 웹 검색"""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return "웹 검색 기능이 설정되지 않았습니다."
    
    try:
        search_url = "https://www.googleapis.com/customsearch/v1"
        search_params = {'key': GOOGLE_API_KEY, 'cx': GOOGLE_CSE_ID, 'q': query, 'num': 3}
        search_response = requests.get(search_url, params=search_params, timeout=5)
        search_response.raise_for_status()
        search_results = search_response.json().get('items', [])

        if not search_results:
            return "웹 검색 결과가 없습니다."

        snippets = [f"{item.get('title', '')}\n{item.get('snippet', '')}" for item in search_results]
        return "\n\n".join(snippets)
    except Exception as e:
        print(f"[오류] 웹 검색 오류: {e}")
        return "정보를 검색하는 중에 문제가 발생했습니다."

# --- 핸들러 로직 ---
async def _handle_dashboard_query(user_id: int, db: Session, router_decision: RouterDecision) -> str:
    """사용자 대시보드 정보를 조회하여 답변 구성"""
    try:
        current_user_obj = db.query(User).filter(User.user_id == user_id).first()
        if not current_user_obj:
            return "사용자 정보를 찾을 수 없습니다."

        dashboard_data = await get_dashboard(current_user=current_user_obj, db=db)
        field = router_decision.dashboard_field

        if field == "credits":
            return f"현재 보유하신 크레딧은 {dashboard_data.total_points:,}C입니다."
        elif field == "carbon_saved":
            return f"지금까지 총 {dashboard_data.total_saved:.2f}kg의 탄소를 절약하셨습니다! 🌱"
        elif field == "garden_level":
            return f"현재 정원 레벨은 {dashboard_data.garden_level}레벨입니다. 멋진 정원이네요!"
        elif field == "today_saved":
            return f"오늘 절약하신 탄소는 {dashboard_data.co2_saved_today:.0f}g입니다."
        else:
            percentage = (dashboard_data.challenge.progress / dashboard_data.challenge.goal * 100) if dashboard_data.challenge.goal > 0 else 0
            return (
                f"📊 {current_user_obj.username}님의 요약\n"
                f"💰 크레딧: {dashboard_data.total_points:,}C\n"
                f"🌍 총 절약: {dashboard_data.total_saved:.2f}kg\n"
                f"🌳 정원: {dashboard_data.garden_level}레벨\n"
                f"📅 오늘: {dashboard_data.co2_saved_today:.0f}g\n"
                f"🏆 챌린지: {percentage:.1f}% 진행 중!"
            )
    except Exception as e:
        return "대시보드 조회 중 오류가 발생했습니다."

async def _handle_recommend_challenge(user_query: str, user_id: int, db: Session, router_decision: RouterDecision) -> str:
    """AI를 통해 맞춤형 챌린지 생성 및 참여"""
    current_user_obj = db.query(User).filter(User.user_id == user_id).first()
    dashboard_data = await get_dashboard(current_user=current_user_obj, db=db)
    
    # 통계 추출
    mode_stats = {m.mode: m.saved_g for m in dashboard_data.modeStats}
    most_used_mode = max(mode_stats, key=mode_stats.get) if mode_stats else "ANY"

    challenge_prompt = f"""You are an AI assistant for eco-friendly challenges. Generate ONE challenge JSON.
    Stats: {dashboard_data.total_saved}kg saved, most used: {most_used_mode}.
    JSON format: {{"title": "string", "description": "string", "reward": 10~100, "target_mode": "WALK/BIKE/BUS/SUBWAY/ANY", "goal_type": "CO2_SAVED/DISTANCE_KM/TRIP_COUNT", "goal_target_value": float}}"""

    llm_res = invoke_llm(challenge_prompt, f"User intent: {router_decision.user_intent or user_query}")
    
    try:
        json_match = re.search(r'\{.*\}', llm_res, re.DOTALL)
        challenge_idea = json.loads(json_match.group())

        challenge_req = AICallengeCreateRequest(
            title=challenge_idea["title"],
            description=challenge_idea["description"],
            reward=challenge_idea["reward"],
            target_mode=TransportMode[challenge_idea.get("target_mode", "ANY").upper()],
            goal_type=schemas.ChallengeGoalType[challenge_idea["goal_type"].upper()],
            goal_target_value=float(challenge_idea["goal_target_value"])
        )

        await create_and_join_ai_challenge(request=challenge_req, db=db, current_user=current_user_obj)
        
        unit = 'km' if 'DISTANCE' in challenge_idea['goal_type'] else 'g' if 'CO2' in challenge_idea['goal_type'] else '회'
        return f"🎯 **{challenge_idea['title']}**\n{challenge_idea['description']}\n\n🎁 보상: {challenge_idea['reward']}C\n📊 목표: {challenge_idea['goal_target_value']}{unit}"
    except:
        return "챌린지 생성에 실패했습니다. 대중교통 이용 챌린지에 참여해보시는 건 어떨까요?"

def classify_user_intent(user_query: str) -> RouterDecision:
    """사용자의 질문 의도 분류"""
    system_prompt = """You are a RePlanet AI router. Classify intent into:
    1. get_user_dashboard (stats/credits), 2. recommend_challenge (new missions), 
    3. general_search (news/weather), 4. direct_answer (greetings).
    Return JSON ONLY."""
    
    llm_res = invoke_llm(system_prompt, user_query)
    try:
        json_match = re.search(r'\{.*\}', llm_res, re.DOTALL)
        return RouterDecision(**json_loads(json_match.group()))
    except:
        return RouterDecision(action="general_search", query=user_query)

# --- 메인 엔드포인트 ---
@router.post("/")
async def chatbot_endpoint(request: ChatRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    user_query = request.message
    user_id = request.user_id
    
    current_user = db.query(User).filter(User.user_id == user_id).first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    decision = classify_user_intent(user_query)
    action = decision.action
    
    final_answer = ""
    if action == "get_user_dashboard":
        final_answer = await _handle_dashboard_query(user_id, db, decision)
    elif action == "recommend_challenge":
        final_answer = await _handle_recommend_challenge(user_query, user_id, db, decision)
    elif action == "general_search":
        search_res = perform_web_search(decision.query or user_query)
        final_answer = invoke_llm("Summarize search results in Korean concisely.", f"Query: {user_query}\nResults: {search_res}")
    else:
        final_answer = decision.answer or "안녕하세요! 리플래닛 AI입니다. 😊"

    return {
        "response": final_answer or "요청을 처리할 수 없습니다.",
        "metadata": {"action": action, "timestamp": datetime.utcnow().isoformat()}
    }