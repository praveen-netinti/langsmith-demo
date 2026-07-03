import json
import uuid
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

client = Client()

PROJECT_NAME = "langsmith-demo"


def str_to_uuid(s: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, s))


def parse_time(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def make_dotted_order(start_time: datetime, run_id: str) -> str:
    return start_time.strftime("%Y%m%dT%H%M%S%fZ") + run_id


def post_traces(traces: list[dict]):
    # Shift ALL traces to fit within last 23 hours (compress the week into 23h)
    now = datetime.now(timezone.utc)
    all_times = [parse_time(t["startTime"]) for t in traces]
    max_time = max(all_times)
    min_time = min(all_times)
    original_span = (max_time - min_time).total_seconds()

    # Map entire range into last 23 hours
    target_span = 23 * 3600  # 23 hours in seconds
    target_end = now - timedelta(minutes=2)

    def shift(dt: datetime) -> datetime:
        elapsed = (dt - min_time).total_seconds()
        ratio = elapsed / original_span if original_span > 0 else 0
        return target_end - timedelta(seconds=target_span * (1 - ratio))

    for i, trace in enumerate(traces):
        spans = trace["spans"]
        root = next((s for s in spans if s["parentId"] is None), spans[0])

        # Root span ID = trace_id (required by LangSmith)
        trace_id = str_to_uuid(root["id"])
        tags = trace.get("tags", [])
        metadata = trace.get("metadata", {})
        metadata["trace_name"] = trace["name"]
        metadata["original_trace_id"] = trace["id"]

        # Build span ID map and dotted orders
        span_ids = {}
        dotted_orders = {}
        start_times = {}

        for span in spans:
            if span["id"] == root["id"]:
                span_ids[span["id"]] = trace_id
            else:
                span_ids[span["id"]] = str_to_uuid(span["id"])
            start_times[span["id"]] = shift(parse_time(span["startTime"]))

        # Compute dotted_orders
        for span in spans:
            run_id = span_ids[span["id"]]
            st = start_times[span["id"]]
            current = make_dotted_order(st, run_id)

            if span["parentId"] is None:
                dotted_orders[span["id"]] = current
            else:
                parent_do = dotted_orders.get(span["parentId"])
                if parent_do:
                    dotted_orders[span["id"]] = parent_do + "." + current
                else:
                    # Parent not in this trace (orphan) — use root's dotted_order
                    root_do = dotted_orders[root["id"]]
                    dotted_orders[span["id"]] = root_do + "." + current

        for span in spans:
            run_id = span_ids[span["id"]]
            is_root = span["parentId"] is None
            st = start_times[span["id"]]

            kwargs = {
                "id": run_id,
                "trace_id": trace_id,
                "dotted_order": dotted_orders[span["id"]],
                "start_time": st,
                "tags": tags if is_root else [],
                "extra": {"metadata": metadata.copy()} if is_root else {},
            }

            if not is_root:
                parent_id = span["parentId"]
                if parent_id in span_ids:
                    kwargs["parent_run_id"] = span_ids[parent_id]
                else:
                    kwargs["parent_run_id"] = trace_id

            if span.get("endTime"):
                kwargs["end_time"] = shift(parse_time(span["endTime"]))

            if span.get("output") is not None:
                kwargs["outputs"] = span["output"]
            elif span["status"] == "success":
                kwargs["outputs"] = {"ok": True}

            if span.get("error"):
                kwargs["error"] = span["error"]

            if span["type"] == "llm" and span.get("model"):
                extra = kwargs.get("extra", {})
                extra.setdefault("metadata", {})
                extra["metadata"]["ls_model_name"] = span["model"]
                extra["metadata"]["ls_provider"] = "openai" if "gpt" in span.get("model", "") else "anthropic"
                if span.get("promptTokens") is not None:
                    extra["metadata"]["ls_prompt_tokens"] = span["promptTokens"]
                    extra["metadata"]["ls_completion_tokens"] = span.get("completionTokens", 0)
                    extra["metadata"]["ls_total_tokens"] = span.get("totalTokens", 0)
                    extra["metadata"]["ls_cost"] = span.get("costUsd")
                kwargs["extra"] = extra

            # Map unsupported run_types to valid ones
            run_type = span["type"]
            if run_type == "guardrail":
                run_type = "tool"

            client.create_run(
                name=span["name"],
                inputs=span.get("input") or {},
                run_type=run_type,
                project_name=PROJECT_NAME,
                **kwargs,
            )

        # Feedback
        if trace.get("feedback"):
            fb = trace["feedback"]
            client.create_feedback(
                run_id=trace_id,
                key="user_rating",
                score=fb.get("score"),
                value=fb.get("rating"),
                comment=fb.get("comment"),
            )

        print(f"  [{i+1}/{len(traces)}] {trace['name']} ({trace['status']})")


if __name__ == "__main__":
    with open("traces.json") as f:
        data = json.load(f)

    traces = data["traces"]
    print(f"Posting {len(traces)} traces to LangSmith project '{PROJECT_NAME}'...")
    post_traces(traces)
    print("Done.")
