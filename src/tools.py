"""
🛠️ TOOL DEFINITIONS & EXECUTION BACKEND
Mã nguồn chứa danh sách Tool Schemas (JSON Schema) và Execution Layer phục vụ cho MCP Server.
"""

import json
from datetime import datetime
from hashlib import sha256
from typing import Dict, Any

# ==============================================================================
# 1. KHAI BÁO TOOL SCHEMAS CHUẨN NATIVE JSON SCHEMA (TASK 1.2)
# ==============================================================================

TOOLS_SCHEMA = [
    # Tool 1: Đã được định nghĩa mẫu sẵn cho Học viên tham khảo
    {
        "name": "academic_query",
        "description": "Tra cứu hồ sơ và thông tin học vụ của sinh viên VinUni bằng mã sinh viên.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần tra cứu (ví dụ: 'SV2026001')"
                }
            },
            "required": ["student_id"]
        }
    },
    
    # --------------------------------------------------------------------------
    # TASK 1.2 hoàn thiện: schema của schedule_appointment.
    # 🎯 YÊU CẦU THIẾT KẾ SCHEMA (JSON SCHEMA STANDARD):
    # 1. Tool dùng để đặt lịch hẹn tư vấn học vụ với Cố vấn học tập VinUni.
    # 2. Thiết kế các tham số (properties) để LLM trích xuất:
    #    - student_id (string): Mã sinh viên cần đặt lịch (ví dụ: 'SV2026001')
    #    - datetime_str (string): Thời gian hẹn (ví dụ: '14:00 15/09/2026')
    #    - advisor_name (string): Tên cố vấn học tập
    # 3. Khai báo danh sách các trường bắt buộc (required).
    # --------------------------------------------------------------------------
    {
        "name": "schedule_appointment",
        "description": "Đặt lịch hẹn tư vấn học vụ với Cố vấn học tập VinUni.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {"type": "string", "description": "Mã sinh viên, ví dụ SV2026001"},
                "datetime_str": {"type": "string", "description": "Thời gian theo HH:MM DD/MM/YYYY, ví dụ 14:00 15/09/2026"},
                "advisor_name": {"type": "string", "description": "Tên cố vấn do người dùng cung cấp hoặc đã tra cứu bằng academic_query. Không tự đoán."}
            },
            "required": ["student_id", "datetime_str", "advisor_name"],
            "additionalProperties": False
        }
    }
]

# ==============================================================================
# 2. MÔ PHỎNG DỮ LIỆU & HÀM THỰC THI TOOL (EXECUTION LAYER)
# ==============================================================================

MOCK_DATABASE = {
    "SV2026001": {
        "full_name": "Nguyễn Văn An",
        "class": "AI-K4",
        "gpa": 3.85,
        "email": "an.nv@vinuni.edu.vn",
        "status": "Đang học",
        "advisor": "PGS.TS Nguyễn Văn A"
    },
    "SV2026002": {
        "full_name": "Trần Thị Bình",
        "class": "AI-K4",
        "gpa": 3.60,
        "email": "binh.tt@vinuni.edu.vn",
        "status": "Đang học",
        "advisor": "TS. Lê Thị B"
    }
}


def execute_academic_query(student_id: str) -> str:
    """Thực thi tra cứu học vụ theo mã sinh viên"""
    student = MOCK_DATABASE.get(student_id.strip().upper())
    if student:
        return json.dumps({
            "status": "SUCCESS",
            "student_id": student_id,
            "data": student
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "status": "NOT_FOUND",
            "message": f"Không tìm thấy dữ liệu sinh viên có mã '{student_id}'"
        }, ensure_ascii=False)


def execute_schedule_appointment(student_id: str, datetime_str: str, advisor_name: str = "PGS.TS Nguyễn Văn A") -> str:
    """Thực thi đặt lịch hẹn tư vấn học vụ"""
    student_id = student_id.strip().upper()
    if student_id not in MOCK_DATABASE:
        return execute_academic_query(student_id)
    try:
        parsed = datetime.strptime(datetime_str, "%H:%M %d/%m/%Y")
    except ValueError:
        return json.dumps({"status": "INVALID_ARGUMENTS", "message": "Thời gian phải hợp lệ và theo HH:MM DD/MM/YYYY."}, ensure_ascii=False)
    if advisor_name.strip().casefold() != MOCK_DATABASE[student_id]["advisor"].casefold():
        return json.dumps({"status": "INVALID_ARGUMENTS", "message": "Cố vấn không khớp hồ sơ sinh viên. Hãy tra cứu lại."}, ensure_ascii=False)
    datetime_str = parsed.strftime("%H:%M %d/%m/%Y")
    # Mã xác định theo nội dung: gọi lại cùng yêu cầu không tạo mã mới.
    booking_id = "BK-" + sha256(f"{student_id}|{datetime_str}|{advisor_name.strip().casefold()}".encode()).hexdigest()[:10].upper()
    return json.dumps({
        "status": "SUCCESS",
        "booking_id": booking_id,
        "simulated": True,
        "student_id": student_id,
        "datetime": datetime_str,
        "advisor": advisor_name,
        "message": f"Đã tạo lịch hẹn mô phỏng {booking_id} cho {student_id} với {advisor_name} vào {datetime_str}. Chưa gửi đến nhà trường."
    }, ensure_ascii=False)


# Router gọi tool thực tế
TOOL_ROUTER = {
    "academic_query": execute_academic_query,
    "schedule_appointment": execute_schedule_appointment
}

def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Hàm trung chuyển thực thi tool"""
    schema = next((s for s in TOOLS_SCHEMA if s["name"] == tool_name), None)
    if schema:
        props = schema["parameters"]["properties"]
        if not isinstance(arguments, dict) or any(k not in props for k in arguments):
            return json.dumps({"status": "INVALID_ARGUMENTS", "message": "Tham số phải là object và chỉ chứa các trường trong schema."}, ensure_ascii=False)
        required = schema["parameters"]["required"]
        if any(k not in arguments for k in required) or any(not isinstance(v, str) or not v.strip() for v in arguments.values()):
            return json.dumps({"status": "INVALID_ARGUMENTS", "message": "Thiếu tham số bắt buộc hoặc tham số không phải chuỗi có nội dung."}, ensure_ascii=False)
    if tool_name in TOOL_ROUTER:
        try:
            return TOOL_ROUTER[tool_name](**arguments)
        except Exception as e:
            return json.dumps({"status": "EXECUTION_ERROR", "error": str(e)}, ensure_ascii=False)
    return json.dumps({"status": "UNKNOWN_TOOL", "error": f"Tool '{tool_name}' không tồn tại!"}, ensure_ascii=False)
