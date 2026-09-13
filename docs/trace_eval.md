# Báo cáo thu hoạch Day 03 — Lốp Học Vụ

- Họ tên: Trần Thị Thu Hiền.
- Mã học viên: 2A202602737.
- Chủ đề: Trợ lý học vụ và đặt lịch tư vấn (dữ liệu minh họa VinUni).
- Thông tin học viên lấy theo tên thư mục dự án, cần đối chiếu trước khi nộp.
- Lần chạy: 2026-09-13T15:44:39.989034+00:00.
- Provider: `MockOfflineProvider`; model: `offline-simulator-v2`.
- Trạng thái nghiệm thu: **Mock Offline — CHƯA nghiệm thu API thật**.
- Kiểm tra API: Kết nối `gemini-3.6-flash`: PASS (OK); kiểm tra tool calling: BLOCKED: RESOURCE_EXHAUSTED (HTTP 429).

## 1. Agentic Fit

| Tiêu chí | Điểm | Giải trình |
|---|---:|---|
| Multi-step Reasoning | 4/5 | Tìm hồ sơ, đọc tên cố vấn rồi đặt lịch theo kết quả, sau đó tổng hợp. |
| Tool Interaction | 5/5 | Công cụ tra cứu cung cấp dữ liệu và công cụ đặt lịch tạo kết quả hành động mô phỏng. |
| Dynamic Decision | 4/5 | SUCCESS cho phép tiếp tục; NOT_FOUND dừng; thiếu dữ liệu phải hỏi bổ sung. |
| Long Horizon Goal | 3/5 | Giữ mục tiêu qua tối đa 5 vòng trong một yêu cầu; chưa có memory dài hạn. |
| Tổng | **16/20** | Phù hợp triển khai ReAct; không cần kiến trúc autonomous dài hạn. |

## 2. Thiết kế và phần đã hoàn thiện

- Schema của academic_query yêu cầu student_id; schedule_appointment yêu cầu student_id, datetime_str, advisor_name.
- MCPAcademicServer gọi router, parse JSON, đóng gói envelope theo quy ước lab. Đây là mô phỏng trong cùng process, không phải MCP transport production.
- ReAct nhận các tool call, thực thi, thêm kết quả vào lịch sử rồi gọi mô hình tiếp. Chỉ dừng khi có văn bản, lỗi hoặc hết 5 vòng.
- Gemini giữ nguyên native Content và thought signatures; OpenAI nối assistant tool calls với tool messages qua ID.
- Kiểm tra kiểu dữ liệu, trường bắt buộc, trường lạ, mã sinh viên, ngày giờ và tên cố vấn.
- Trace có run_id, test_id, provider, model, is_mock, step, hành động, observation và độ trễ đo bằng perf_counter.
- Thought chỉ là mô tả hành động do adapter tạo, không phải nội dung suy nghĩ nội bộ.
- Tool đặt lịch trả mã ổn định cho cùng nội dung; không gửi lịch thật, không lưu DB, không kiểm tra lịch bận.

## 3. Kết quả chạy thực tế

**5/5 test đạt; 5 lượt gọi tool.**

| Test | Kết quả | Tool calls | Phản hồi thực tế |
|---|---|---:|---|
| TC01 | PASS | 0 | Chào bạn! Tôi hỗ trợ tra cứu hồ sơ sinh viên và tạo lịch tư vấn mô phỏng. Demo chưa cung cấp quy chế VinUni chính thức; hãy hỏi phòng đào tạo về yêu cầu tốt nghiệp. |
| TC02 | PASS | 1 | Nguyễn Văn An (SV2026001): lớp AI-K4, GPA 3.85, email an.nv@vinuni.edu.vn, trạng thái Đang học. Cố vấn: PGS.TS Nguyễn Văn A. Dữ liệu minh họa. |
| TC03 | PASS | 1 | Đã tạo lịch hẹn mô phỏng BK-E5B722D385 cho SV2026001 với PGS.TS Nguyễn Văn A vào 14:00 15/09/2026. Chưa gửi đến nhà trường. |
| TC04 | PASS | 2 | Đã tạo lịch hẹn mô phỏng BK-BDF4DA7196 cho SV2026002 với TS. Lê Thị B vào 09:00 16/09/2026. Chưa gửi đến nhà trường. |
| TC05 | PASS | 1 | Không tìm thấy dữ liệu sinh viên có mã 'SV9999999' |

PASS dựa trên sự có mặt của Final Answer, không có lỗi runtime, chuỗi tool, tham số và status đúng kỳ vọng. Đây không phải chấm điểm ngữ nghĩa toàn bộ câu trả lời của LLM. Khi chạy live cần đọc lại từng câu trả lời.

## 4. Trace TC04 — trích từ file thực tế

```json
[
  {
    "run_id": "12f733d0-0bb1-4011-bbe1-beb20cb352a8",
    "test_id": "TC04",
    "step": 1,
    "query": "Hãy tra cứu cố vấn học tập của SV2026002, sau đó đặt lịch tư vấn với đúng cố vấn vào 09:00 16/09/2026.",
    "timestamp": "2026-09-13T15:44:39.989034+00:00",
    "provider": "MockOfflineProvider",
    "model": "offline-simulator-v2",
    "is_mock": true,
    "action_type": "MODEL_DECISION",
    "elapsed_ms": 0.039,
    "thought": "Gọi academic_query với dữ liệu từ yêu cầu hoặc kết quả đã nhận.",
    "tools": [
      "academic_query"
    ],
    "latency_ms": 0.014
  },
  {
    "run_id": "12f733d0-0bb1-4011-bbe1-beb20cb352a8",
    "test_id": "TC04",
    "step": 1,
    "query": "Hãy tra cứu cố vấn học tập của SV2026002, sau đó đặt lịch tư vấn với đúng cố vấn vào 09:00 16/09/2026.",
    "timestamp": "2026-09-13T15:44:39.989034+00:00",
    "provider": "MockOfflineProvider",
    "model": "offline-simulator-v2",
    "is_mock": true,
    "action_type": "TOOL_EXECUTION",
    "elapsed_ms": 0.068,
    "thought": "Gọi academic_query với dữ liệu từ yêu cầu hoặc kết quả đã nhận.",
    "call_id": "mock-1",
    "tool_name": "academic_query",
    "arguments": {
      "student_id": "SV2026002"
    },
    "observation": {
      "status": "SUCCESS",
      "student_id": "SV2026002",
      "data": {
        "full_name": "Trần Thị Bình",
        "class": "AI-K4",
        "gpa": 3.6,
        "email": "binh.tt@vinuni.edu.vn",
        "status": "Đang học",
        "advisor": "TS. Lê Thị B"
      }
    },
    "latency_ms": 0.024
  },
  {
    "run_id": "12f733d0-0bb1-4011-bbe1-beb20cb352a8",
    "test_id": "TC04",
    "step": 2,
    "query": "Hãy tra cứu cố vấn học tập của SV2026002, sau đó đặt lịch tư vấn với đúng cố vấn vào 09:00 16/09/2026.",
    "timestamp": "2026-09-13T15:44:39.989034+00:00",
    "provider": "MockOfflineProvider",
    "model": "offline-simulator-v2",
    "is_mock": true,
    "action_type": "MODEL_DECISION",
    "elapsed_ms": 0.086,
    "thought": "Gọi schedule_appointment với dữ liệu từ yêu cầu hoặc kết quả đã nhận.",
    "tools": [
      "schedule_appointment"
    ],
    "latency_ms": 0.013
  },
  {
    "run_id": "12f733d0-0bb1-4011-bbe1-beb20cb352a8",
    "test_id": "TC04",
    "step": 2,
    "query": "Hãy tra cứu cố vấn học tập của SV2026002, sau đó đặt lịch tư vấn với đúng cố vấn vào 09:00 16/09/2026.",
    "timestamp": "2026-09-13T15:44:39.989034+00:00",
    "provider": "MockOfflineProvider",
    "model": "offline-simulator-v2",
    "is_mock": true,
    "action_type": "TOOL_EXECUTION",
    "elapsed_ms": 0.131,
    "thought": "Gọi schedule_appointment với dữ liệu từ yêu cầu hoặc kết quả đã nhận.",
    "call_id": "mock-2",
    "tool_name": "schedule_appointment",
    "arguments": {
      "student_id": "SV2026002",
      "datetime_str": "09:00 16/09/2026",
      "advisor_name": "TS. Lê Thị B"
    },
    "observation": {
      "status": "SUCCESS",
      "booking_id": "BK-BDF4DA7196",
      "simulated": true,
      "student_id": "SV2026002",
      "datetime": "09:00 16/09/2026",
      "advisor": "TS. Lê Thị B",
      "message": "Đã tạo lịch hẹn mô phỏng BK-BDF4DA7196 cho SV2026002 với TS. Lê Thị B vào 09:00 16/09/2026. Chưa gửi đến nhà trường."
    },
    "latency_ms": 0.042
  },
  {
    "run_id": "12f733d0-0bb1-4011-bbe1-beb20cb352a8",
    "test_id": "TC04",
    "step": 3,
    "query": "Hãy tra cứu cố vấn học tập của SV2026002, sau đó đặt lịch tư vấn với đúng cố vấn vào 09:00 16/09/2026.",
    "timestamp": "2026-09-13T15:44:39.989034+00:00",
    "provider": "MockOfflineProvider",
    "model": "offline-simulator-v2",
    "is_mock": true,
    "action_type": "FINAL_ANSWER",
    "elapsed_ms": 0.152,
    "thought": "Tổng hợp thông tin có sẵn để trả lời.",
    "output": "Đã tạo lịch hẹn mô phỏng BK-BDF4DA7196 cho SV2026002 với TS. Lê Thị B vào 09:00 16/09/2026. Chưa gửi đến nhà trường.",
    "latency_ms": 0.014
  }
]
```

## 5. Kiểm thử bổ sung

Chạy `.venv/Scripts/python.exe -m unittest discover -s tests -v` để kiểm tra các trường hợp lỗi và hợp đồng dữ liệu SDK. Test SDK dùng response giả để kiểm tra message history, không chứng minh đã gọi API thật.

## 6. Nghiệm thu và nộp bài

- [ ] Chạy đủ test bằng Gemini/OpenAI thật. Trạng thái hiện tại: Mock Offline — CHƯA nghiệm thu API thật.
- [x] Key Gemini được nhận diện và câu kiểm tra không chứa hồ sơ trả `OK`; chưa chạy suite live do HTTP 429 hết hạn mức.
- [x] Hoàn thiện schema, server mô phỏng, vòng lặp, 5 test cases và demo.
- [x] Có trace và kết quả test sinh từ chương trình.
- [ ] Đọc lại câu trả lời live và đối chiếu yêu cầu giảng viên.
- [x] Repository đã sẵn sàng để commit/push; học viên dùng link GitHub để nộp trên LMS.

Lệnh nghiệm thu sau khi nhập key vào .env: `.venv/Scripts/python.exe src/app.py --provider gemini --all`, sau đó `.venv/Scripts/python.exe scripts/generate_report.py`.
Nếu chọn OpenAI, dùng `--provider openai` và đặt LLM_MODEL phù hợp (hoặc để trống). Tuyệt đối không đưa .env/API key vào bài nộp.
