import json
import re

import ollama

from backend.config import OLLAMA_MODEL, MAX_AGENT_STEPS
from backend.tools import (
    TOOLS,
    analyze_dependencies,
    check_schedule_conflicts,
    choose_best_recovery,
    create_communication,
    evaluate_recovery_options,
    generate_ai_recovery_options,
    generate_replanned_schedule,
    get_current_trip,
    resolve_event_id,
    simulate_flight_disruption,
)


SYSTEM_PROMPT = """
You are TripRescue AI, an autonomous travel disruption
and replanning agent.

Your job is to understand a travel disruption expressed
in natural language and autonomously recover the journey.

The user should NOT need to provide:
- event IDs
- flight IDs
- backup flight details
- dependency information
- tool names
- JSON

First inspect the current journey.

IMPORTANT:
- Never invent event IDs.
- Always read the actual event IDs from get_current_trip.
- If the user mentions a flight disruption, identify the
  flight automatically.
- Never send placeholders such as "flight ID",
  "changed flight ID", or "cancelled flight ID".
- If there is only one flight, use that flight automatically.

The autonomous workflow is:

1. Get current itinerary.
2. Understand the disruption.
3. Identify the affected flight.
4. Simulate the disruption.
5. Analyze the dependency graph.
6. Check schedule conflicts.
7. Generate AI recovery flight scenarios.
8. Evaluate the scenarios against downstream constraints.
9. Select the least disruptive feasible scenario.
10. Generate the revised itinerary.
11. Prepare a traveler communication.

Recovery flights are SIMULATED AI scenarios only.
There is no live airline booking API.

The deterministic Python tools are responsible for:
- dependency traversal
- time calculations
- conflict detection
- schedule propagation
- recovery evaluation

You are responsible for:
- understanding natural language
- orchestration
- recovery reasoning
- communication.

Do not ask the user for information that can be inferred
from the current itinerary.
"""


def _extract_json(text):
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL
    )

    if match:
        try:
            return json.loads(
                match.group(0)
            )
        except json.JSONDecodeError:
            return None

    return None


def detect_delay_from_message(message):
    text = message.lower()

    patterns = [
        r"(\d+)\s*(?:hour|hours|hr|hrs)\s*(?:delay|late)",
        r"(?:delay|delayed|late)\s*(?:by|for)?\s*(\d+)\s*(?:hour|hours|hr|hrs)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text
        )

        if match:
            return int(
                match.group(1)
            ) * 60

    minute_patterns = [
        r"(\d+)\s*(?:minute|minutes|min|mins)\s*(?:delay|late)",
        r"(?:delay|delayed|late)\s*(?:by|for)?\s*(\d+)\s*(?:minute|minutes|min|mins)",
    ]

    for pattern in minute_patterns:
        match = re.search(
            pattern,
            text
        )

        if match:
            return int(
                match.group(1)
            )

    return 0


def is_cancellation(message):
    text = message.lower()

    words = [
        "cancelled",
        "canceled",
        "cancel",
        "flight was cancelled",
        "flight was canceled",
    ]

    return any(
        word in text
        for word in words
    )


def detect_disruption_with_ai(message, trip):
    flights = [
        event
        for event in trip.get("events", [])
        if event.get("type") == "flight"
    ]

    flight = (
        flights[0]
        if flights
        else None
    )

    default_delay = detect_delay_from_message(
        message
    )

    default_cancelled = is_cancellation(
        message
    )

    prompt = f"""
Analyze this travel disruption.

User message:
{message}

Current flight:
{json.dumps(flight, indent=2)}

Return ONLY JSON:

{{
  "disruption_type": "delay" or "cancellation",
  "delay_minutes": 0,
  "cancelled": false,
  "flight_id": "actual flight id from itinerary"
}}

Rules:
- Use the actual flight ID.
- If the user says 3 hours, delay_minutes must be 180.
- If no delay amount is explicitly given, use 0.
- Cancellation should set cancelled to true.
"""

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze travel disruption "
                        "messages and return JSON only."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            format="json"
        )

        content = response.get(
            "message",
            {}
        ).get(
            "content",
            ""
        )

        parsed = _extract_json(
            content
        )

        if isinstance(parsed, dict):
            delay = parsed.get(
                "delay_minutes",
                default_delay
            )

            try:
                delay = int(delay)
            except (ValueError, TypeError):
                delay = default_delay

            return {
                "disruption_type": parsed.get(
                    "disruption_type",
                    "cancellation"
                    if default_cancelled
                    else "delay"
                ),
                "delay_minutes": max(
                    delay,
                    0
                ),
                "cancelled": bool(
                    parsed.get(
                        "cancelled",
                        default_cancelled
                    )
                ),
                "flight_id": resolve_event_id(
                    parsed.get("flight_id")
                ),
            }

    except Exception:
        pass

    return {
        "disruption_type": (
            "cancellation"
            if default_cancelled
            else "delay"
        ),
        "delay_minutes": default_delay,
        "cancelled": default_cancelled,
        "flight_id": resolve_event_id(),
    }


def execute_tool(
    tool_name,
    arguments
):
    if not isinstance(arguments, dict):
        arguments = {}

    if tool_name in {
        "analyze_dependencies",
        "simulate_flight_disruption",
        "check_schedule_conflicts",
        "generate_ai_recovery_options",
        "evaluate_recovery_options",
        "generate_replanned_schedule",
    }:
        if "flight_id" in arguments:
            arguments["flight_id"] = resolve_event_id(
                arguments.get("flight_id")
            )

        if "event_id" in arguments:
            arguments["event_id"] = resolve_event_id(
                arguments.get("event_id")
            )

    tool = TOOLS.get(tool_name)

    if not tool:
        return {
            "success": False,
            "message": f"Unknown tool: {tool_name}"
        }

    try:
        return tool(**arguments)

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
        }


def _run_recovery_fallback(
    message,
    disruption
):
    workflow = []

    trip = get_current_trip()

    workflow.append({
        "id": "stepDisruption",
        "status": "complete",
        "title": "Disruption detected",
        "detail": message,
    })

    flight_id = disruption.get(
        "flight_id"
    )

    delay_minutes = disruption.get(
        "delay_minutes",
        0
    )

    cancelled = disruption.get(
        "cancelled",
        False
    )

    simulation = simulate_flight_disruption(
        flight_id=flight_id,
        delay_minutes=delay_minutes,
        cancelled=cancelled
    )

    workflow.append({
        "id": "stepImpact",
        "status": "active",
        "title": "Impact analyzed",
        "detail": "Tracing dependency chain..."
    })

    impact = analyze_dependencies(
        flight_id
    )

    conflicts = check_schedule_conflicts(
        flight_id
    )

    workflow.append({
        "id": "stepImpact",
        "status": "complete",
        "title": "Impact analyzed",
        "detail": (
            f"{impact.get('dependency_count', 0)} "
            "downstream event(s) affected."
        ),
    })

    workflow.append({
        "id": "stepRecovery",
        "status": "active",
        "title": "Recovery options generated",
        "detail": "AI is generating simulated alternatives..."
    })

    recovery = generate_ai_recovery_options(
        flight_id=flight_id,
        cancelled=cancelled
    )

    workflow.append({
        "id": "stepRecovery",
        "status": "complete",
        "title": "Recovery options generated",
        "detail": (
            f"{len(recovery.get('options', []))} "
            "AI recovery scenarios generated."
        ),
    })

    workflow.append({
        "id": "stepConstraints",
        "status": "active",
        "title": "Constraints evaluated",
        "detail": "Checking downstream schedule conflicts..."
    })

    evaluation = evaluate_recovery_options(
        flight_id
    )

    workflow.append({
        "id": "stepConstraints",
        "status": "complete",
        "title": "Constraints evaluated",
        "detail": "Recovery scenarios evaluated."
    })

    workflow.append({
        "id": "stepSelected",
        "status": "active",
        "title": "Recovery selected",
        "detail": "Selecting least disruptive feasible option..."
    })

    selected = choose_best_recovery()

    workflow.append({
        "id": "stepSelected",
        "status": "complete",
        "title": "Recovery selected",
        "detail": (
            selected.get("selected", {}).get(
                "flight_name",
                "Recovery option"
            )
        ),
    })

    workflow.append({
        "id": "stepReplanned",
        "status": "active",
        "title": "Journey replanned",
        "detail": "Propagating the change through the journey..."
    })

    replanned = generate_replanned_schedule(
        flight_id
    )

    workflow.append({
        "id": "stepReplanned",
        "status": "complete",
        "title": "Journey replanned",
        "detail": "Affected events have been rescheduled."
    })

    workflow.append({
        "id": "stepCommunication",
        "status": "active",
        "title": "Traveler update prepared",
        "detail": "Generating traveler communication..."
    })

    communication = create_communication()

    workflow.append({
        "id": "stepCommunication",
        "status": "complete",
        "title": "Traveler update prepared",
        "detail": "Traveler communication is ready."
    })

    final_trip = get_current_trip()

    return {
        "success": True,
        "message": "Journey automatically replanned.",
        "disruption": disruption,
        "simulation": simulation,
        "impact": impact,
        "conflicts": conflicts,
        "recovery_options": recovery.get(
            "options",
            []
        ),
        "simulation_notice": recovery.get(
            "simulation_notice",
            "AI-generated recovery scenarios."
        ),
        "evaluation": evaluation.get(
            "evaluations",
            []
        ),
        "selected_recovery": selected.get(
            "selected"
        ),
        "selection_reason": selected.get(
            "reason"
        ),
        "replanned_trip": replanned.get(
            "trip",
            final_trip
        ),
        "communication": communication.get(
            "message",
            ""
        ),
        "dependency_chain": impact.get(
            "dependency_chain",
            ""
        ),
        "workflow": workflow,
    }


def execute_agent(message):
    message = str(message or "").strip()

    if not message:
        return {
            "success": False,
            "message": "Please describe what changed."
        }

    trip = get_current_trip()

    if not trip.get("events"):
        return {
            "success": False,
            "message": (
                "Create your journey first, then "
                "describe the disruption."
            )
        }

    disruption = detect_disruption_with_ai(
        message,
        trip
    )

    if not disruption.get("flight_id"):
        disruption["flight_id"] = resolve_event_id()

    return _run_recovery_fallback(
        message,
        disruption
    )