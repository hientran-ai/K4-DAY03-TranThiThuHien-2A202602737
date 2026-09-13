"""CLI, bounded ReAct loop and evidence-based evaluation for Day 03."""
import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from mcp_server import MCPAcademicServer
from prompts import CHATBOT_BASELINE_PROMPT, REACT_AGENT_SYSTEM_PROMPT, MAX_ITERATIONS
from providers import get_llm_provider, ProviderError

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def load_test_cases():
    path = ROOT / "config/test_cases.json"
    if not path.exists():
        path = ROOT / "config/test_cases.example.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_waterfall_trace(trace_data, path=None):
    path = Path(path) if path else ROOT / "docs/trace_waterfall.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace_data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_baseline_chatbot(user_query, provider):
    return provider.generate(user_query, CHATBOT_BASELINE_PROMPT)


def run_react_agent(user_query, provider, mcp_server, test_id=None):
    history, logs = [], []
    started = time.perf_counter()
    run_id = str(uuid.uuid4())
    def event(step, action_type, **data):
        item = {"run_id": run_id, "test_id": test_id, "step": step, "query": user_query,
                "timestamp": datetime.now(timezone.utc).isoformat(), "provider": type(provider).__name__,
                "model": provider.model_name, "is_mock": provider.is_mock, "action_type": action_type,
                "elapsed_ms": round((time.perf_counter()-started)*1000, 3), **data}
        logs.append(item)
    for step in range(1, MAX_ITERATIONS+1):
        tick = time.perf_counter()
        try:
            response = provider.generate_with_tools(user_query, mcp_server.list_tools(), REACT_AGENT_SYSTEM_PROMPT, history)
        except ProviderError as exc:
            event(step, "ERROR", output=str(exc), latency_ms=round((time.perf_counter()-tick)*1000, 3))
            break
        model_ms = round((time.perf_counter()-tick)*1000, 3)
        thought = response.get("thought", "Đề xuất hành động.")
        if response.get("type") == "text" and response.get("content", "").strip():
            event(step, "FINAL_ANSWER", thought=thought, output=response["content"], latency_ms=model_ms)
            break
        calls = response.get("calls", [])
        if response.get("type") != "tool_calls" or not calls or len(calls) > 8:
            event(step, "ERROR", output="Phản hồi mô hình không hợp lệ hoặc có quá nhiều tool call.", latency_ms=model_ms)
            break
        event(step, "MODEL_DECISION", thought=thought, tools=[c["tool_name"] for c in calls], latency_ms=model_ms)
        results = []
        for call in calls:
            tick = time.perf_counter()
            observation = mcp_server.call_tool(call["tool_name"], call["arguments"])["result"]
            results.append(observation)
            event(step, "TOOL_EXECUTION", thought=thought, call_id=call["id"], tool_name=call["tool_name"],
                  arguments=call["arguments"], observation=observation,
                  latency_ms=round((time.perf_counter()-tick)*1000, 3))
        history.append({"native": response.get("native"), "calls": calls, "results": results})
    else:
        event(MAX_ITERATIONS, "MAX_ITERATIONS", output="Đã đạt giới hạn 5 vòng xử lý. Hãy chia nhỏ yêu cầu.", latency_ms=0)
    return logs


def evaluate_case(tc, logs):
    calls = [e for e in logs if e["action_type"] == "TOOL_EXECUTION"]
    expected = tc.get("expected_tools")
    checks = {"final_answer": bool(logs and logs[-1]["action_type"] == "FINAL_ANSWER" and logs[-1].get("output", "").strip()),
              "no_runtime_error": not any(e["action_type"] in ("ERROR", "MAX_ITERATIONS") for e in logs)}
    if expected is not None:
        checks["tool_sequence"] = [e["tool_name"] for e in calls] == expected
    for i, spec in enumerate(tc.get("expected_calls", [])):
        checks[f"call_{i+1}"] = i < len(calls) and all(calls[i]["arguments"].get(k) == v for k,v in spec.get("arguments", {}).items()) and calls[i]["observation"].get("status") == spec.get("status", "SUCCESS")
    return {"test_id": tc["id"], "passed": all(checks.values()), "checks": checks, "tool_count": len(calls),
            "answer": logs[-1].get("output", "") if logs else "", "is_mock": all(e["is_mock"] for e in logs)}


def run_suite(provider):
    traces, results = [], []
    for tc in load_test_cases():
        logs = run_react_agent(tc["question"], provider, MCPAcademicServer(), tc["id"])
        traces.extend(logs)
        results.append(evaluate_case(tc, logs))
    return {"provider": type(provider).__name__, "model": provider.model_name, "is_mock": provider.is_mock,
            "created_at": datetime.now(timezone.utc).isoformat(), "passed": sum(r["passed"] for r in results),
            "total": len(results), "tool_count": sum(r["tool_count"] for r in results), "results": results, "traces": traces}


def main():
    parser = argparse.ArgumentParser(description="Lốp Học Vụ · Day 03")
    parser.add_argument("--provider", choices=["mock", "gemini", "openai"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--query")
    args = parser.parse_args()
    try:
        provider = get_llm_provider(args.provider)
        print(f"Provider: {type(provider).__name__} | Model: {provider.model_name} | Mock: {provider.is_mock}")
        if args.all:
            suite = run_suite(provider)
            save_waterfall_trace(suite.pop("traces"))
            save_waterfall_trace(suite, ROOT / "docs/test_results.json")
            for r in suite["results"]:
                print(f"{r['test_id']}: {'PASS' if r['passed'] else 'FAIL'} | {r['tool_count']} tool | {r['answer']}")
            print(f"Kết quả: {suite['passed']}/{suite['total']}; {suite['tool_count']} tool calls; is_mock={suite['is_mock']}")
            return 0 if suite["passed"] == suite["total"] else 1
        all_logs = []
        while True:
            query = input("Bạn: ").strip() if args.interactive else args.query or load_test_cases()[3]["question"]
            if query.lower() in ("exit", "quit", ""):
                break
            if args.compare:
                print("Chatbot:", run_baseline_chatbot(query, provider))
            logs = run_react_agent(query, provider, MCPAcademicServer())
            all_logs.extend(logs)
            print(json.dumps(logs, ensure_ascii=False, indent=2))
            save_waterfall_trace(all_logs, ROOT / "docs/trace_interactive.json")
            if not args.interactive:
                return 0 if logs[-1]["action_type"] == "FINAL_ANSWER" else 1
        return 0
    except ProviderError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
