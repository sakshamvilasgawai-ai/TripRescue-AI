from collections import deque
from datetime import datetime


def build_event_map(events):
    return {
        event["id"]: event
        for event in events
    }


def build_dependency_graph(events):
    graph = {
        event["id"]: []
        for event in events
    }

    for event in events:
        event_id = event["id"]

        for dependency in event.get("depends_on", []):
            if dependency not in graph:
                graph[dependency] = []

            graph[dependency].append(event_id)

    return graph


def build_reverse_dependency_graph(events):
    return {
        event["id"]: list(event.get("depends_on", []))
        for event in events
    }


def find_affected_event_ids(events, changed_event_id):
    graph = build_dependency_graph(events)

    affected = []
    visited = set()

    queue = deque([changed_event_id])

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


def get_downstream_order(events, changed_event_id):
    affected_ids = set(
        find_affected_event_ids(
            events,
            changed_event_id
        )
    )

    if not affected_ids:
        return []

    event_map = build_event_map(events)
    graph = build_dependency_graph(events)

    indegree = {
        event_id: 0
        for event_id in affected_ids
    }

    for event_id in affected_ids:
        event = event_map[event_id]

        for dependency in event.get("depends_on", []):
            if dependency in affected_ids:
                indegree[event_id] += 1

    queue = deque(
        event["id"]
        for event in events
        if (
            event["id"] in affected_ids
            and indegree[event["id"]] == 0
        )
    )

    ordered = []

    while queue:
        current = queue.popleft()

        ordered.append(current)

        for dependent in graph.get(current, []):
            if dependent not in affected_ids:
                continue

            indegree[dependent] -= 1

            if indegree[dependent] == 0:
                queue.append(dependent)

    # Safety fallback
    for event in events:
        event_id = event["id"]

        if (
            event_id in affected_ids
            and event_id not in ordered
        ):
            ordered.append(event_id)

    return ordered


def get_dependency_chain(events, changed_event_id):
    event_map = build_event_map(events)

    chain = []

    if changed_event_id in event_map:
        changed = event_map[changed_event_id]

        chain.append({
            "id": changed["id"],
            "type": changed["type"],
            "name": changed["name"],
            "status": "changed"
        })

    for event_id in get_downstream_order(
        events,
        changed_event_id
    ):
        event = event_map[event_id]

        chain.append({
            "id": event["id"],
            "type": event["type"],
            "name": event["name"],
            "status": "affected"
        })

    return chain


def dependency_chain_text(events, changed_event_id):
    chain = get_dependency_chain(
        events,
        changed_event_id
    )

    return " → ".join(
        item["name"]
        for item in chain
    )


def get_dependency_end_time(event, event_map):
    latest_end = None

    for dependency_id in event.get(
        "depends_on",
        []
    ):
        dependency = event_map.get(
            dependency_id
        )

        if not dependency:
            continue

        end_value = dependency.get("end")

        if not end_value:
            continue

        try:
            end_time = datetime.fromisoformat(
                end_value.replace(
                    "Z",
                    "+00:00"
                )
            )
        except ValueError:
            continue

        if (
            latest_end is None
            or end_time > latest_end
        ):
            latest_end = end_time

    return latest_end