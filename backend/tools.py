import json
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import ollama

from backend.config import OLLAMA_MODEL
from backend.dependency_engine import (
    build_dependency_graph,
    build_event_map,
    dependency_chain_text,
    find_affected_event_ids,
    find_affected_events,
    get_downstream_order,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TRIP_FILE = os.path.join(DATA_DIR, "current_trip.json")


def _empty_trip():
    return {
        "trip_id": None,
        "traveler": None,
        "origin": None,
        "destination": None,
        "events": [],
        "original_events": [],
        "recovery_options": [],
        "selected_recovery": None,
        "last_replan": None,
    }


def load_trip():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(TRIP_FILE):
        trip = _empty_trip()
        save_trip(trip)
        return trip

    try:
        with open(TRIP_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return _empty_trip()

        return data

    except (json.JSONDecodeError, OSError):
        trip = _empty_trip()
        save_trip(trip)
        return trip


def save_trip(trip):
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(
        TRIP_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            trip,
            file,
            indent=4,
            ensure_ascii=False
        )

    return trip


def _parse_datetime(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except (ValueError, TypeError):
        return None


def _format_datetime(value):
    if isinstance(value, str):
        return value

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.isoformat(timespec="minutes")


def _duration_minutes(event):
    start = _parse_datetime(event.get("start"))
    end = _parse_datetime(event.get("end"))

    if not start or not end:
        return 60

    minutes = int(
        (end - start).total_seconds() / 60
    )

    return max(minutes, 1)


def _shift_event(event, minutes):
    shifted = deepcopy(event)

    start = _parse_datetime(event.get("start"))
    end = _parse_datetime(event.get("end"))

    if not start or not end:
        return shifted

    delta = timedelta(minutes=minutes)

    shifted["start"] = _format_datetime(
        start + delta
    )

    shifted["end"] = _format_datetime(
        end + delta
    )

    return shifted


def _minutes_between(first, second):
    first_dt = _parse_datetime(first)
    second_dt = _parse_datetime(second)

    if not first_dt or not second_dt:
        return None

    return int(
        (second_dt - first_dt).total_seconds() / 60
    )


def resolve_event_id(event_id=None):
    trip = load_trip()
    events = trip.get("events", [])

    if event_id:
        normalized = str(
            event_id
        ).strip().lower()

        invalid_placeholders = {
            "",
            "flight id",
            "changed flight id",
            "cancelled flight id",
            "canceled flight id",
            "cancelled flight",
            "canceled flight",
            "changed flight",
            "the flight id",
            "the cancelled flight id",
            "the canceled flight id",
        }

        if normalized not in invalid_placeholders:
            for event in events:
                if (
                    str(event.get("id", ""))
                    .strip()
                    .lower()
                    == normalized
                ):
                    return event["id"]

    for event in events:
        if event.get("type") == "flight":
            return event["id"]

    return None


def get_current_trip():
    return load_trip()


def create_trip(
    traveler,
    origin,
    destination,
    events
):
    now = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d%H%M%S")

    trip_id = f"trip_{now}"

    cleaned_events = []

    for index, event in enumerate(events):
        event_copy = deepcopy(event)

        if not event_copy.get("id"):
            event_copy["id"] = (
                f"{event_copy.get('type', 'event')}_{index + 1}"
            )

        if "depends_on" not in event_copy:
            event_copy["depends_on"] = []

        if "buffer_minutes" not in event_copy:
            event_copy["buffer_minutes"] = 0

        cleaned_events.append(event_copy)

    trip = {
        "trip_id": trip_id,
        "traveler": traveler,
        "origin": origin,
        "destination": destination,
        "events": cleaned_events,
        "original_events": deepcopy(cleaned_events),
        "recovery_options": [],
        "selected_recovery": None,
        "last_replan": None,
    }

    save_trip(trip)

    return {
        "success": True,
        "message": "Journey created successfully.",
        "trip": trip,
    }


def find_event_by_id(event_id):
    resolved_id = resolve_event_id(event_id)

    if not resolved_id:
        return None

    trip = load_trip()

    for event in trip.get("events", []):
        if event.get("id") == resolved_id:
            return event

    return None


def find_flight():
    trip = load_trip()

    for event in trip.get("events", []):
        if event.get("type") == "flight":
            return event

    return None


def analyze_dependencies(event_id=None):
    trip = load_trip()

    resolved_id = resolve_event_id(event_id)

    if not resolved_id:
        return {
            "success": False,
            "message": "No flight was found in the journey."
        }

    events = trip.get("events", [])

    affected_ids = find_affected_event_ids(
        events,
        resolved_id
    )

    affected_events = find_affected_events(
        events,
        resolved_id
    )

    chain = dependency_chain_text(
        events,
        resolved_id
    )

    return {
        "success": True,
        "changed_event_id": resolved_id,
        "affected_event_ids": affected_ids,
        "affected_events": affected_events,
        "dependency_chain": chain,
        "dependency_count": len(affected_ids),
    }


def simulate_flight_disruption(
    flight_id=None,
    delay_minutes=0,
    new_arrival_time=None,
    cancelled=False
):
    trip = load_trip()

    resolved_id = resolve_event_id(flight_id)

    if not resolved_id:
        return {
            "success": False,
            "message": "No flight was found."
        }

    event_map = build_event_map(
        trip.get("events", [])
    )

    flight = event_map.get(resolved_id)

    if not flight:
        return {
            "success": False,
            "message": "Flight not found."
        }

    original_start = flight.get("start")
    original_end = flight.get("end")

    if cancelled:
        flight["status"] = "cancelled"

        trip["events"] = [
            flight if event["id"] == resolved_id
            else event
            for event in trip["events"]
        ]

        save_trip(trip)

        return {
            "success": True,
            "flight_id": resolved_id,
            "status": "cancelled",
            "original_start": original_start,
            "original_end": original_end,
            "new_start": None,
            "new_arrival": None,
        }

    delay_minutes = max(
        int(delay_minutes or 0),
        0
    )

    start_dt = _parse_datetime(original_start)
    end_dt = _parse_datetime(original_end)

    if new_arrival_time:
        parsed_arrival = _parse_datetime(
            new_arrival_time
        )

        if parsed_arrival:
            end_dt = parsed_arrival

    elif end_dt:
        end_dt = end_dt + timedelta(
            minutes=delay_minutes
        )

    if start_dt and delay_minutes:
        start_dt = start_dt + timedelta(
            minutes=delay_minutes
        )

    if start_dt:
        flight["start"] = _format_datetime(
            start_dt
        )

    if end_dt:
        flight["end"] = _format_datetime(
            end_dt
        )

    flight["status"] = "delayed"

    trip["events"] = [
        flight if event["id"] == resolved_id
        else event
        for event in trip["events"]
    ]

    save_trip(trip)

    return {
        "success": True,
        "flight_id": resolved_id,
        "status": "delayed",
        "delay_minutes": delay_minutes,
        "original_start": original_start,
        "original_end": original_end,
        "new_start": flight.get("start"),
        "new_arrival": flight.get("end"),
    }


def check_schedule_conflicts(event_id=None):
    trip = load_trip()

    resolved_id = resolve_event_id(event_id)

    if not resolved_id:
        return {
            "success": False,
            "message": "No changed flight found."
        }

    events = trip.get("events", [])
    event_map = build_event_map(events)

    changed_event = event_map.get(resolved_id)

    if not changed_event:
        return {
            "success": False,
            "message": "Changed event not found."
        }

    arrival = _parse_datetime(
        changed_event.get("end")
    )

    conflicts = []

    affected_ids = find_affected_event_ids(
        events,
        resolved_id
    )

    for event_id in affected_ids:
        event = event_map.get(event_id)

        if not event:
            continue

        start = _parse_datetime(
            event.get("start")
        )

        if not start or not arrival:
            continue

        buffer_minutes = int(
            event.get("buffer_minutes", 0)
            or 0
        )

        required_start = arrival + timedelta(
            minutes=buffer_minutes
        )

        if start < required_start:
            conflicts.append({
                "event_id": event["id"],
                "event_name": event["name"],
                "scheduled_start": event["start"],
                "required_start": _format_datetime(
                    required_start
                ),
                "conflict_minutes": int(
                    (
                        required_start - start
                    ).total_seconds() / 60
                ),
            })

    return {
        "success": True,
        "changed_event_id": resolved_id,
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
    }


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


def _fallback_recovery_options(
    flight,
    cancelled=False
):
    start = _parse_datetime(
        flight.get("start")
    )
    end = _parse_datetime(
        flight.get("end")
    )

    if not start or not end:
        return []

    duration = _duration_minutes(flight)

    if cancelled:
        base_start = start
        base_end = end
    else:
        base_start = start
        base_end = end

    options = []

    offsets = [
        -120,
        60,
        180
    ]

    labels = [
        "Earlier recovery flight",
        "Near-original recovery flight",
        "Later recovery flight",
    ]

    for index, offset in enumerate(offsets):
        option_start = (
            base_start
            + timedelta(minutes=offset)
        )

        option_end = (
            option_start
            + timedelta(minutes=duration)
        )

        options.append({
            "option_id": f"recovery_{index + 1}",
            "label": labels[index],
            "flight_name": (
                f"AI Recovery Flight {index + 1}"
            ),
            "departure": _format_datetime(
                option_start
            ),
            "arrival": _format_datetime(
                option_end
            ),
            "duration_minutes": duration,
            "reason": (
                "Simulated recovery option "
                "generated because live flight "
                "availability is not connected."
            ),
            "simulation_only": True,
        })

    return options


def generate_ai_recovery_options(
    flight_id=None,
    cancelled=False
):
    trip = load_trip()

    resolved_id = resolve_event_id(
        flight_id
    )

    if not resolved_id:
        return {
            "success": False,
            "message": "No flight found."
        }

    flight = None

    for event in trip.get("events", []):
        if event.get("id") == resolved_id:
            flight = event
            break

    if not flight:
        return {
            "success": False,
            "message": "Flight not found."
        }

    duration = _duration_minutes(flight)

    prompt = f"""
You are a travel recovery planning AI.

Generate exactly 3 simulated recovery flight options.

Important:
- These are NOT real flights.
- There is NO live airline API.
- Do not claim that seats or tickets are available.
- Do not invent real airline bookings.
- Generate plausible simulated schedule alternatives.
- Preserve approximately the same flight duration.
- The goal is to minimize disruption to downstream events.

Current flight:
Name: {flight.get("name")}
Departure: {flight.get("start")}
Arrival: {flight.get("end")}
Duration minutes: {duration}
Cancelled: {cancelled}

Return ONLY valid JSON in this exact structure:

{{
  "options": [
    {{
      "option_id": "recovery_1",
      "label": "Earlier recovery flight",
      "flight_name": "AI Recovery Flight 1",
      "departure": "ISO_DATETIME",
      "arrival": "ISO_DATETIME",
      "duration_minutes": {duration},
      "reason": "short reason",
      "simulation_only": true
    }},
    {{
      "option_id": "recovery_2",
      "label": "Near-original recovery flight",
      "flight_name": "AI Recovery Flight 2",
      "departure": "ISO_DATETIME",
      "arrival": "ISO_DATETIME",
      "duration_minutes": {duration},
      "reason": "short reason",
      "simulation_only": true
    }},
    {{
      "option_id": "recovery_3",
      "label": "Later recovery flight",
      "flight_name": "AI Recovery Flight 3",
      "departure": "ISO_DATETIME",
      "arrival": "ISO_DATETIME",
      "duration_minutes": {duration},
      "reason": "short reason",
      "simulation_only": true
    }}
  ]
}}
"""

    options = []

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate simulated travel "
                        "recovery schedules. Return JSON only."
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

        if parsed:
            options = parsed.get(
                "options",
                []
            )

    except Exception:
        options = []

    valid_options = []

    for index, option in enumerate(options):
        if not isinstance(option, dict):
            continue

        departure = _parse_datetime(
            option.get("departure")
        )

        arrival = _parse_datetime(
            option.get("arrival")
        )

        if not departure or not arrival:
            continue

        if arrival <= departure:
            continue

        valid_options.append({
            "option_id": option.get(
                "option_id",
                f"recovery_{index + 1}"
            ),
            "label": option.get(
                "label",
                f"AI Recovery Flight {index + 1}"
            ),
            "flight_name": option.get(
                "flight_name",
                f"AI Recovery Flight {index + 1}"
            ),
            "departure": _format_datetime(
                departure
            ),
            "arrival": _format_datetime(
                arrival
            ),
            "duration_minutes": int(
                (
                    arrival - departure
                ).total_seconds() / 60
            ),
            "reason": option.get(
                "reason",
                "AI-generated simulated recovery option."
            ),
            "simulation_only": True,
        })

    if len(valid_options) < 3:
        valid_options = _fallback_recovery_options(
            flight,
            cancelled=cancelled
        )

    trip["recovery_options"] = valid_options
    save_trip(trip)

    return {
        "success": True,
        "simulation_notice": (
            "Recovery flights are AI-generated "
            "simulation scenarios only. "
            "Live airline availability is not connected."
        ),
        "options": valid_options,
    }


def _simulate_schedule(
    events,
    changed_flight_id,
    recovery_option
):
    simulated = deepcopy(events)

    event_map = build_event_map(
        simulated
    )

    flight = event_map.get(
        changed_flight_id
    )

    if not flight:
        return simulated

    new_start = _parse_datetime(
        recovery_option.get("departure")
    )

    new_end = _parse_datetime(
        recovery_option.get("arrival")
    )

    if not new_start or not new_end:
        return simulated

    old_end = _parse_datetime(
        flight.get("end")
    )

    flight["start"] = _format_datetime(
        new_start
    )

    flight["end"] = _format_datetime(
        new_end
    )

    flight["status"] = "replanned"

    downstream_order = get_downstream_order(
        simulated,
        changed_flight_id
    )

    previous_end = new_end

    for event_id in downstream_order:
        event = event_map.get(event_id)

        if not event:
            continue

        current_start = _parse_datetime(
            event.get("start")
        )

        current_end = _parse_datetime(
            event.get("end")
        )

        if not current_start or not current_end:
            continue

        duration = current_end - current_start

        buffer_minutes = int(
            event.get("buffer_minutes", 0)
            or 0
        )

        required_start = (
            previous_end
            + timedelta(minutes=buffer_minutes)
        )

        if current_start < required_start:
            new_event_start = required_start
        else:
            new_event_start = current_start

        new_event_end = (
            new_event_start + duration
        )

        event["start"] = _format_datetime(
            new_event_start
        )

        event["end"] = _format_datetime(
            new_event_end
        )

        previous_end = new_event_end

    return simulated


def evaluate_recovery_options(
    flight_id=None
):
    trip = load_trip()

    resolved_id = resolve_event_id(
        flight_id
    )

    if not resolved_id:
        return {
            "success": False,
            "message": "No flight found."
        }

    options = trip.get(
        "recovery_options",
        []
    )

    if not options:
        return {
            "success": False,
            "message": "No recovery options available."
        }

    results = []

    original_events = trip.get(
        "events",
        []
    )

    event_map = build_event_map(
        original_events
    )

    downstream_ids = find_affected_event_ids(
        original_events,
        resolved_id
    )

    for option in options:
        simulated = _simulate_schedule(
            original_events,
            resolved_id,
            option
        )

        simulated_map = build_event_map(
            simulated
        )

        conflicts = []
        total_shift = 0

        for event_id in downstream_ids:
            before = event_map.get(
                event_id
            )

            after = simulated_map.get(
                event_id
            )

            if not before or not after:
                continue

            shift = _minutes_between(
                before.get("start"),
                after.get("start")
            )

            if shift is not None:
                total_shift += max(
                    shift,
                    0
                )

            after_start = _parse_datetime(
                after.get("start")
            )

            after_end = _parse_datetime(
                after.get("end")
            )

            if after_start and after_end:
                dependencies = after.get(
                    "depends_on",
                    []
                )

                for dependency_id in dependencies:
                    dependency = simulated_map.get(
                        dependency_id
                    )

                    if not dependency:
                        continue

                    dependency_end = _parse_datetime(
                        dependency.get("end")
                    )

                    if (
                        dependency_end
                        and after_start < dependency_end
                    ):
                        conflicts.append({
                            "event_id": event_id,
                            "event_name": after.get(
                                "name"
                            ),
                        })

        score = (
            total_shift
            + (len(conflicts) * 10000)
        )

        results.append({
            "option_id": option.get(
                "option_id"
            ),
            "flight_name": option.get(
                "flight_name"
            ),
            "total_downstream_shift_minutes": total_shift,
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "score": score,
            "feasible": len(conflicts) == 0,
        })

    trip["recovery_evaluations"] = results
    save_trip(trip)

    return {
        "success": True,
        "evaluations": results,
    }


def choose_best_recovery():
    trip = load_trip()

    evaluations = trip.get(
        "recovery_evaluations",
        []
    )

    options = trip.get(
        "recovery_options",
        []
    )

    if not evaluations or not options:
        return {
            "success": False,
            "message": "Recovery options have not been evaluated."
        }

    feasible = [
        item
        for item in evaluations
        if item.get("feasible")
    ]

    candidates = (
        feasible
        if feasible
        else evaluations
    )

    selected_evaluation = min(
        candidates,
        key=lambda item: item.get(
            "score",
            999999999
        )
    )

    selected_id = selected_evaluation.get(
        "option_id"
    )

    selected_option = next(
        (
            option
            for option in options
            if option.get("option_id")
            == selected_id
        ),
        None
    )

    trip["selected_recovery"] = selected_option
    save_trip(trip)

    return {
        "success": True,
        "selected": selected_option,
        "evaluation": selected_evaluation,
        "reason": (
            "Selected the feasible simulated recovery "
            "with the lowest downstream disruption."
        ),
    }


def generate_replanned_schedule(
    flight_id=None
):
    trip = load_trip()

    resolved_id = resolve_event_id(
        flight_id
    )

    selected = trip.get(
        "selected_recovery"
    )

    if not resolved_id:
        return {
            "success": False,
            "message": "No flight found."
        }

    if not selected:
        return {
            "success": False,
            "message": "No recovery option selected."
        }

    events_before = deepcopy(
        trip.get("events", [])
    )

    events_after = _simulate_schedule(
        events_before,
        resolved_id,
        selected
    )

    for event in events_after:
        if event.get("id") == resolved_id:
            event["status"] = "replanned"

    trip["events"] = events_after

    trip["last_replan"] = {
        "changed_event_id": resolved_id,
        "selected_option_id": selected.get(
            "option_id"
        ),
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    save_trip(trip)

    return {
        "success": True,
        "events": events_after,
        "trip": trip,
    }


def create_communication():
    trip = load_trip()

    selected = trip.get(
        "selected_recovery"
    )

    if not selected:
        return {
            "success": False,
            "message": "No recovery selected."
        }

    traveler = trip.get(
        "traveler"
    ) or "Traveler"

    events = trip.get(
        "events",
        []
    )

    flight = find_flight()

    flight_name = (
        flight.get("name")
        if flight
        else "your flight"
    )

    arrival = (
        flight.get("end")
        if flight
        else selected.get("arrival")
    )

    meeting = next(
        (
            event
            for event in events
            if event.get("type")
            == "meeting"
        ),
        None
    )

    message = (
        f"Hello {traveler},\n\n"
        f"Your journey has been automatically "
        f"replanned after a disruption to "
        f"{flight_name}.\n\n"
        f"AI recovery scenario selected: "
        f"{selected.get('flight_name')}.\n"
        f"Updated arrival: {arrival}.\n"
    )

    if meeting:
        message += (
            f"Your downstream schedule has also "
            f"been adjusted to protect the dependency "
            f"chain. Your meeting is now scheduled for "
            f"{meeting.get('start')}.\n"
        )

    message += (
        "\nPlease note: the recovery flight shown "
        "is an AI-generated simulation because "
        "live airline availability is not connected."
    )

    return {
        "success": True,
        "message": message,
    }


TOOLS = {
    "get_current_trip": get_current_trip,
    "analyze_dependencies": analyze_dependencies,
    "simulate_flight_disruption": simulate_flight_disruption,
    "check_schedule_conflicts": check_schedule_conflicts,
    "generate_ai_recovery_options": generate_ai_recovery_options,
    "evaluate_recovery_options": evaluate_recovery_options,
    "choose_best_recovery": choose_best_recovery,
    "generate_replanned_schedule": generate_replanned_schedule,
    "create_communication": create_communication,
}