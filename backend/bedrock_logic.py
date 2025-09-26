import boto3
import json
import os
import requests
import re
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

# --- 애플리케이션 모듈 임포트 ---
from backend.routes.ai_challenge_router import AICallengeCreateRequest, create_and_join_ai_challenge
from backend.routes.dashboard import get_dashboard
from backend import schemas
from backend.models import User, TransportMode
from backend.database import get_db

# --- 설정 ---
# ✅ 사용자가 제공한 설정을 여기에 반영합니다.
AWS_DEFAULT_REGION = "us-east-1"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyBgs37kJYWB7zsTfIrDTqe1hpOxBhNkH44")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "01354cc88406341ec")

# 일반 LLM 호출에 사용할 모델 ARN (Inference Profile)
BEDROCK_MODEL_ARN = os.getenv("BEDROCK_MODEL_ARN", "arn:aws:bedrock:us-east-1:327784329358:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0")
# Bedrock 지식 기반(Knowledge Base) 설정
BEDROCK_KNOWLEDGE_BASE_ID = os.getenv("BEDROCK_KNOWLEDGE_BASE_ID", "PUGB1AL6L1")
# 지식 기반 답변 생성에 사용할 표준 파운데이션 모델 ID
BEDROCK_KB_GENERATOR_MODEL_ID = "anthropic.claude-3-sonnet-v1:0"


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

class RouterDecision(BaseModel):
    action: str
    query: Optional[str] = None
    user_intent: Optional[str] = None
    answer: Optional[str] = None
    dashboard_field: Optional[str] = None

def invoke_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """AWS Bedrock LLM 호출 함수"""
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
        response = bedrock_runtime_client.invoke_model(
            modelId=BEDROCK_MODEL_ARN, # ✅ 제공된 ARN을 modelId로 사용합니다.
            body=json.dumps(request_body)
        )
        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text']
    except Exception as e:
        print(f"[오류] Bedrock 모델 호출 중 오류가 발생했습니다: {e}")
        return None

def query_knowledge_base(query: str) -> Optional[str]:
    """Bedrock 지식 기반 검색 함수"""
    if not bedrock_agent_runtime_client or not BEDROCK_KNOWLEDGE_BASE_ID:
        print("[알림] 지식 기반 클라이언트가 초기화되지 않았거나 ID가 설정되지 않았습니다.")
        return None
    print(f"\n[알림] Bedrock 지식 기반에서 '{query}'에 대한 정보를 검색합니다...")
    try:
        # 지식 기반 API는 표준 파운데이션 모델 ARN이 필요합니다.
        model_arn = f"arn:aws:bedrock:{AWS_DEFAULT_REGION}::foundation-model/{BEDROCK_KB_GENERATOR_MODEL_ID}"
        response = bedrock_agent_runtime_client.retrieve_and_generate(
            input={'text': query},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': BEDROCK_KNOWLEDGE_BASE_ID,
                    'modelArn': model_arn
                }
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
        print(f"[오류] Bedrock 지식 기반 검색 중 오류가 발생했습니다: {e}")
        return None

def perform_web_search(query: str) -> str:
    """Google Custom Search API를 사용한 웹 검색"""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        return "웹 검색 기능이 설정되지 않았습니다. API 키와 CSE ID를 확인해주세요."
    print(f"\n[알림] 웹에서 '{query}'에 대한 최신 정보를 검색합니다...")
    try:
        search_url = "https://www.googleapis.com/customsearch/v1"
        search_params = {'key': GOOGLE_API_KEY, 'cx': GOOGLE_CSE_ID, 'q': query, 'num': 3}
        search_response = requests.get(search_url, params=search_params, timeout=5)
        search_response.raise_for_status()
        search_results = search_response.json().get('items', [])
        
        if not search_results:
            return "웹 검색 결과가 없습니다."
        
        snippets = [item.get('snippet', '') for item in search_results]
        return "\n\n".join(snippets)

    except requests.exceptions.RequestException as e:
        print(f"[오류] 웹 검색 과정에서 오류가 발생했습니다: {e}")
        return "정보 검색 과정에서 오류가 발생했습니다."
    except Exception as e:
        print(f"[오류] 웹 검색 결과 처리 중 오류 발생: {e}")
        return "검색 결과를 처리하는 중 오류가 발생했습니다."

async def _handle_dashboard_query(
    user_id: int, 
    db: Session, 
    router_decision: RouterDecision
) -> str:
    """대시보드 관련 쿼리 처리"""
    print("[알림] 사용자 대시보드 정보를 조회합니다.")
    try:
        current_user_obj = db.query(User).filter(User.user_id == user_id).first()
        if not current_user_obj:
            raise HTTPException(status_code=404, detail="User not found")
        
        dashboard_data = await get_dashboard(current_user=current_user_obj, db=db)
        
        field = router_decision.dashboard_field
        if field == "credits":
            return f"현재 보유하신 크레딧은 {dashboard_data.total_points:,}C입니다."
        elif field == "carbon_saved":
            return f"지금까지 총 {dashboard_data.total_saved:.2f}kg의 탄소를 절약하셨습니다! 정말 대단해요! 🌱"
        elif field == "garden_level":
            return f"현재 정원 레벨은 {dashboard_data.garden_level}레벨입니다. 계속 노력하시면 더 멋진 정원을 만들 수 있어요!"
        elif field == "today_saved":
            return f"오늘 절약하신 탄소는 {dashboard_data.co2_saved_today:.0f}g입니다."
        elif field == "recent_activity":
            if dashboard_data.last7days:
                total_saved_7days = sum(d.saved_g for d in dashboard_data.last7days)
                return f"최근 7일간 총 {total_saved_7days:.0f}g의 탄소를 절약하셨습니다."
            return "최근 활동 기록이 없습니다. 오늘부터 시작해보세요!"
        else:
            challenge_goal = dashboard_data.challenge.goal
            challenge_progress = dashboard_data.challenge.progress
            percentage = (challenge_progress / challenge_goal * 100) if challenge_goal > 0 else 0
            
            return (
                f"📊 {current_user_obj.username}님의 대시보드 요약\n\n"
                f"💰 보유 크레딧: {dashboard_data.total_points:,}C\n"
                f"🌍 총 절약 탄소: {dashboard_data.total_saved:.2f}kg\n"
                f"🌳 정원 레벨: {dashboard_data.garden_level}레벨\n"
                f"📅 오늘 절약: {dashboard_data.co2_saved_today:.0f}g\n"
                f"🏆 챌린지 진행률: {percentage:.1f}%\n\n"
                "더 궁금한 점이 있으시면 언제든 물어보세요!"
            )
    except Exception as e:
        print(f"[오류] 대시보드 정보 조회 중 오류 발생: {e}")
        return "사용자 정보를 조회하는 데 실패했습니다. 다시 시도해 주세요."

async def _handle_recommend_challenge(
    user_query: str, 
    user_id: int, 
    db: Session, 
    router_decision: RouterDecision
) -> str:
    """AI 챌린지 추천 및 생성 로직"""
    print("[알림] AI 챌린지를 추천하고 생성합니다.")
    
    current_user_obj = db.query(User).filter(User.user_id == user_id).first()
    if not current_user_obj:
        raise HTTPException(status_code=404, detail="User not found")
    
    dashboard_data = await get_dashboard(current_user=current_user_obj, db=db)
    
    mode_stats = {m.mode: m.saved_g for m in dashboard_data.modeStats}
    most_used_mode = max(mode_stats, key=mode_stats.get) if mode_stats else "없음"
    
    challenge_prompt = f"""You are an AI assistant that generates personalized eco-friendly challenges in Korean. Generate ONE challenge that is achievable within 7 days.
    User Stats:
    - Total carbon saved: {dashboard_data.total_saved:.2f}kg
    - Most used transport: {most_used_mode}
    - Garden level: {dashboard_data.garden_level}
    - Recent 7 days activity: {sum(d.saved_g for d in dashboard_data.last7days)}g saved
    
    Create a fun and encouraging challenge. Provide a response ONLY in the following JSON format:
    {{
        "title": "A creative and friendly Korean title",
        "description": "An encouraging Korean description",
        "reward": an integer between 10 and 100,
        "target_mode": "WALK/BIKE/BUS/SUBWAY/ANY",
        "goal_type": "CO2_SAVED/DISTANCE_KM/TRIP_COUNT",
        "goal_target_value": a float or integer
    }}"""
    
    user_intent = router_decision.user_intent or user_query
    challenge_idea_str = invoke_llm(challenge_prompt, f"User intent: {user_intent}")
    
    try:
        json_match = re.search(r'\{.*\}', challenge_idea_str, re.DOTALL)
        if not json_match:
            raise ValueError("LLM 응답에서 JSON을 찾을 수 없습니다.")
        
        challenge_idea = json.loads(json_match.group())
        
        challenge_request = AICallengeCreateRequest(
            title=challenge_idea["title"],
            description=challenge_idea["description"],
            reward=challenge_idea["reward"],
            target_mode=TransportMode[challenge_idea.get("target_mode", "ANY").upper()],
            goal_type=schemas.ChallengeGoalType[challenge_idea["goal_type"].upper()],
            goal_target_value=float(challenge_idea["goal_target_value"])
        )
        
        await create_and_join_ai_challenge(
            request=challenge_request, db=db, current_user=current_user_obj
        )
        
        goal_unit = 'km' if 'DISTANCE' in challenge_idea['goal_type'] else 'g' if 'CO2' in challenge_idea['goal_type'] else '회'
        return (
            f"🎯 새로운 챌린지를 생성했어요!\n\n"
            f"**{challenge_idea['title']}**\n"
            f"{challenge_idea['description']}\n\n"
            f"🎁 보상: {challenge_idea['reward']}C\n"
            f"📊 목표: {challenge_idea['goal_target_value']} {goal_unit}\n\n"
            f"화이팅! 당신의 작은 실천이 지구를 살립니다! 💚"
        )
        
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"[오류] 챌린지 생성 중 오류: {e}\nLLM Raw Response: {challenge_idea_str}")
        return "챌린지를 추천하는 데 실패했어요. 대신 '이번 주 대중교통 3번 이용하기'는 어떠세요?"

def classify_user_intent(user_query: str) -> RouterDecision:
    """사용자 의도를 분류하는 향상된 함수"""
    router_system_prompt = """You are a highly intelligent routing agent for 'RePlanet', an eco-friendly service application. Your primary role is to accurately classify the user's intent based on their query and provide a structured JSON output. Analyze the user's message carefully and choose the most appropriate action.

Categories and Logic:

1.  **"get_user_dashboard"**: This is for any query related to the user's personal data and statistics within the app.
    * **Keywords (Korean)**: 크레딧, 포인트, 탄소, 절약, 정원, 레벨, 내 정보, 얼마나, 뭐했지, 기록, 데이터, 현황, 등급
    * **Logic**: If the user asks about their own achievements, savings, or status, this is the correct action.
    * **`dashboard_field`**: You MUST populate this field.
        * `credits`: For questions about points, credits (e.g., "내 포인트 얼마야?").
        * `carbon_saved`: For questions about total carbon savings (e.g., "탄소 얼마나 줄였어?").
        * `garden_level`: For questions about their garden's level or status (e.g., "내 정원 레벨은?").
        * `today_saved`: For questions about today's activity (e.g., "오늘 내가 한 활동 알려줘").
        * `recent_activity`: For questions about recent activities or the past week (e.g., "최근 일주일 기록 보여줘").
        * `all`: For general or multiple data requests (e.g., "내 정보 요약해줘").

2.  **"recommend_challenge"**: This is for when the user wants a new task, mission, or challenge.
    * **Keywords (Korean)**: 챌린지, 추천, 미션, 퀘스트, 할만한 거, 뭐할까, 도전
    * **Logic**: If the user is looking for a new goal or activity to participate in, use this action.

3.  **"knowledge_base_search"**: This is for questions about the RePlanet service itself, its features, or related environmental policies. This is an internal information search.
    * **Keywords (Korean)**: 리플래닛, 사용법, 정책, 에코마일리지, 포인트 사용법, 앱 기능
    * **Logic**: Questions that can be answered by an FAQ or a user manual fall into this category.
    * **`query`**: Refine the user's question into a clear search term. Example: "포인트는 어디다 쓸 수 있어?" -> "포인트 사용처".

4.  **"general_search"**: This is for real-time information, current events, or general knowledge questions not related to the user's data or the app's features. This requires an external web search.
    * **Keywords (Korean)**: 날씨, 오늘, 뉴스, 최신, [일반 명사] 뭐야?, [지역] 정보
    * **Logic**: If the question cannot be answered by the app's internal data (dashboard, knowledge base), use this.
    * **`query`**: Refine the query for an effective web search. Example: "오늘 서울 미세먼지 어때?" -> "서울 오늘 미세먼지 농도".

5.  **"direct_answer"**: This is for simple conversational turns like greetings, thanks, or affirmations where a direct, simple response is sufficient.
    * **Keywords (Korean)**: 안녕, 하이, 고마워, 응, 아니, ㅋㅋ, ㅎㅎ
    * **Logic**: Use for chit-chat that doesn't fit other categories.
    * **`answer`**: Provide a friendly and short response in Korean.

Output Format: You must respond ONLY with a valid JSON object. Do not include any text before or after the JSON block.

{
    "action": "The selected category name from the list above",
    "query": "A refined search query for 'knowledge_base_search' or 'general_search', otherwise null",
    "user_intent": "The user's original, unmodified message",
    "dashboard_field": "The specific data field for 'get_user_dashboard', otherwise null",
    "answer": "A direct, short response for 'direct_answer', otherwise null"
}
"""
    
    llm_response = invoke_llm(router_system_prompt, user_query)
    
    if not llm_response:
        return RouterDecision(action="general_search", query=user_query, user_intent=user_query)
    
    try:
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON found in LLM response for router")
            
        decision_data = json.loads(json_match.group())
        decision_data.setdefault("user_intent", user_query)
        return RouterDecision(**decision_data)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[오류] 라우터 결정 파싱 실패: {e}\nLLM Raw Response: {llm_response}")
        return RouterDecision(action="general_search", query=user_query, user_intent=user_query)

@router.post("/")
async def chatbot_endpoint(request: ChatRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """메인 챗봇 엔드포인트"""
    user_query = request.message
    user_id = request.user_id
    
    current_user_obj = db.query(User).filter(User.user_id == user_id).first()
    if not current_user_obj:
        raise HTTPException(status_code=404, detail="User not found")
    
    print(f"\n{'='*50}\n사용자 질문: {user_query} (ID: {user_id})\n{'='*50}\n")
    
    router_decision = classify_user_intent(user_query)
    action = router_decision.action
    print(f"[라우터 결정] Action: {action}, Field: {router_decision.dashboard_field}")
    
    final_answer = ""
    
    try:
        if action == "get_user_dashboard":
            final_answer = await _handle_dashboard_query(user_id, db, router_decision)
        elif action == "recommend_challenge":
            final_answer = await _handle_recommend_challenge(user_query, user_id, db, router_decision)
        elif action == "knowledge_base_search":
            final_answer = query_knowledge_base(router_decision.query or user_query)
            if not final_answer:
                action = "general_search"
                print("[대체] 지식 기반 검색 실패, 웹 검색으로 전환합니다.")
        
        if action == "general_search":
            search_results = perform_web_search(router_decision.query or user_query)
            summarize_prompt = "You are a helpful assistant. Summarize the following search results in Korean concisely and in a friendly tone, directly answering the user's question."
            final_answer = invoke_llm(summarize_prompt, f"User question: {user_query}\n\nSearch results:\n{search_results}")
                
        elif action == "direct_answer":
            final_answer = router_decision.answer or "안녕하세요! 리플래닛 AI 도우미입니다. 무엇을 도와드릴까요? 😊"
        
        if not final_answer:
            final_answer = "죄송합니다, 요청을 처리하는 데 문제가 발생했습니다. 다른 방식으로 질문해주시겠어요?"
        
        print(f"\n[최종 답변]\n{final_answer[:200]}...")
        
        return {
            "response": final_answer,
            "metadata": {
                "action": action,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        print(f"[오류] 챗봇 엔드포인트 처리 중 예외 발생: {e}")
        raise HTTPException(status_code=500, detail="요청 처리 중 서버에서 오류가 발생했습니다.")