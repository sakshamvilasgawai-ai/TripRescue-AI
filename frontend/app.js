const $ = (id) => document.getElementById(id);


const createTripForm = $("createTripForm");
const disruptionInput = $("disruptionInput");
const replanButton = $("replanButton");
const resetButton = $("resetButton");

const resultsSection = $("resultsSection");
const replannedSection = $("replannedSection");

const currentJourney = $("currentJourney");
const dependencyChain = $("dependencyChain");
const recoveryOptions = $("recoveryOptions");
const selectedRecovery = $("selectedRecovery");
const replannedJourney = $("replannedJourney");
const communication = $("communication");


const workflowIds = [
    "stepDisruption",
    "stepImpact",
    "stepRecovery",
    "stepConstraints",
    "stepSelected",
    "stepReplanned",
    "stepCommunication",
];


function value(id) {
    return $(id).value.trim();
}


function optionalEvent(
    id,
    type,
    name,
    startId,
    endId,
    dependsOn = []
) {
    const start = value(startId);
    const end = value(endId);

    if (!start || !end) {
        return null;
    }

    return {
        id,
        type,
        name: value(name) || "Untitled Event",
        start: new Date(start).toISOString(),
        end: new Date(end).toISOString(),
        location: "",
        depends_on: dependsOn,
        buffer_minutes: 15,
    };
}


function formatDateTime(dateString) {
    if (!dateString) {
        return "—";
    }

    const date = new Date(dateString);

    if (Number.isNaN(date.getTime())) {
        return dateString;
    }

    return date.toLocaleString(
        [],
        {
            dateStyle: "short",
            timeStyle: "short",
        }
    );
}


function formatType(type) {
    const labels = {
        flight: "Flight",
        hotel: "Hotel",
        meeting: "Meeting",
        activity: "Activity",
        dinner: "Dinner",
    };

    return labels[type] || type;
}


function setWorkflowState(
    id,
    status,
    detail
) {
    const element = $(id);

    if (!element) {
        return;
    }

    element.classList.remove(
        "active",
        "complete"
    );

    if (status === "active") {
        element.classList.add("active");
    }

    if (status === "complete") {
        element.classList.add("complete");
    }

    const paragraph = element.querySelector("p");

    if (paragraph) {
        paragraph.textContent =
            detail || "Waiting...";
    }
}


function resetWorkflow() {
    workflowIds.forEach((id) => {
        setWorkflowState(
            id,
            "waiting",
            "Waiting..."
        );
    });
}


function renderJourney(
    events,
    target,
    emptyText = "No journey created yet."
) {
    if (!events || events.length === 0) {
        target.className =
            "journey-list empty";

        target.textContent = emptyText;

        return;
    }

    target.className = "journey-list";

    target.innerHTML = "";

    events.forEach((event) => {

        const item =
            document.createElement("div");

        item.className =
            "journey-event";

        const time =
            document.createElement("div");

        time.className =
            "journey-time";

        time.innerHTML =
            `${formatDateTime(event.start)}<br>↓<br>${formatDateTime(event.end)}`;


        const main =
            document.createElement("div");

        main.className =
            "journey-main";

        const title =
            document.createElement("strong");

        title.textContent =
            event.name;

        const meta =
            document.createElement("span");

        const location =
            event.location
                ? ` • ${event.location}`
                : "";

        meta.textContent =
            `${formatType(event.type)}${location}`;


        main.appendChild(title);
        main.appendChild(meta);


        const badge =
            document.createElement("div");

        badge.className =
            "event-badge";

        badge.textContent =
            event.status === "replanned"
                ? "Replanned"
                : formatType(event.type);


        item.appendChild(time);
        item.appendChild(main);
        item.appendChild(badge);

        target.appendChild(item);
    });
}


function renderRecoveryOptions(options) {
    recoveryOptions.innerHTML = "";

    if (!options || options.length === 0) {
        recoveryOptions.textContent =
            "No recovery options generated.";

        return;
    }

    options.forEach((option) => {

        const card =
            document.createElement("div");

        card.className =
            "recovery-option";


        const header =
            document.createElement("div");

        header.className =
            "recovery-option-header";


        const title =
            document.createElement("strong");

        title.textContent =
            option.flight_name ||
            option.label ||
            "Recovery option";


        const status =
            document.createElement("span");

        status.className =
            "option-status";

        status.textContent =
            "SIMULATION";


        header.appendChild(title);
        header.appendChild(status);


        const description =
            document.createElement("p");

        description.textContent =
            `${formatDateTime(option.departure)} → ${formatDateTime(option.arrival)} • ${option.reason || "AI-generated recovery scenario."}`;


        card.appendChild(header);
        card.appendChild(description);

        recoveryOptions.appendChild(card);
    });
}


function renderSelectedRecovery(option) {
    selectedRecovery.innerHTML = "";

    if (!option) {
        selectedRecovery.textContent = "—";
        return;
    }

    const wrapper =
        document.createElement("div");

    wrapper.className =
        "selected-recovery";


    const title =
        document.createElement("strong");

    title.textContent =
        option.flight_name ||
        option.label ||
        "Recovery flight";


    const details =
        document.createElement("span");

    details.textContent =
        `${formatDateTime(option.departure)} → ${formatDateTime(option.arrival)}`;


    const notice =
        document.createElement("span");

    notice.style.marginTop = "7px";

    notice.textContent =
        "AI-generated simulation. Not live availability.";


    wrapper.appendChild(title);
    wrapper.appendChild(details);
    wrapper.appendChild(notice);

    selectedRecovery.appendChild(wrapper);
}


function renderWorkflow(workflow) {
    if (!workflow) {
        return;
    }

    workflow.forEach((step) => {
        setWorkflowState(
            step.id,
            step.status,
            step.detail
        );
    });
}


async function loadCurrentTrip() {
    try {
        const response =
            await fetch("/api/trip");

        const data =
            await response.json();

        renderJourney(
            data.events || [],
            currentJourney
        );

        if (data.events && data.events.length > 0) {
            const traveler =
                data.traveler || "";

            $("traveler").value =
                traveler;

            $("origin").value =
                data.origin || "";

            $("destination").value =
                data.destination || "";
        }

    } catch (error) {
        currentJourney.textContent =
            "Unable to load current journey.";
    }
}


function buildEvents() {
    const events = [];

    const flight = {
        id: "flight_1",
        type: "flight",
        name:
            value("flightName") ||
            "Primary Flight",
        start:
            new Date(
                value("flightStart")
            ).toISOString(),
        end:
            new Date(
                value("flightEnd")
            ).toISOString(),
        location:
            value("destination"),
        depends_on: [],
        buffer_minutes: 0,
    };

    events.push(flight);


    const hotel = {
        id: "hotel_1",
        type: "hotel",
        name:
            value("hotelName") ||
            "Hotel Check-in",
        start:
            new Date(
                value("hotelStart")
            ).toISOString(),
        end:
            new Date(
                value("hotelEnd")
            ).toISOString(),
        location:
            value("destination"),
        depends_on: [
            "flight_1"
        ],
        buffer_minutes: 30,
    };

    events.push(hotel);


    const meeting =
        optionalEvent(
            "meeting_1",
            "meeting",
            "meetingName",
            "meetingStart",
            "meetingEnd",
            ["hotel_1"]
        );

    if (meeting) {
        events.push(meeting);
    }


    const activityDependency =
        meeting
            ? ["meeting_1"]
            : ["hotel_1"];


    const activity =
        optionalEvent(
            "activity_1",
            "activity",
            "activityName",
            "activityStart",
            "activityEnd",
            activityDependency
        );

    if (activity) {
        events.push(activity);
    }


    let dinnerDependencies;

    if (activity) {
        dinnerDependencies = [
            "activity_1"
        ];
    } else if (meeting) {
        dinnerDependencies = [
            "meeting_1"
        ];
    } else {
        dinnerDependencies = [
            "hotel_1"
        ];
    }


    const dinner =
        optionalEvent(
            "dinner_1",
            "dinner",
            "dinnerName",
            "dinnerStart",
            "dinnerEnd",
            dinnerDependencies
        );

    if (dinner) {
        events.push(dinner);
    }


    return events;
}


createTripForm.addEventListener(
    "submit",
    async (event) => {

        event.preventDefault();

        const events =
            buildEvents();

        const payload = {
            traveler:
                value("traveler"),

            origin:
                value("origin"),

            destination:
                value("destination"),

            events,
        };


        try {

            const response =
                await fetch(
                    "/api/trip",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json",
                        },

                        body:
                            JSON.stringify(
                                payload
                            ),
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Unable to create journey."
                );
            }


            resultsSection.classList.add(
                "hidden"
            );

            replannedSection.classList.add(
                "hidden"
            );

            resetWorkflow();

            renderJourney(
                data.trip.events,
                currentJourney
            );


            alert(
                "Journey created successfully."
            );

        } catch (error) {

            alert(
                error.message ||
                "Unable to create journey."
            );
        }
    }
);


replanButton.addEventListener(
    "click",
    async () => {

        const message =
            disruptionInput.value.trim();

        if (!message) {
            alert(
                "Describe what happened first."
            );

            return;
        }


        replanButton.disabled = true;

        replanButton.textContent =
            "AI is replanning...";


        resultsSection.classList.remove(
            "hidden"
        );

        replannedSection.classList.add(
            "hidden"
        );

        resetWorkflow();


        try {

            const response =
                await fetch(
                    "/api/agent",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json",
                        },

                        body:
                            JSON.stringify({
                                message,
                            }),
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Agent request failed."
                );
            }


            if (!data.success) {
                throw new Error(
                    data.message ||
                    "Agent could not complete recovery."
                );
            }


            renderWorkflow(
                data.workflow
            );


            dependencyChain.textContent =
                data.dependency_chain ||
                "No dependency chain found.";


            renderRecoveryOptions(
                data.recovery_options
            );


            renderSelectedRecovery(
                data.selected_recovery
            );


            if (data.replanned_trip) {

                replannedSection.classList.remove(
                    "hidden"
                );

                renderJourney(
                    data.replanned_trip.events,
                    replannedJourney
                );

                communication.textContent =
                    data.communication ||
                    "No communication generated.";

                renderJourney(
                    data.replanned_trip.events,
                    currentJourney
                );
            }

        } catch (error) {

            alert(
                error.message ||
                "Something went wrong."
            );

        } finally {

            replanButton.disabled = false;

            replanButton.innerHTML =
                `Replan Automatically <span>→</span>`;
        }
    }
);


resetButton.addEventListener(
    "click",
    async () => {

        const confirmed =
            window.confirm(
                "Reset the current journey?"
            );

        if (!confirmed) {
            return;
        }


        try {

            const response =
                await fetch(
                    "/api/reset",
                    {
                        method: "POST",
                    }
                );


            const data =
                await response.json();


            if (!data.success) {
                throw new Error(
                    "Reset failed."
                );
            }


            createTripForm.reset();

            $("flightName").value =
                "Primary Flight";

            $("hotelName").value =
                "Hotel Check-in";

            $("meetingName").value =
                "Client Meeting";

            $("activityName").value =
                "City Activity";

            $("dinnerName").value =
                "Dinner";


            disruptionInput.value = "";

            resultsSection.classList.add(
                "hidden"
            );

            replannedSection.classList.add(
                "hidden"
            );

            resetWorkflow();

            renderJourney(
                [],
                currentJourney
            );

        } catch (error) {

            alert(
                error.message ||
                "Unable to reset journey."
            );
        }
    }
);


loadCurrentTrip();