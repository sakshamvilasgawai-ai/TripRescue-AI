from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.agent import execute_agent
from backend.tools import (
    create_trip,
    get_current_trip,
    save_trip,
)


app = FastAPI(
    title="TripRescue AI",
    version="7.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TripEvent(BaseModel):
    id: str
    type: str
    name: str
    start: str
    end: str
    location: Optional[str] = None
    depends_on: List[str] = Field(
        default_factory=list
    )
    buffer_minutes: int = 0


class TripRequest(BaseModel):
    traveler: str
    origin: str
    destination: str
    events: List[TripEvent]


class AgentRequest(BaseModel):
    message: str


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "TripRescue AI"
    }


@app.get("/api/trip")
def get_trip():
    return get_current_trip()


@app.post("/api/trip")
def create_trip_endpoint(
    request: TripRequest
):
    events = [
        event.model_dump()
        for event in request.events
    ]

    return create_trip(
        traveler=request.traveler,
        origin=request.origin,
        destination=request.destination,
        events=events
    )


@app.post("/api/reset")
def reset_trip():
    empty_trip = {
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

    save_trip(
        empty_trip
    )

    return {
        "success": True,
        "message": "Journey reset successfully."
    }


@app.post("/api/agent")
def run_agent(
    request: AgentRequest
):
    return execute_agent(
        request.message
    )


app.mount(
    "/",
    StaticFiles(
        directory="frontend",
        html=True
    ),
    name="frontend"
)