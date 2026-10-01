import json

from ollama import chat

from .config import (
    OLLAMA_MODEL,
    MAX_AGENT_STEPS
)

from .tools import TOOLS


SYSTEM_PROMPT = """
You are TripRescue AI.

You are an autonomous travel disruption
and replanning agent.

Your job is to manage a multi-step journey
containing flights, hotels, meetings and activities.

The core concept is DEPENDENCY-AWARE REPLANNING.

When a disruption occurs you MUST:

1. Get the current itinerary.
2. Identify the changed event.
3. Analyze downstream dependencies.
4. Calculate schedule conflicts.
5. Find alternative flights.
6. Evaluate alternatives.
7. Select a suitable alternative.
8. Generate a revised itinerary.
9. Create a communication.

You must use tools for these operations.

Do not invent itinerary data.

Do not claim that real bookings,
cancellations, refunds or messages occurred.

This is a simulated travel environment.

At the end provide:

- What changed
- Affected events
- Selected alternative
- Updated itinerary
- Communication status

Do not reveal hidden chain-of-thought.
"""


TOOL_SCHEMAS = [

    {
        "type": "function",
        "function": {
            "name": "get_itinerary",
            "description": "Get the current itinerary.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "simulate_flight_disruption",
            "description": "Calculate the effect of a flight delay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_id": {
                        "type": "string"
                    },
                    "delay_minutes": {
                        "type": "integer"
                    }
                },
                "required": [
                    "flight_id",
                    "delay_minutes"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "analyze_dependencies",
            "description": "Find downstream dependent events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "changed_event_id": {
                        "type": "string"
                    }
                },
                "required": [
                    "changed_event_id"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "check_schedule_conflicts",
            "description": "Check conflicts caused by a new arrival time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "arrival_time": {
                        "type": "string"
                    }
                },
                "required": [
                    "arrival_time"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "find_alternative_flights",
            "description": "Find available alternative flights.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "evaluate_alternative_flights",
            "description": "Evaluate alternatives against downstream constraints.",
            "parameters": {
                "type": "object",
                "properties": {
                    "arrival_time": {
                        "type": "string"
                    }
                },
                "required": [
                    "arrival_time"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "generate_replanned_schedule",
            "description": "Generate the updated itinerary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "new_flight_id": {
                        "type": "string"
                    },
                    "new_arrival_time": {
                        "type": "string"
                    }
                },
                "required": [
                    "new_flight_id",
                    "new_arrival_time"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "create_communication",
            "description": "Create the travel update communication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "affected_events": {
                        "type": "string"
                    },
                    "reason": {
                        "type": "string"
                    }
                },
                "required": [
                    "affected_events",
                    "reason"
                ]
            }
        }
    }

]


def execute_tool(
    tool_name,
    arguments
):
    tool = TOOLS.get(tool_name)

    if tool is None:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }

    try:
        return tool(**arguments)

    except Exception as error:
        return {
            "success": False,
            "error": str(error)
        }


def execute_agent(user_message):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

    trace = []

    for step in range(MAX_AGENT_STEPS):

        try:

            response = chat(
                model=OLLAMA_MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS
            )

        except Exception as error:

            return {
                "success": False,
                "error": (
                    "Could not connect to Ollama: "
                    + str(error)
                ),
                "trace": trace
            }

        message = response["message"]

        tool_calls = message.get(
            "tool_calls",
            []
        )

        messages.append(message)

        if not tool_calls:

            return {
                "success": True,
                "response": message.get(
                    "content",
                    "No response generated."
                ),
                "trace": trace
            }

        for call in tool_calls:

            function = call["function"]

            tool_name = function["name"]

            arguments = function.get(
                "arguments",
                {}
            )

            if isinstance(arguments, str):

                try:
                    arguments = json.loads(
                        arguments
                    )

                except json.JSONDecodeError:

                    arguments = {}

            result = execute_tool(
                tool_name,
                arguments
            )

            trace.append(
                {
                    "step": step + 1,
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "content": json.dumps(
                        result,
                        default=str
                    )
                }
            )

    return {
        "success": False,
        "response": (
            "The agent reached its maximum "
            "number of steps."
        ),
        "trace": trace
    }