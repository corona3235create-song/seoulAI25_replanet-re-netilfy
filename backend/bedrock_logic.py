import boto3
import json
import os
import requests
import re
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta

# --- 애플리케이션 모듈 임포트 ---
# ai_challenge_router에서 직접 함수와 모델을 가져옵니다.
from backend.routes.ai_challenge_router import AICallengeCreateRequest, create_and_join_ai_challenge
from backend.routes.dashboard import get_dashboard
from backend import crud, models, schemas
from backend.models import User, TransportMode, Challenge, ChallengeMember
from backend.database import get_db

# --- 설정 ---
AWS_DEFAULT_REGION = "us-east-1"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyBgs37kJYWB7zsTfIrDTqe1hpOxBhNkH44")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "01354cc88406341ec")
BEDROCK_MODEL_ARN = os.getenv("BEDROCK_MODEL_ARN", "arn:aws:bedrock:us-east-1:327784329358:inference-profile/us.anthropic.claude-opus-4-20250514-v1:0")
BEDROCK_KNOWLEDGE_BASE_ID = os.getenv("BEDROCK_KNOWLEDGE_BASE_ID", "PUGB1AL6L1")

# --- Boto3 클라이언트 초기화 ---
try:
    bedrock_runtime_client = boto3.client('bedrock-runtime', region_name=AWS_DEFAULT_REGION)
    bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime', region_name=AWS_DEFAULT_REGION)
    print("[알림] AWS Bedrock 클라이언트가 성공적으로 초기화되었습니다.")
except Exception as e:
    print(f"[오류] AWS 클라이언트 생성 중 오류가 발생했습니다: {e}")
    bedrock_runtime_client = None
    bedrock_agent_runtime_client = None

# FastAPI 라우터 생성
router = APIRouter(
    prefix="/chat",
    tags=["Chatbot"]
)

class ChatRequest(BaseModel):
    user_id: int
    message: str

def invoke_llm(system_prompt, user_prompt):
    if not bedrock_runtime_client:
        raise ConnectionError("Bedrock runtime client is not initialized.")
    try:
        messages = [{"role": "user", "content": user_prompt}]
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": messages
        }
        response = bedrock_runtime_client.invoke_model(modelId=BEDROCK_MODEL_ARN, body=json.dumps(request_body))
        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text']
    except Exception as e:
        print(f"Bedrock 모델 호출 중 오류가 발생했습니다: {e}")
        return None

def query_knowledge_base(query):
    if not bedrock_agent_runtime_client:
        raise ConnectionError("Bedrock agent runtime client is not initialized.")
    print(f"\n[알림] Bedrock 지식 기반에서 '{query}'에 대한 정보를 검색합니다...")
    try:
        response = bedrock_agent_runtime_client.retrieve_and_generate(
            input={'text': query},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {'knowledgeBaseId': BEDROCK_KNOWLEDGE_BASE_ID, 'modelArn': BEDROCK_MODEL_ARN}
            }
        )
        if response and response.get('output') and response.get('citations'):
            answer = response['output']['text']
            citations = response['citations']
            source_details = []
            for citation in citations:
                if citation.get('retrievedReferences'):
                    retrieved_ref = citation['retrievedReferences'][0]
                    location = retrieved_ref.get('location', {}).get('s3Location', {}).get('uri')
                    if location:
                        source_details.append(f"- {location}")
            formatted_answer = f"{answer}\n\n--- 출처 ---\n" + "\n".join(source_details) if source_details else answer
            print("[알림] 지식 기반에서 답변을 성공적으로 찾았습니다.")
            return formatted_answer
        else:
            print("[알림] 지식 기반에서 관련 정보를 찾지 못했습니다.")
            return None
    except Exception as e:
        print(f"Bedrock 지식 기반 검색 중 오류가 발생했습니다: {e}")
        return None

def perform_web_search(query):
    print(f"\n[알림] 웹에서 '{query}'에 대한 최신 정보를 검색합니다...")
    try:
        search_url = "https://www.googleapis.com/customsearch/v1"
        search_params = {'key': GOOGLE_API_KEY, 'cx': GOOGLE_CSE_ID, 'q': query, 'num': 3}
        search_response = requests.get(search_url, params=search_params)
        search_response.raise_for_status()
        search_results = search_response.json()
        items = search_results.get('items', [])
        if not items: return "웹 검색 결과가 없습니다."
        full_context = ""
        urls = [item.get('link') for item in items]
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        print("[알림] 검색된 웹페이지의 본문을 중요도 순으로 추출합니다...")
        for url in urls:
            if not url: continue
            try:
                page_response = requests.get(url, headers=headers, timeout=5)
                page_response.raise_for_status()
                soup = BeautifulSoup(page_response.text, 'lxml')
                text_parts = [element.get_text(strip=True) for tag in ['h1', 'h2', 'h3', 'p'] for element in soup.find_all(tag)]
                page_text = '\n'.join(text_parts)
                full_context += f"--- URL: {url}의 내용 ---\n{page_text}\n\n"
            except requests.exceptions.RequestException as e:
                print(f"  - URL {url} 방문 실패: {e}")
                continue
        if not full_context: return "웹페이지 내용을 가져오는 데 실패했습니다."
        print(f"[추출 완료] 총 {len(full_context)}자리의 정보를 바탕으로 답변을 생성합니다.")
        return full_context
    except Exception as e:
        print(f"웹 검색 과정에서 오류가 발생했습니다: {e}")
        return "정보 검색 과정에서 오류가 발생했습니다."

async def _handle_recommend_challenge(user_query: str, user_id: int, db: Session, router_decision: dict):
    """AI 챌린지 추천 및 생성 로직을 처리하는 헬퍼 함수"""
    print("[알림] AI 챌린지를 추천하고 생성합니다.")
    current_user_obj = db.query(User).filter(User.user_id == user_id).first()
    if not current_user_obj:
        raise HTTPException(status_code=404, detail="User not found for challenge recommendation.")
    
    dashboard_data = await get_dashboard(current_user=current_user_obj, db=db)
    
    challenge_prompt = f"""
    You are an AI assistant that generates eco-friendly challenge ideas.
    Based on the user's intent and their recent activity data, generate a single challenge idea in JSON format.
    The challenge should be simple, actionable, and encourage carbon reduction.
    Prioritize light challenges that the user hasn't done much recently, or suggest new types of activities.
    Avoid recommending challenges for activities the user has frequently done in the last 7 days.
    
    User's recent activity data:
    - Last 7 days carbon saved (g): {json.dumps([{"date": str(d.date), "saved_g": d.saved_g} for d in dashboard_data.last7days])}
    - Mode statistics: {json.dumps([{"mode": m.mode, "saved_g": m.saved_g} for m in dashboard_data.modeStats])}
    - Total carbon saved (kg): {dashboard_data.total_saved}
    - Current garden level: {dashboard_data.garden_level}
    
    Provide a title, a short description, a reward (integer), a goal_type (must be one of: CO2_SAVED, DISTANCE_KM, TRIP_COUNT), a goal_target_value (float), and an optional target_mode (ANY, WALK, BIKE, PUBLIC_TRANSPORT).
    
    Example for a distance-based challenge:
    {{
        "title": "주말에 3km 걷기",
        "description": "이번 주말, 차 대신 두 발로 3km를 걸어보세요!",
        "reward": 50,
        "target_mode": "WALK",
        "goal_type": "DISTANCE_KM",
        "goal_target_value": 3.0
    }}
    Example for a general CO2-based challenge:
    {{
        "title": "분리수거 챌린지",
        "description": "오늘 하루 분리수거를 완벽하게 실천해서 탄소 배출을 줄여보세요!",
        "reward": 20,
        "target_mode": "ANY",
        "goal_type": "CO2_SAVED",
        "goal_target_value": 100.0
    }}
    
    User intent: "{router_decision.get("user_intent", user_query)}"
    Your JSON response:
    """
    
    challenge_idea_str = invoke_llm(challenge_prompt, "")
    
    try:
        challenge_idea = json.loads(challenge_idea_str)
        
        challenge_request = AICallengeCreateRequest(
            title=challenge_idea["title"],
            description=challenge_idea["description"],
            reward=challenge_idea["reward"],
            target_mode=TransportMode[challenge_idea.get("target_mode", "ANY").upper()],
            goal_type=schemas.ChallengeGoalType[challenge_idea["goal_type"].upper()],
            goal_target_value=float(challenge_idea["goal_target_value"])
        )
        
        challenge_response = await create_and_join_ai_challenge(
            request=challenge_request,
            db=db,
            current_user=current_user_obj
        )
        
        final_answer = challenge_response.get("message", "AI 챌린지 생성 및 참여에 실패했습니다.")
        if challenge_response.get("challenge"):
            final_answer += f" 챌린지 제목: {challenge_response['challenge'].title}"
        return final_answer

    except (json.JSONDecodeError, KeyError) as e:
        print(f"[오류] AI 챌린지 아이디어 파싱 중 오류 발생: {e}")
        return "AI 챌린지 아이디어를 이해하는 데 문제가 발생했습니다. 다른 방식으로 제안해볼까요?"
    except Exception as e:
        print(f"[오류] AI 챌린지 생성 및 참여 중 오류 발생: {e}")
        return f"AI 챌린지 생성 및 참여 중 오류가 발생했습니다: {e}"

@router.post("/")
async def chatbot_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    user_query = request.message
    user_id = request.user_id

    print(f"사용자 질문: {user_query}\n")
    print("[1단계] 사용자의 질문 의도를 파악합니다...")
    router_system_prompt = f"""
    You are a smart orchestrator that analyzes the user's question and decides which action to take... 
    (이하 프롬프트 내용은 기존과 동일)
    """
    
    router_output_str = invoke_llm(router_system_prompt, user_query)
    
    action, router_decision = None, {}
    if not router_output_str:
        action, router_decision = "general_search", {"query": user_query}
    else:
        try:
            json_match = re.search(r'\{.*\}', router_output_str, re.DOTALL)
            if json_match:
                router_decision = json.loads(json_match.group())
                action = router_decision.get("action")
            else: raise ValueError("No JSON object found")
        except Exception as e:
            print(f"[오류] 조율자(Router) 결정 파싱 실패: {e}. 일반 검색으로 전환합니다.")
            action, router_decision = "general_search", {"query": user_query}

    final_answer, query, original_action = "", router_decision.get("query", user_query), action

    if action == "knowledge_base_search":
        print(f"[알림] 조율자 판단: '{action}'. 지식 기반 검색을 시작합니다.")
        final_answer = query_knowledge_base(query)
        if not final_answer:
            print("[알림] 지식 기반 검색 실패. 웹 검색으로 전환합니다.")
            action = "general_search"

    if action == "general_search":
        if original_action != 'knowledge_base_search':
            print(f"[알림] 조율자 판단: '{action}'. 웹 검색을 시작합니다.")
        search_results = perform_web_search(query)
        if "오류" in search_results or "없습니다" in search_results:
            final_answer = search_results
        else:
            search_results = search_results[:20000]
            print("\n[3단계] 검색 결과를 바탕으로 최종 답변을 생성합니다...")
            final_answer_system_prompt = "당신은 주어진 검색 결과를 바탕으로 사용자의 질문에 대해... (이하 프롬프트 내용은 기존과 동일)"
            final_answer = invoke_llm(final_answer_system_prompt, f"<search_results>\n{search_results}\n</search_results>\n\n사용자 질문: {user_query}")

    elif action == "detect_activity_and_suggest_challenge":
        print("[알림] 조율자 판단: 'detect_activity_and_suggest_challenge'.")
        activity_keywords = {"자전거": TransportMode.BIKE, "걸어서": TransportMode.WALK, "도보": TransportMode.WALK, "버스": TransportMode.BUS, "지하철": TransportMode.SUBWAY}
        detected_keyword, detected_activity_mode = None, None
        for keyword, mode in activity_keywords.items():
            if keyword in user_query:
                detected_keyword, detected_activity_mode = keyword, mode
                break
        
        if not detected_activity_mode:
            final_answer = invoke_llm("You are a friendly AI assistant.", user_query)
        else:
            utc_today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=9)
            if datetime.utcnow().hour < 9: utc_today_start -= timedelta(days=1)
            utc_today_end = utc_today_start + timedelta(days=1)
            mobility_log = db.query(models.MobilityLog).filter(models.MobilityLog.user_id == user_id, models.MobilityLog.transport_mode == detected_activity_mode, models.MobilityLog.started_at >= utc_today_start, models.MobilityLog.started_at < utc_today_end).order_by(models.MobilityLog.started_at.desc()).first()
            if mobility_log:
                bonus_credits = int(mobility_log.distance_km * 5)
                crud.create_credit_log(db, user_id=user_id, points=bonus_credits, reason=f"챗봇 활동 확인 보너스: {detected_keyword}")
                final_answer = f"네! 오늘 {mobility_log.distance_km:.1f}km를 {detected_keyword}(으)로 이동하신 기록을 확인했어요. 정말 멋져요! 추가 보너스로 {bonus_credits}C를 드렸습니다. 🎁"
            else:
                joined_challenge_ids = {m.challenge_id for m in db.query(models.ChallengeMember).filter(models.ChallengeMember.user_id == user_id).all()}
                available_challenges = db.query(models.Challenge).filter(models.Challenge.challenge_id.notin_(joined_challenge_ids), models.Challenge.title.contains(detected_keyword)).all()
                if available_challenges:
                    suggested_challenge = available_challenges[0]
                    suggestion_prompt = f"You are a friendly and encouraging AI assistant... (이하 프롬프트 내용은 기존과 동일)"
                    final_answer = invoke_llm(suggestion_prompt, "")
                else:
                    print(f"[알림] 관련 챌린지 없음. 사용자 맞춤형 AI 챌린지 생성을 시도합니다.")
                    final_answer = await _handle_recommend_challenge(user_query, user_id, db, {"user_intent": f"{detected_keyword} 타기와 관련된 챌린지 추천"})

    elif action == "recommend_challenge":
        final_answer = await _handle_recommend_challenge(user_query, user_id, db, router_decision)

    elif action in ["get_carbon_reduction_tip", "get_goal_strategy"]:
        final_answer = invoke_llm("You are a helpful AI assistant...", router_decision.get("user_intent", user_query))

    elif action == "direct_answer":
        final_answer = router_decision.get("answer", "죄송합니다. 답변을 생성할 수 없습니다.")
    
    if not final_answer:
        final_answer = "죄송합니다. 요청을 처리하는 데 문제가 발생했습니다."

    print("\n--- 최종 답변 ---\n" + final_answer)
    return {"response": final_answer}