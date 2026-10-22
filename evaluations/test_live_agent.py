import asyncio
import json
import time
from datetime import date, datetime
from pathlib import Path
import re
import unicodedata

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.pipelineiq.agent import root_agent



APP_NAME = "pipelineiq_eval"
USER_ID = "evaluation_user"

PROMPT = (
    "Find five historical pipeline incidents in Texas. "
    "Show their incident IDs, dates and reported causes."
)

def normalize_text(value: object) -> str:
    """Normalize common Unicode and formatting differences."""
    text = unicodedata.normalize("NFKC", str(value))

    # Normalize Unicode dash characters to ASCII hyphen.
    text = re.sub(r"[\u2010-\u2015\u2212]", "-", text)

    # Normalize whitespace.
    text = " ".join(text.split())

    return text

async def main():
    session_service = InMemorySessionService()

    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    tool_calls = []
    tool_responses = []
    final_answer = ""

    start = time.perf_counter()

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=PROMPT)],
        ),
    ):
        for call in event.get_function_calls() or []:
            tool_calls.append({
                "name": call.name,
                "args": call.args,
            })

        for response in event.get_function_responses() or []:
            tool_responses.append({
                "name": response.name,
                "response": response.response,
            })

        if event.is_final_response() and event.content:
            final_answer = " ".join(
                part.text
                for part in event.content.parts or []
                if part.text
            )

    latency = round(time.perf_counter() - start, 2)

    print("\n=== TOOL CALLS ===")
    print(json.dumps(tool_calls, indent=2, default=str))

    print("\n=== FINAL ANSWER ===")
    print(final_answer)

    # Check that the agent actually used the search tool.
    search_calls = [
        call for call in tool_calls
        if call["name"] == "search_incidents"
    ]

    assert search_calls, "FAIL: Agent did not call search_incidents"

    assert any(
        str(call["args"].get("state", "")).upper() == "TX"
        and call["args"].get("limit", 5) == 5
        for call in search_calls
    ), "FAIL: Incorrect search parameters"

    search_results = [
        item["response"]
        for item in tool_responses
        if item["name"] == "search_incidents"
    ]

    assert search_results, "FAIL: No search tool response"

    records = []
    for result in search_results:
        if result.get("status") == "success":
            records.extend(result.get("records", []))

    assert len(records) >= 5, "FAIL: Fewer than 5 records returned"

    # Grounding check: incident IDs in the final answer must
    # belong to the tool response.
    valid_ids = {
        str(record["incident_id"]) for record in records
    }

    import re
    mentioned_ids = set(
        re.findall(r"\b20\d{6}\b", final_answer)
    )

    assert mentioned_ids, "FAIL: No incident IDs in final answer"

    assert mentioned_ids <= valid_ids, (
        f"FAIL: Unsupported IDs: {mentioned_ids - valid_ids}"
    )

    assert len(mentioned_ids) == 5, (
        f"FAIL: Expected 5 unique IDs, got {len(mentioned_ids)}"
    )

    # Each listed record must have its date and cause
    # somewhere in the final response.
    for record in records:
        if str(record["incident_id"]) not in mentioned_ids:
            continue

        incident_date = normalize_text(
            str(record["incident_date"])[:10]
        )

        cause = record.get("cause")

        normalized_answer = normalize_text(final_answer)

        assert incident_date in normalized_answer, (
            f"FAIL: Date missing for {record['incident_id']}"
        )

        if cause:
            assert normalize_text(cause).casefold() in (
                normalized_answer.casefold()
                ), (
                f"FAIL: Cause missing for {record['incident_id']}"
            )

    metrics = {
        "status": "PASS",
        "latency_seconds": latency,
        "tool_call_count": len(tool_calls),
        "grounded_incident_ids": len(mentioned_ids),
        "expected_state": "TX",
        "expected_limit": 5,
        "checks": [
            "tool_called",
            "correct_arguments",
            "tool_response_present",
            "incident_ids_grounded",
            "record_fields_present",
        ],
    }

    output = Path("evaluations/results")
    output.mkdir(parents=True, exist_ok=True)

    (output / "baseline.json").write_text(
        json.dumps(metrics, indent=2)
    )

    print("\n=== EVALUATION RESULTS ===")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
