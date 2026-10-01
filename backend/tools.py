import json
import os
import uuid

from datetime import datetime, timedelta

from .dependency_engine import (
    find_affected_events,
    build_event_map
)


DATA_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "itinerary.json"
)


def load_data():
    with open(
        DATA_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def get_itinerary():
    data = load_data()

    return {
        "success": True,
        "trip_id": data["trip_id"],
        "traveler": data["traveler"],
        "origin": data["origin"],
        "destination": data["destination"],
        "events": data["events"],
        "alternative_flights": data.get(
            "alternative_flights",
            []
        )
    }


def simulate_flight_disruption(
    flight_id: str,
    delay_minutes: int
):
    data = load_data()

    flight = None

    for event in data["events"]:

        if event["id"] == flight_id:
            flight = event
            break

    if flight is None:
        return {
            "success": False,
            "error": "Flight not found"
        }

    original_departure = datetime.fromisoformat(
        flight["start"]
    )

    original_arrival = datetime.fromisoformat(
        flight["end"]
    )

    new_departure = (
        original_departure
        + timedelta(minutes=delay_minutes)
    )

    new_arrival = (
        original_arrival
        + timedelta(minutes=delay_minutes)
    )

    return {
        "success": True,
        "flight_id": flight_id,
        "flight": flight["name"],
        "delay_minutes": delay_minutes,
        "original_departure": flight["start"],
        "original_arrival": flight["end"],
        "new_departure": new_departure.isoformat(),
        "new_arrival": new_arrival.isoformat()
    }


def analyze_dependencies(
    changed_event_id: str
):
    data = load_data()

    affected = find_affected_events(
        data["events"],
        changed_event_id
    )

    return {
        "success": True,
        "changed_event": changed_event_id,
        "affected_count": len(affected),
        "affected_events": [
            {
                "id": event["id"],
                "type": event["type"],
                "name": event["name"],
                "start": event["start"],
                "end": event["end"],
                "location": event["location"],
                "depends_on": event.get(
                    "depends_on",
                    []
                )
            }
            for event in affected
        ]
    }


def check_schedule_conflicts(
    arrival_time: str
):
    data = load_data()

    arrival = datetime.fromisoformat(
        arrival_time
    )

    conflicts = []

    for event in data["events"]:

        if event["type"] == "flight":
            continue

        start = datetime.fromisoformat(
            event["start"]
        )

        if arrival >= start:

            conflicts.append(
                {
                    "event_id": event["id"],
                    "event": event["name"],
                    "scheduled_start": event["start"],
                    "reason": (
                        "The new flight arrival occurs "
                        "after this event's scheduled start."
                    )
                }
            )

    return {
        "success": True,
        "arrival_time": arrival_time,
        "conflict_count": len(conflicts),
        "conflicts": conflicts
    }


def find_alternative_flights():
    data = load_data()

    return {
        "success": True,
        "alternatives": data.get(
            "alternative_flights",
            []
        )
    }


def evaluate_alternative_flights(
    arrival_time: str
):
    """
    Evaluate each alternative against
    downstream schedule constraints.
    """

    data = load_data()

    arrival = datetime.fromisoformat(
        arrival_time
    )

    alternatives = data.get(
        "alternative_flights",
        []
    )

    meeting = next(
        (
            event
            for event in data["events"]
            if event["type"] == "meeting"
        ),
        None
    )

    results = []

    for flight in alternatives:

        flight_arrival = datetime.fromisoformat(
            flight["arrival"]
        )

        hotel_checkin = (
            flight_arrival
            + timedelta(minutes=60)
        )

        meeting_start = (
            flight_arrival
            + timedelta(hours=3)
        )

        meeting_end = (
            meeting_start
            + timedelta(minutes=90)
        )

        dinner_start = (
            meeting_end
            + timedelta(minutes=90)
        )

        dinner_end = (
            dinner_start
            + timedelta(minutes=90)
        )

        conflicts = []

        if meeting:

            original_meeting_start = datetime.fromisoformat(
                meeting["start"]
            )

            if meeting_start > original_meeting_start:
                conflicts.append(
                    "Client meeting must be rescheduled."
                )

        results.append(
            {
                "flight_id": flight["id"],
                "flight": flight["name"],
                "departure": flight["departure"],
                "arrival": flight["arrival"],
                "hotel_checkin": hotel_checkin.isoformat(),
                "meeting_start": meeting_start.isoformat(),
                "meeting_end": meeting_end.isoformat(),
                "dinner_start": dinner_start.isoformat(),
                "dinner_end": dinner_end.isoformat(),
                "conflicts": conflicts,
                "feasible": True
            }
        )

    return {
        "success": True,
        "evaluated_at": arrival_time,
        "options": results
    }


def generate_replanned_schedule(
    new_flight_id: str,
    new_arrival_time: str
):
    data = load_data()

    arrival = datetime.fromisoformat(
        new_arrival_time
    )

    updated_events = []

    hotel_checkin = (
        arrival
        + timedelta(minutes=60)
    )

    meeting_start = (
        arrival
        + timedelta(hours=3)
    )

    meeting_end = (
        meeting_start
        + timedelta(minutes=90)
    )

    dinner_start = (
        meeting_end
        + timedelta(minutes=90)
    )

    dinner_end = (
        dinner_start
        + timedelta(minutes=90)
    )

    for event in data["events"]:

        updated = dict(event)

        if event["type"] == "flight":

            if event["id"] == "FLIGHT-001":

                updated["id"] = new_flight_id
                updated["end"] = new_arrival_time
                updated["status"] = "replanned"

        elif event["type"] == "hotel":

            updated["start"] = hotel_checkin.isoformat()
            updated["status"] = "rescheduled"

        elif event["type"] == "meeting":

            updated["start"] = meeting_start.isoformat()
            updated["end"] = meeting_end.isoformat()
            updated["status"] = "rescheduled"

        elif event["type"] == "activity":

            updated["start"] = dinner_start.isoformat()
            updated["end"] = dinner_end.isoformat()
            updated["status"] = "rescheduled"

        updated_events.append(updated)

    return {
        "success": True,
        "new_flight": new_flight_id,
        "new_arrival": new_arrival_time,
        "events": updated_events
    }


def create_communication(
    affected_events: str,
    reason: str
):
    message_id = (
        "MSG-"
        + uuid.uuid4().hex[:8].upper()
    )

    message = (
        "TRIPRESCUE AI — TRAVEL UPDATE\n\n"
        f"Affected events: {affected_events}\n\n"
        f"Reason: {reason}\n\n"
        "A revised itinerary has been prepared."
    )

    return {
        "success": True,
        "message_id": message_id,
        "status": "DRAFTED",
        "message": message,
        "simulation": True
    }


TOOLS = {
    "get_itinerary": get_itinerary,
    "simulate_flight_disruption": simulate_flight_disruption,
    "analyze_dependencies": analyze_dependencies,
    "check_schedule_conflicts": check_schedule_conflicts,
    "find_alternative_flights": find_alternative_flights,
    "evaluate_alternative_flights": evaluate_alternative_flights,
    "generate_replanned_schedule": generate_replanned_schedule,
    "create_communication": create_communication
}