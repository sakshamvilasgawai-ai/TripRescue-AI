from collections import deque


def build_dependency_graph(events):
    """
    Build a forward dependency graph.

    Example:

    FLIGHT
       ↓
    HOTEL
       ↓
    MEETING
       ↓
    DINNER
    """

    graph = {
        event["id"]: []
        for event in events
    }

    for event in events:
        for dependency in event.get("depends_on", []):
            if dependency not in graph:
                graph[dependency] = []

            graph[dependency].append(event["id"])

    return graph


def build_event_map(events):
    return {
        event["id"]: event
        for event in events
    }


def find_affected_event_ids(events, changed_event_id):
    """
    Traverse the dependency graph using BFS.

    Returns every downstream event affected
    by the changed event.
    """

    graph = build_dependency_graph(events)

    affected = []

    queue = deque([changed_event_id])
    visited = set()

    while queue:
        current = queue.popleft()

        if current in visited:
            continue

        visited.add(current)

        for dependent in graph.get(current, []):

            if dependent not in affected:
                affected.append(dependent)

            queue.append(dependent)

    return affected


def find_affected_events(events, changed_event_id):
    event_map = build_event_map(events)

    affected_ids = find_affected_event_ids(
        events,
        changed_event_id
    )

    return [
        event_map[event_id]
        for event_id in affected_ids
        if event_id in event_map
    ]


def dependency_chain(events, changed_event_id):
    """
    Return a human-readable dependency chain.
    """

    affected = find_affected_events(
        events,
        changed_event_id
    )

    return [
        {
            "id": event["id"],
            "type": event["type"],
            "name": event["name"]
        }
        for event in affected
    ]