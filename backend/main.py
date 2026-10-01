import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import execute_agent
from .tools import (
    get_itinerary,
    simulate_flight_disruption,
    analyze_dependencies,
    check_schedule_conflicts,
    find_alternative_flights,
    evaluate_alternative_flights,
    generate_replanned_schedule,
    create_communication
)


app = FastAPI(
    title="TripRescue AI",
    version="2.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


class AgentRequest(BaseModel):
    message: str


class DisruptionRequest(BaseModel):
    flight_id: str
    delay_minutes: int


class ReplanRequest(BaseModel):
    flight_id: str
    arrival_time: str


@app.get("/api/health")
def health():

    return {
        "status": "online",
        "agent": "TripRescue AI",
        "version": "2.0"
    }


@app.get("/api/itinerary")
def itinerary():

    return get_itinerary()


@app.post("/api/disrupt")
def disrupt(
    request: DisruptionRequest
):

    return simulate_flight_disruption(
        request.flight_id,
        request.delay_minutes
    )


@app.post("/api/dependencies")
def dependencies(
    request: dict
):

    return analyze_dependencies(
        request["event_id"]
    )


@app.post("/api/conflicts")
def conflicts(
    request: dict
):

    return check_schedule_conflicts(
        request["arrival_time"]
    )


@app.get("/api/alternatives")
def alternatives():

    return find_alternative_flights()


@app.post("/api/evaluate")
def evaluate(
    request: dict
):

    return evaluate_alternative_flights(
        request["arrival_time"]
    )


@app.post("/api/replan")
def replan(
    request: ReplanRequest
):

    return generate_replanned_schedule(
        request.flight_id,
        request.arrival_time
    )


@app.post("/api/communication")
def communication(
    request: dict
):

    return create_communication(
        request["affected_events"],
        request["reason"]
    )


@app.post("/api/agent")
def run_agent(
    request: AgentRequest
):

    return execute_agent(
        request.message
    )


frontend_path = os.path.join(
    os.path.dirname(
        os.path.dirname(__file__)
    ),
    "frontend"
)


app.mount(
    "/",
    StaticFiles(
        directory=frontend_path,
        html=True
    ),
    name="frontend"
)