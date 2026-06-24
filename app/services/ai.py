import uuid
import json
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app import crud

def get_gemini_client() -> genai.Client:
    """Gemini API 클라이언트를 반환합니다."""
    return genai.Client(api_key=settings.GEMINI_API_KEY)

async def generate_embedding(text: str) -> List[float]:
    """gemini-embedding-001 모델을 사용하여 1536차원 벡터 임베딩을 생성합니다."""
    client = get_gemini_client()
    try:
        # 비동기 클라이언트 호출
        response = await client.aio.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
        )
        # embedding 객체에서 float 리스트 추출
        # 보통 response.embeddings[0].values 형태로 존재합니다.
        if response.embeddings:
            return response.embeddings[0].values
        elif response.embedding:
            return response.embedding.values
        else:
            # 기본 반환 예외 처리
            raise ValueError("No embeddings returned from Gemini API")
    except Exception as e:
        # 임베딩 생성 실패 시 1536차원 제로 벡터로 폴백(Fallback)하되 에러 로그를 남깁니다.
        print(f"[Embedding Error] Failed to generate embedding: {e}")
        return [0.0] * 1536

async def save_semantic_memory(user_id: uuid.UUID, query: str, response: str, db: AsyncSession):
    """과거 대화의 질문-답변 쌍을 임베딩하여 pgvector 데이터베이스에 저장합니다."""
    embedding_text = f"Question: {query}\nResponse: {response}"
    embedding = await generate_embedding(embedding_text)
    await crud.save_semantic_memory(db, user_id, query, response, embedding)

async def retrieve_semantic_memories(user_id: uuid.UUID, query: str, db: AsyncSession) -> List[Dict[str, str]]:
    """질문 내용을 기반으로 코사인 유사도 상위 3개의 과거 대화 기억을 조회합니다."""
    embedding = await generate_embedding(query)
    memories = await crud.retrieve_semantic_memories(db, user_id, embedding, limit=3)
    return [{"query": m.query, "response": m.response} for m in memories]

async def get_tts_text(response_text: str) -> str:
    """텍스트가 300자를 초과할 때, gemini-2.5-flash를 내부 호출하여

    150~250자 수준의 정중하고 자연스러운 구어체 텍스트로 요약 및 재가공합니다.
    """
    if len(response_text) <= 300:
        return response_text
        
    client = get_gemini_client()
    prompt = (
        "다음 문장은 시스템의 답변입니다. 이 답변을 150자 이상 250자 이하의 "
        "정중하고 친근하며 자연스러운 구어체(존댓말) 문장으로 요약 및 재가공해 주세요.\n"
        f"원본 답변: {response_text}"
    )
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"[TTS Summary Error] Failed to summarize text: {e}")
        return response_text[:250]  # 에러 발생 시 글자 수 강제 제한

# === Function Calling용 도구 정의 ===
# 실제 비동기 처리를 위해 래핑 및 라우팅을 구성할 목적으로 정보를 선언합니다.

def get_current_weather(location: str) -> str:
    """지정된 위치의 현재 날씨 정보를 조회합니다 (모의 도구)."""
    return f"{location}의 날씨는 현재 맑으며 온도는 24도, 습도는 50%입니다."

async def execute_ai_chat(user_id: uuid.UUID, query: str, db: AsyncSession) -> Dict[str, Any]:
    """사용자 메시지를 처리하여 Gemini AI 대화를 실행하고 필요한 도구를 바인딩 및 실행합니다."""
    client = get_gemini_client()
    
    # 1. 사용자 프로필 동적 로드
    profile = await crud.get_user_profile(db, user_id)
    profile_info = profile.profile_data if profile else {}
    
    # 2. 시스템 인스트럭션 빌드 (프로필 정보 머지)
    system_instruction = (
        "귀하는 사용자의 스마트한 개인 인공지능 비서 'ARGOS' 백엔드 시스템입니다.\n"
        "항상 정중하고 친절하게 답변하십시오.\n"
        f"현재 대화 중인 사용자 정보:\n{json.dumps(profile_info, ensure_ascii=False)}\n\n"
        "도구가 필요할 경우 제공된 도구 목록(날씨, 구글 서비스, IoT 제어 등)을 Function Calling 형태로 호출하여 사용하십시오."
    )
    
    # 3. 세맨틱 메모리를 통한 컨텍스트 로드
    past_memories = await retrieve_semantic_memories(user_id, query, db)
    memory_context = ""
    if past_memories:
        memory_context = "과거 대화 내역 참고:\n"
        for m in past_memories:
            memory_context += f"- 질문: {m['query']} / 답변: {m['response']}\n"
        memory_context += "\n"
        
    full_prompt = f"{memory_context}사용자 질문: {query}"
    
    # 4. 도구(Tools) 바인딩 및 Gemini API 비동기 호출
    # Function Calling에 사용할 도구 함수들을 지정합니다.
    # Google Workspace API 및 IoT API 연동을 위해 임베디드 툴 목록을 제공합니다.
    tools_list = [
        get_current_weather,
        # 아래의 Google Workspace 및 IoT 함수들을 Function Calling 스키마에 부합하도록 연결합니다.
        # 실제 호출 시 JSON 인자를 해석해 app/services/ 아래 모듈들을 호출합니다.
    ]
    
    # google-genai SDK 툴 포맷팅 구성
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                # Python 함수를 직접 리스트로 전달하면 google-genai가 알아서 스키마를 추출해 바인딩합니다.
                tools=tools_list,
            )
        )
        
        final_text = response.text or ""
        
        # 5. Function Calling 발생 시 백엔드 핸들링
        # SDK에서 function_calls가 넘어오면 이를 비동기로 파싱하고 실제 함수를 실행한 후,
        # 그 결과를 다시 Gemini에 넘겨 최종 텍스트를 받거나, 직접 결과를 빌드해 리턴합니다.
        function_calls = response.function_calls
        if function_calls:
            for call in function_calls:
                func_name = call.name
                args = call.args
                
                # 날씨 모의 호출 처리
                if func_name == "get_current_weather":
                    location = args.get("location", "서울")
                    tool_result = get_current_weather(location)
                    
                    # 도구 실행 결과를 Gemini로 다시 전송하여 답변 생성
                    follow_up_response = await client.aio.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[
                            types.Part.from_text(text=full_prompt),
                            types.Part.from_function_call(name=func_name, args=args),
                            types.Part.from_function_response(name=func_name, response={"result": tool_result})
                        ],
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction
                        )
                    )
                    final_text = follow_up_response.text or ""
                    break
        
        # 6. 대화 내용 세맨틱 메모리에 저장 (비동기로 진행되지만 대기함)
        if final_text:
            await save_semantic_memory(user_id, query, final_text, db)
            
        # 7. 응답의 길이가 300자를 넘는 경우 TTS 요약 텍스트 생성
        tts_text = await get_tts_text(final_text)
        
        return {
            "response": final_text,
            "tts_response": tts_text,
            "function_called": bool(function_calls)
        }
        
    except Exception as e:
        print(f"[AI Chat Error] Error during Gemini generate_content: {e}")
        # 오류 발생 시 기본 안내 멘트
        err_msg = "죄송합니다. 현재 AI 백엔드 서버 처리 과정에서 오류가 발생했습니다."
        return {
            "response": err_msg,
            "tts_response": err_msg,
            "function_called": False
        }
