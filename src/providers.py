"""Native tool conversations. Live API errors never silently fall back to Mock."""
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class ProviderError(RuntimeError):
    pass


class BaseLLMProvider:
    is_mock = False

    def generate(self, prompt, system_prompt=""):
        return self.generate_with_tools(prompt, [], system_prompt, []).get("content", "")

    def generate_with_tools(self, prompt, tools_schema, system_prompt="", history=None):
        raise NotImplementedError


def text_response(content):
    return {"type": "text", "content": content, "thought": "Tổng hợp thông tin có sẵn để trả lời."}


class MockOfflineProvider(BaseLLMProvider):
    """Rule-based simulator, not a language model. State arrives through history."""
    is_mock = True
    model_name = "offline-simulator-v2"

    def generate(self, prompt, system_prompt=""):
        return "Tôi có thể hướng dẫn học vụ chung, nhưng không có công cụ truy cập hồ sơ hoặc tạo lịch hẹn. Demo chưa có tài liệu quy chế chính thức; hãy xác nhận quy định với phòng đào tạo."

    def generate_with_tools(self, prompt, tools_schema, system_prompt="", history=None):
        history = history or []
        lower = prompt.casefold()
        student_match = re.search(r"\bSV\d+\b", prompt, re.I)
        booking = any(word in lower for word in ("đặt lịch", "hẹn tư vấn", "lịch hẹn"))
        if not (booking or student_match or "tra cứu" in lower):
            return text_response("Chào bạn! Tôi hỗ trợ tra cứu hồ sơ sinh viên và tạo lịch tư vấn mô phỏng. Demo chưa cung cấp quy chế VinUni chính thức; hãy hỏi phòng đào tạo về yêu cầu tốt nghiệp.")
        if not student_match:
            return text_response("Bạn vui lòng cung cấp mã sinh viên cần tra cứu hoặc đặt lịch.")
        student_id = student_match.group().upper()
        time_match = re.search(r"\b(\d{1,2}:\d{2})\b", prompt)
        date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", prompt)
        advisor_match = re.search(r"với\s+((?:PGS\.?\s*TS\.?|TS\.?)[^,\n]+?)(?=\s+vào|,|$)", prompt, re.I)
        explicit_advisor = advisor_match.group(1).strip().rstrip(".") if advisor_match else None
        observed = [r for turn in history for r in turn["results"]]
        if observed:
            latest = observed[-1]
            if latest.get("status") != "SUCCESS":
                return text_response(latest.get("message", "Công cụ báo lỗi; vui lòng kiểm tra lại yêu cầu."))
            if "booking_id" in latest:
                return text_response(latest["message"])
            if not booking:
                d = latest["data"]
                return text_response(f"{d['full_name']} ({latest['student_id']}): lớp {d['class']}, GPA {d['gpa']}, email {d['email']}, trạng thái {d['status']}. Cố vấn: {d['advisor']}. Dữ liệu minh họa.")
        if booking and (not time_match or not date_match):
            return text_response("Bạn vui lòng cung cấp đủ giờ và ngày hẹn, ví dụ 14:00 15/09/2026.")
        multi_step = "tra cứu" in lower or "sau đó" in lower
        if booking and (observed or (explicit_advisor and not multi_step)):
            advisor = observed[-1]["data"]["advisor"] if observed else explicit_advisor
            name = "schedule_appointment"
            args = {"student_id": student_id, "datetime_str": f"{time_match.group()} {date_match.group()}", "advisor_name": advisor}
        else:
            name, args = "academic_query", {"student_id": student_id}
        return {"type": "tool_calls", "calls": [{"id": f"mock-{len(history)+1}", "tool_name": name, "arguments": args}],
                "thought": f"Gọi {name} với dữ liệu từ yêu cầu hoặc kết quả đã nhận."}


def configured_key(name):
    value = os.getenv(name, "").strip()
    return value if value and not value.startswith("your_") else None


def gemini_compatible_schema(tool):
    """Gemini Developer API rejects JSON Schema additionalProperties."""
    result = deepcopy(tool)
    def clean(value):
        if isinstance(value, dict):
            value.pop("additionalProperties", None)
            for child in value.values():
                clean(child)
        elif isinstance(value, list):
            for child in value:
                clean(child)
    clean(result)
    return result


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key=None, model=None):
        from openai import OpenAI
        key = api_key or configured_key("OPENAI_API_KEY")
        if not key:
            raise ProviderError("Chưa có OPENAI_API_KEY hợp lệ trong .env.")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        self.client = OpenAI(api_key=key, timeout=45, max_retries=1)

    def generate_with_tools(self, prompt, tools_schema, system_prompt="", history=None):
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
        for turn in history or []:
            messages.append(turn["native"])
            for call, result in zip(turn["calls"], turn["results"]):
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})
        params = {"model": self.model_name, "messages": messages}
        if tools_schema:
            params.update(tools=[{"type": "function", "function": t} for t in tools_schema], tool_choice="auto", parallel_tool_calls=False)
        try:
            response = self.client.chat.completions.create(**params)
            msg = response.choices[0].message
            if msg.tool_calls:
                calls = [{"id": c.id, "tool_name": c.function.name, "arguments": json.loads(c.function.arguments)} for c in msg.tool_calls]
                return {"type": "tool_calls", "calls": calls, "native": msg.model_dump(exclude_none=True),
                        "thought": "Mô hình đề xuất công cụ: " + ", ".join(c["tool_name"] for c in calls)}
            if not msg.content:
                raise ProviderError("OpenAI trả về câu trả lời rỗng.")
            return text_response(msg.content)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"OpenAI API thất bại ({type(exc).__name__}). Kiểm tra model, API key, hạn mức và kết nối; không chuyển sang Mock.") from exc


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key=None, model=None):
        from google import genai
        from google.genai import types
        key = api_key or configured_key("GEMINI_API_KEY")
        if not key:
            raise ProviderError("Chưa có GEMINI_API_KEY hợp lệ trong .env.")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-3.6-flash"
        self.client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=45000))

    def generate_with_tools(self, prompt, tools_schema, system_prompt="", history=None):
        from google.genai import types
        contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        for turn in history or []:
            # Preserve native Content including opaque thought signatures.
            contents.append(turn["native"])
            parts = [types.Part(function_response=types.FunctionResponse(name=c["tool_name"], id=c.get("native_id"), response=r))
                     for c, r in zip(turn["calls"], turn["results"])]
            contents.append(types.Content(role="user", parts=parts))
        config = types.GenerateContentConfig(system_instruction=system_prompt or None,
            tools=[types.Tool(function_declarations=[gemini_compatible_schema(t) for t in tools_schema])] if tools_schema else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True), temperature=0.2)
        try:
            response = self.client.models.generate_content(model=self.model_name, contents=contents, config=config)
            if not response.candidates or not response.candidates[0].content:
                raise ProviderError("Gemini không trả về nội dung khả dụng.")
            content = response.candidates[0].content
            calls = []
            for i, part in enumerate(content.parts or []):
                c = part.function_call
                if c:
                    calls.append({"id": c.id or f"gemini-{len(history or [])}-{i}", "native_id": c.id,
                                  "tool_name": c.name, "arguments": dict(c.args or {})})
            if calls:
                return {"type": "tool_calls", "calls": calls, "native": content,
                        "thought": "Mô hình đề xuất công cụ: " + ", ".join(c["tool_name"] for c in calls)}
            answer = "\n".join(p.text for p in content.parts or [] if p.text and not p.thought)
            if not answer:
                raise ProviderError("Gemini trả về câu trả lời rỗng.")
            return text_response(answer)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Gemini API thất bại ({type(exc).__name__}). Kiểm tra model, API key, hạn mức và kết nối; không chuyển sang Mock.") from exc


def get_llm_provider(provider_type=None):
    kind = (provider_type or os.getenv("LLM_PROVIDER", "mock")).lower()
    if kind == "mock":
        return MockOfflineProvider()
    if kind == "gemini":
        return GeminiProvider()
    if kind == "openai":
        return OpenAIProvider()
    raise ProviderError(f"Provider '{kind}' không được hỗ trợ. Chọn mock, gemini hoặc openai.")
