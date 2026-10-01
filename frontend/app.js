const runButton = document.getElementById(
    "runAgent"
);

const promptBox = document.getElementById(
    "prompt"
);

const workflow = document.getElementById(
    "workflow"
);

const resultSection = document.getElementById(
    "resultSection"
);

const resultBox = document.getElementById(
    "result"
);

const agentStatus = document.getElementById(
    "agentStatus"
);

const stepCount = document.getElementById(
    "stepCount"
);


const TOOL_LABELS = {

    get_itinerary:
        "Get current itinerary",

    simulate_flight_disruption:
        "Simulate flight disruption",

    analyze_dependencies:
        "Analyze dependency chain",

    check_schedule_conflicts:
        "Check schedule conflicts",

    find_alternative_flights:
        "Find alternative flights",

    generate_replanned_schedule:
        "Generate revised itinerary",

    create_communication:
        "Prepare communication"
};


runButton.addEventListener(
    "click",
    runAgent
);


async function runAgent() {

    const prompt = promptBox.value.trim();

    if (!prompt) {

        alert(
            "Please enter a disruption scenario."
        );

        return;
    }


    runButton.disabled = true;

    agentStatus.classList.remove(
        "hidden"
    );


    workflow.innerHTML = `
        <div class="empty-state">
            Agent is executing tools...
        </div>
    `;


    resultSection.classList.add(
        "hidden"
    );


    clearJourneyHighlights();


    try {

        const response = await fetch(
            "/api/agent",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    message: prompt
                })
            }
        );


        const data = await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Server request failed."
            );
        }


        renderWorkflow(
            data.trace || []
        );


        renderResult(
            data
        );


        processAffectedEvents(
            data.trace || []
        );


    } catch (error) {

        workflow.innerHTML = `
            <div class="error-card">
                <strong>Agent Error</strong>
                <br>
                ${escapeHtml(
                    error.message
                )}
            </div>
        `;

    } finally {

        runButton.disabled = false;

        agentStatus.classList.add(
            "hidden"
        );
    }
}


function renderWorkflow(trace) {

    if (!trace.length) {

        workflow.innerHTML = `
            <div class="error-card">
                The model did not execute any tools.
                Check the Ollama model and agent configuration.
            </div>
        `;

        stepCount.textContent =
            "0 tool calls";

        return;
    }


    stepCount.textContent =
        `${trace.length} tool calls`;


    workflow.innerHTML = "";


    trace.forEach(
        (item, index) => {

            const card =
                document.createElement(
                    "div"
                );

            card.className =
                "workflow-card";


            const toolName =
                TOOL_LABELS[
                    item.tool
                ] ||
                item.tool;


            card.innerHTML = `
                <span class="workflow-number">
                    ${index + 1}
                </span>

                <h3>
                    ${escapeHtml(
                        toolName
                    )}
                </h3>

                <p>
                    ${escapeHtml(
                        JSON.stringify(
                            item.arguments
                        )
                    )}
                </p>
            `;


            workflow.appendChild(
                card
            );
        }
    );
}


function processAffectedEvents(trace) {

    clearJourneyHighlights();


    trace.forEach(
        item => {

            if (
                item.tool ===
                "analyze_dependencies"
            ) {

                const result =
                    item.result;


                if (
                    result &&
                    result.affected_events
                ) {

                    result.affected_events.forEach(
                        event => {

                            const element =
                                document.querySelector(
                                    `[data-event="${event.id}"]`
                                );


                            if (element) {

                                element.classList.add(
                                    "affected"
                                );
                            }

                        }
                    );
                }
            }


            if (
                item.tool ===
                "simulate_flight_disruption"
            ) {

                const element =
                    document.querySelector(
                        '[data-event="FLIGHT-001"]'
                    );


                if (element) {

                    element.classList.add(
                        "changed"
                    );
                }
            }
        }
    );
}


function clearJourneyHighlights() {

    document
        .querySelectorAll(
            ".journey-card"
        )
        .forEach(
            element => {

                element.classList.remove(
                    "changed",
                    "affected"
                );
            }
        );
}


function renderResult(data) {

    resultSection.classList.remove(
        "hidden"
    );


    resultBox.innerHTML = "";


    const trace =
        data.trace || [];


    let replanned =
        null;


    let communication =
        null;


    trace.forEach(
        item => {

            if (
                item.tool ===
                "generate_replanned_schedule"
            ) {

                replanned =
                    item.result;
            }


            if (
                item.tool ===
                "create_communication"
            ) {

                communication =
                    item.result;
            }

        }
    );


    if (replanned && replanned.events) {

        replanned.events.forEach(
            event => {

                const card =
                    document.createElement(
                        "div"
                    );


                card.className =
                    "result-card replanned";


                const start =
                    formatDateTime(
                        event.start
                    );


                const end =
                    formatDateTime(
                        event.end
                    );


                card.innerHTML = `
                    <div class="result-type">
                        ${escapeHtml(
                            event.type
                        )}
                    </div>

                    <h3>
                        ${escapeHtml(
                            event.name
                        )}
                    </h3>

                    <p>
                        ${start}
                        ${end ? " → " + end : ""}
                    </p>

                    <p>
                        ${escapeHtml(
                            event.location || ""
                        )}
                    </p>

                    <p>
                        Status:
                        ${escapeHtml(
                            event.status
                        )}
                    </p>
                `;


                resultBox.appendChild(
                    card
                );
            }
        );
    }


    if (communication) {

        const card =
            document.createElement(
                "div"
            );


        card.className =
            "communication";


        card.innerHTML = `
            <strong>
                Communication Draft
            </strong>

            <pre>${escapeHtml(
                communication.message || ""
            )}</pre>
        `;


        resultBox.appendChild(
            card
        );
    }


    if (
        data.response
    ) {

        const card =
            document.createElement(
                "div"
            );


        card.className =
            "communication";


        card.innerHTML = `
            <strong>
                Agent Summary
            </strong>

            <pre>${escapeHtml(
                data.response
            )}</pre>
        `;


        resultBox.appendChild(
            card
        );
    }


    if (
        !resultBox.children.length
    ) {

        resultBox.innerHTML = `
            <div class="error-card">
                The agent completed without producing
                a replanned schedule.
            </div>
        `;
    }
}


function formatDateTime(value) {

    if (!value) {
        return "";
    }


    const date =
        new Date(value);


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return value;
    }


    return date.toLocaleString(
        "en-IN",
        {
            dateStyle: "medium",
            timeStyle: "short"
        }
    );
}


function escapeHtml(value) {

    if (
        value === undefined ||
        value === null
    ) {

        return "";
    }


    return String(value)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );
}