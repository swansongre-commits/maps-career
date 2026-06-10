# -*- coding: utf-8 -*-
"""
LLM 발화 이해 어댑터 (선택적 A단계)

학생 자유 발화 → GPT → 진로 관심 키워드(긍정) / 제외 키워드(부정) 추출.
- 환경변수 OPENAI_API_KEY 가 있을 때만 동작. 없거나 호출 실패 시 available()=False
  이거나 extract()가 None을 반환 → 호출부(recommender)가 규칙 기반으로 폴백.
- 추상 발화("사람 돕는 일", "남을 가르치는 직업")처럼 명사 토크나이저가 약한
  입력을 표준 키워드로 변환하는 것이 목적.
- 프롬프트 인젝션 대비: 출력은 JSON 강제 + 길이/개수/문자 검증으로 정제.
"""
import os
import re
import json

# .env 파일에서 OPENAI_API_KEY 자동 로드(있으면). 미설치/파일없음이면 조용히 무시.
# encoding="utf-8-sig" 로 BOM(메모장·PowerShell이 붙이는 경우)도 안전하게 처리.
try:
    from dotenv import load_dotenv
    _ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_ENV_PATH, encoding="utf-8-sig")
except Exception:
    pass

MODEL_DEFAULT = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

SYSTEM_PROMPT = """당신은 한국 학생(어린이~고등학생)의 진로 관심사 발화를 분석해 키워드를 뽑는 도우미입니다.

규칙:
1. 학생이 **긍정적으로 관심을 보인** 분야·활동·대상의 핵심 키워드만 뽑으세요.
2. **부정 표현(~는 싫어요, 별로예요, 안 맞아요, 하기 싫어요) 안의 단어는 긍정에서 빼고 부정 목록에 넣으세요.**
3. 키워드는 **명사형 표준 용어**로 바꾸세요. 어린이의 쉬운 말도 학과·직업에서 쓰는 표준어로 정규화하세요.
   - "AI"→"인공지능", "똑똑한 기계"→"인공지능"·"로봇", "아픈 사람 고치기"→"의학"·"치료",
     "남 도와주기"→"사회복지"·"상담", "남 가르치기"→"교육", "별 보기"→"천문"·"우주"
4. 긍정 키워드는 3~7개. 각 키워드는 공백 없는 1~4어절 명사.
5. 반드시 아래 JSON 으로만 답하세요(설명 금지).

{"긍정_키워드": ["..."], "부정_제외": ["..."], "근거": "한 줄 요약"}
"""

_TERM_RE = re.compile(r"[^가-힣A-Za-z0-9]")


def get_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "").strip()


def available() -> bool:
    return bool(get_api_key())


def _clean_terms(seq, limit=10):
    out = []
    for t in seq or []:
        if not isinstance(t, str):
            continue
        t = _TERM_RE.sub("", t).strip()
        if 1 <= len(t) <= 20 and t not in out:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def extract(speech: str, model: str = MODEL_DEFAULT):
    """발화 → {'pos':[...], 'neg':[...], 'rationale':str} 또는 None(실패/키없음)."""
    if not available():
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=get_api_key())
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",
                 "content": f"[학생 발화]\n{str(speech)[:2000]}"},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        return {
            "pos": _clean_terms(data.get("긍정_키워드")),
            "neg": _clean_terms(data.get("부정_제외")),
            "rationale": str(data.get("근거", ""))[:200],
        }
    except Exception as e:  # 키 오류·네트워크·JSON 등 모든 실패 → 폴백
        return {"error": str(e)[:200]}


if __name__ == "__main__":
    print("API key present:", available())
    if available():
        print(extract("남을 도와주고 이야기 들어주는 일이 좋아요. 계산하는 건 싫어요."))
