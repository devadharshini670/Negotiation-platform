//NEGOTIATION STATUS

const NEGOTIATION_STATUS = {
    NOT_STARTED: "Not Started",
    IN_PROGRESS: "In Progress",
    AGREEMENT: "Agreement",
    REJECTED: "Rejected",
    DEADLOCK: "Deadlock",
    COMPLETED: "Completed"
};


//SCENARIOS

const scenarios = {

    vendor: {

        title: "Vendor Pricing",

        agents: [

            {
                name: "Buyer",
                role: "Customer",
                goal: "Get the lowest possible price",
                constraint: "Limited budget",
                icon: "👤"
            },

            {
                name: "Vendor",
                role: "Seller",
                goal: "Maximize profit",
                constraint: "Minimum selling price",
                icon: "🤖"
            }

        ],

        negotiation: {

            startingPrice: 1000,

            buyerTarget: 750,

            buyerWalkAway: 850,

            vendorTarget: 950,

            vendorMinimum: 800,

            increment: 25

        }

    },


    job: {

        title: "Job Offer",

        agents: [

            {
                name: "Candidate",
                role: "Job Seeker",
                goal: "Get better compensation",
                constraint: "Experience and skills",
                icon: "👤"
            },

            {
                name: "HR",
                role: "Employer",
                goal: "Control hiring cost",
                constraint: "Company budget",
                icon: "🤖"
            }

        ],

        negotiation: {

            startingPrice: 500000,

            candidateTarget: 650000,

            candidateWalkAway: 575000,

            hrTarget: 525000,

            hrMaximum: 625000,

            increment: 25000

        }

    },


    budget: {

        title: "Project Budget",

        agents: [

            {
                name: "Manager",
                role: "Project Lead",
                goal: "Get sufficient project funding",
                constraint: "Approval requirements",
                icon: "👤"
            },

            {
                name: "Finance",
                role: "Financial Controller",
                goal: "Control project spending",
                constraint: "Budget limit",
                icon: "🤖"
            }

        ],

        negotiation: {

            startingPrice: 1000000,

            managerTarget: 1400000,

            managerMinimum: 1250000,

            financeTarget: 1050000,

            financeMaximum: 1350000,

            increment: 50000

        }

    }

};



const personalityDefinitions = {

    Aggressive: {

        icon: "🔥",

        description:
            "Pushes hard, makes strong demands and concedes slowly.",

        concessionRate: 0.25,

        tolerance: 0.20,

        style: "firm"

    },


    Collaborative: {

        icon: "🤝",

        description:
            "Seeks a balanced solution and is willing to compromise.",

        concessionRate: 0.50,

        tolerance: 0.70,

        style: "cooperative"

    },


    "Risk-Averse": {

        icon: "🛡️",

        description:
            "Moves carefully and prefers predictable agreements.",

        concessionRate: 0.35,

        tolerance: 0.40,

        style: "careful"

    }

};



let messageTimer = null;

let autonomousTimer = null;

let autonomousRunId = 0;

let processingMessage = false;

let negotiationCompleted = false;

let chatInitialized = false;




function getCurrentScenario() {

    return localStorage.getItem("scenario");

}


function getAgentPersonalities() {

    const saved =
        localStorage.getItem("agentPersonalities");

    if (!saved) {

        return {
            agent1: null,
            agent2: null
        };

    }

    try {

        const parsed = JSON.parse(saved);

        return {

            agent1: parsed.agent1 || null,

            agent2: parsed.agent2 || null

        };

    } catch (error) {

        console.error(
            "Invalid personality data:",
            error
        );

        return {

            agent1: null,

            agent2: null

        };

    }

}


function getAgentPersonality(agentNumber) {

    const personalities =
        getAgentPersonalities();

    return personalities[
        `agent${agentNumber}`
    ] || null;

}




function selectScenario(type) {

    if (!scenarios[type]) {

        console.error(
            "Invalid scenario:",
            type
        );

        return;

    }

    localStorage.setItem(
        "scenario",
        type
    );

    localStorage.removeItem(
        "agentPersonalities"
    );

    localStorage.removeItem(
        "negotiationRounds"
    );

    localStorage.removeItem(
        "negotiationState"
    );

    window.location.href =
        "agents.html";

}




function selectRoundPreset(
    rounds,
    element
) {

    rounds = Number(rounds);

    if (
        !Number.isFinite(rounds) ||
        rounds < 3 ||
        rounds > 10
    ) {

        return;

    }

    document
        .querySelectorAll(".round-option")
        .forEach(option => {

            option.classList.remove(
                "selected"
            );

        });


    if (element) {

        element.classList.add(
            "selected"
        );

    }


    const customInput =
        document.getElementById(
            "customRounds"
        );


    if (customInput) {

        customInput.value = "";

    }


    localStorage.setItem(
        "negotiationRounds",
        rounds
    );


    updateRoundSelectionInfo(
        rounds
    );

    updateConfigurationSummary();

}


function setCustomRounds() {

    const input =
        document.getElementById(
            "customRounds"
        );

    if (!input) {

        return;

    }

    let rounds =
        Number(input.value);


    if (
        !Number.isFinite(rounds)
    ) {

        rounds = 5;

    }


    rounds =
        Math.max(
            3,
            Math.min(
                10,
                Math.floor(rounds)
            )
        );


    input.value = rounds;


    document
        .querySelectorAll(".round-option")
        .forEach(option => {

            option.classList.remove(
                "selected"
            );

        });


    localStorage.setItem(
        "negotiationRounds",
        rounds
    );


    updateRoundSelectionInfo(
        rounds
    );

    updateConfigurationSummary();

}


function getSelectedRounds() {

    const saved =
        Number(
            localStorage.getItem(
                "negotiationRounds"
            )
        );


    if (
        Number.isFinite(saved) &&
        saved >= 3 &&
        saved <= 10
    ) {

        return saved;

    }


    return 5;

}


function updateRoundSelectionInfo(
    rounds
) {

    const element =
        document.getElementById(
            "roundSelectionInfo"
        );


    if (element) {

        element.textContent =
            `Negotiation length: ${rounds} rounds`;

    }

}



function loadAgentConfiguration() {

    const container =
        document.getElementById(
            "agents"
        );

    if (!container) {

        return;

    }


    const scenarioKey =
        getCurrentScenario();


    const data =
        scenarios[scenarioKey];


    if (!data) {

        window.location.href =
            "index.html";

        return;

    }


    const title =
        document.getElementById(
            "scenarioName"
        );


    if (title) {

        title.textContent =
            data.title;

    }


    container.innerHTML = "";


    data.agents.forEach(
        (agent, index) => {

            const card =
                document.createElement(
                    "div"
                );


            card.className =
                "agent-card";


            card.innerHTML = `

                <div class="agent-number">
                    Agent ${index + 1}
                </div>

                <div class="agent-icon">
                    ${agent.icon}
                </div>

                <h3>
                    ${agent.name}
                </h3>

                <p>
                    <strong>Role:</strong>
                    ${agent.role}
                </p>

                <p>
                    <strong>Goal:</strong>
                    ${agent.goal}
                </p>

                <p>
                    <strong>Constraint:</strong>
                    ${agent.constraint}
                </p>

                <div class="agent-personality-display">

                    <strong>
                        Selected Personality:
                    </strong>

                    <span id="selectedPersonality${index + 1}">
                        Not Selected
                    </span>

                </div>
            `;


            container.appendChild(card);

        }
    );


    createPersonalitySelection(
        data.agents
    );


    initializeRoundSettings();

    updateConfigurationSummary();

}



function createPersonalitySelection(
    agents
) {

    const container =
        document.getElementById(
            "personalityContainer"
        );


    if (!container) {

        return;

    }


    container.innerHTML = "";


    agents.forEach(
        (agent, index) => {

            const agentNumber =
                index + 1;


            const section =
                document.createElement(
                    "div"
                );


            section.className =
                "agent-personality-section";


            section.innerHTML = `

                <div class="agent-personality-header">

                    <div class="personality-agent-icon">
                        ${agent.icon}
                    </div>

                    <div>

                        <h3>
                            ${agent.name} Personality
                        </h3>

                        <p>
                            Choose a personality specifically for ${agent.name}.
                        </p>

                    </div>

                </div>

                <div class="personality-options">

                    ${createPersonalityOptions(
                        agentNumber
                    )}

                </div>
            `;


            container.appendChild(
                section
            );

        }
    );


    loadAgentPersonalities();

}


function createPersonalityOptions(
    agentNumber
) {

    let html = "";


    Object.keys(
        personalityDefinitions
    ).forEach(
        personality => {

            const definition =
                personalityDefinitions[
                    personality
                ];


            html += `

                <div
                    class="personality-option"
                    data-agent="${agentNumber}"
                    data-personality="${personality}"
                    onclick="selectAgentPersonality(${agentNumber}, '${personality}', this)"
                >

                    <div class="personality-option-top">

                        <span class="personality-option-icon">
                            ${definition.icon}
                        </span>

                        <span>
                            ${personality}
                        </span>

                    </div>

                    <p>
                        ${definition.description}
                    </p>

                </div>
            `;

        }
    );


    return html;

}


function selectAgentPersonality(
    agentNumber,
    personality,
    element
) {

    if (
        !personalityDefinitions[
            personality
        ]
    ) {

        return;

    }


    const personalities =
        getAgentPersonalities();


    personalities[
        `agent${agentNumber}`
    ] =
        personality;


    localStorage.setItem(
        "agentPersonalities",
        JSON.stringify(
            personalities
        )
    );


    document
        .querySelectorAll(
            `.personality-option[data-agent="${agentNumber}"]`
        )
        .forEach(option => {

            option.classList.remove(
                "selected"
            );

        });


    if (element) {

        element.classList.add(
            "selected"
        );

    }


    updateAgentPersonalityDisplay(
        agentNumber,
        personality
    );


    updateConfigurationSummary();

}


function updateAgentPersonalityDisplay(
    agentNumber,
    personality
) {

    const display =
        document.getElementById(
            `selectedPersonality${agentNumber}`
        );


    if (!display) {

        return;

    }


    const definition =
        personalityDefinitions[
            personality
        ];


    if (!definition) {

        display.textContent =
            "Not Selected";

        return;

    }


    display.textContent =
        `${definition.icon} ${personality}`;

}


function loadAgentPersonalities() {

    const personalities =
        getAgentPersonalities();


    ["agent1", "agent2"]
        .forEach(agentKey => {

            const personality =
                personalities[
                    agentKey
                ];


            if (!personality) {

                return;

            }


            const agentNumber =
                agentKey.replace(
                    "agent",
                    ""
                );


            const option =
                document.querySelector(
                    `.personality-option[data-agent="${agentNumber}"][data-personality="${personality}"]`
                );


            if (option) {

                option.classList.add(
                    "selected"
                );

            }


            updateAgentPersonalityDisplay(
                Number(agentNumber),
                personality
            );

        });

}



function updateConfigurationSummary() {

    const summary =
        document.getElementById(
            "configurationSummary"
        );


    if (!summary) {

        return;

    }


    const personalities =
        getAgentPersonalities();


    const rounds =
        getSelectedRounds();


    const scenarioKey =
        getCurrentScenario();


    const data =
        scenarios[scenarioKey];


    if (!data) {

        return;

    }


    const p1 =
        personalities.agent1;


    const p2 =
        personalities.agent2;


    if (!p1 || !p2) {

        summary.innerHTML = `

            <div class="summary-warning">

                ⚠️ Select a personality for both agents.

            </div>

        `;

        return;

    }


    summary.innerHTML = `

        <div class="summary-grid">

            <div>

                <span>
                    Agent 1
                </span>

                <strong>
                    ${data.agents[0].icon}
                    ${data.agents[0].name}
                </strong>

                <small>
                    ${personalityDefinitions[p1].icon}
                    ${p1}
                </small>

            </div>


            <div>

                <span>
                    Agent 2
                </span>

                <strong>
                    ${data.agents[1].icon}
                    ${data.agents[1].name}
                </strong>

                <small>
                    ${personalityDefinitions[p2].icon}
                    ${p2}
                </small>

            </div>


            <div>

                <span>
                    Negotiation Length
                </span>

                <strong>
                    ${rounds} Rounds
                </strong>

                <small>
                    Autonomous multi-agent simulation
                </small>

            </div>

        </div>
    `;

}




function initializeRoundSettings() {

    const rounds =
        getSelectedRounds();


    localStorage.setItem(
        "negotiationRounds",
        rounds
    );


    const preset =
        document.querySelector(
            `.round-option[data-rounds="${rounds}"]`
        );


    if (preset) {

        preset.classList.add(
            "selected"
        );

    }


    const customInput =
        document.getElementById(
            "customRounds"
        );


    if (
        customInput &&
        ![3, 5, 8].includes(rounds)
    ) {

        customInput.value =
            rounds;

    }


    updateRoundSelectionInfo(
        rounds
    );

}



function createNegotiationState() {

    const scenarioKey =
        getCurrentScenario();


    const data =
        scenarios[scenarioKey];


    if (!data) {

        return null;

    }


    const personalities =
        getAgentPersonalities();


    const maxRounds =
        getSelectedRounds();


    const state = {

        scenario:
            scenarioKey,

        scenarioTitle:
            data.title,

        currentRound:
            1,

        maxRounds:
            maxRounds,

        currentAgentTurn:
            1,

        previousOffer:
            null,

        currentOffer:
            null,

        negotiationStatus:
            NEGOTIATION_STATUS.NOT_STARTED,

        agentGoals: {

            agent1:
                data.agents[0].goal,

            agent2:
                data.agents[1].goal

        },

        agentConstraints: {

            agent1:
                data.agents[0].constraint,

            agent2:
                data.agents[1].constraint

        },

        agentPersonality: {

            agent1:
                personalities.agent1,

            agent2:
                personalities.agent2

        },

        negotiationHistory: [],

        offerHistory: [],

        decisions: [],

        usedOffers: [],

        lastOfferByAgent: {

            agent1: null,

            agent2: null

        },

        concessions: {

            agent1: [],

            agent2: []

        },

        agreementValue:
            null,

        rejectionReason:
            null,

        deadlockReason:
            null,

        startedAt:
            null,

        completedAt:
            null

    };


    saveNegotiationState(
        state
    );


    return state;

}


function getNegotiationState() {

    const saved =
        localStorage.getItem(
            "negotiationState"
        );


    if (!saved) {

        return createNegotiationState();

    }


    try {

        return JSON.parse(
            saved
        );

    } catch (error) {

        console.error(
            "Invalid negotiation state:",
            error
        );


        return createNegotiationState();

    }

}


function saveNegotiationState(
    state
) {

    localStorage.setItem(
        "negotiationState",
        JSON.stringify(state)
    );

}



function getAgent1() {

    const scenario =
        scenarios[
            getCurrentScenario()
        ];


    return scenario
        ? scenario.agents[0].name
        : "Agent 1";

}


function getAgent2() {

    const scenario =
        scenarios[
            getCurrentScenario()
        ];


    return scenario
        ? scenario.agents[1].name
        : "Agent 2";

}




function formatCurrency(
    value
) {

    if (
        value === null ||
        value === undefined ||
        Number.isNaN(
            Number(value)
        )
    ) {

        return "—";

    }


    return new Intl.NumberFormat(
        "en-IN",
        {

            style: "currency",

            currency: "INR",

            maximumFractionDigits: 0

        }
    ).format(
        Number(value)
    );

}


function getLastOffer(
    state,
    agentNumber
) {

    if (
        !state ||
        !state.lastOfferByAgent
    ) {

        return null;

    }


    return state.lastOfferByAgent[
        `agent${agentNumber}`
    ];

}



function getBuyerAcceptanceLimit(
    personality
) {

    if (
        personality ===
        "Aggressive"
    ) {

        return 825;

    }


    if (
        personality ===
        "Collaborative"
    ) {

        return 850;

    }


    return 840;

}


function getVendorAcceptanceLimit(
    personality
) {

    if (
        personality ===
        "Aggressive"
    ) {

        return 925;

    }


    if (
        personality ===
        "Collaborative"
    ) {

        return 850;

    }


    return 875;

}




function calculateInitialOffer(
    state,
    agentNumber
) {

    const n =
        scenarios[
            state.scenario
        ].negotiation;


    const personality =
        state.agentPersonality[
            `agent${agentNumber}`
        ];


 

    if (
        state.scenario ===
        "vendor"
    ) {

        if (
            agentNumber === 1
        ) {

            if (
                personality ===
                "Aggressive"
            ) {

                return 700;

            }


            if (
                personality ===
                "Collaborative"
            ) {

                return 775;

            }


            return 750;

        }


        if (
            personality ===
            "Aggressive"
        ) {

            return 1000;

        }


        if (
            personality ===
            "Collaborative"
        ) {

            return 925;

        }


        return 950;

    }


  

    if (
        state.scenario ===
        "job"
    ) {

        if (
            agentNumber === 1
        ) {

            if (
                personality ===
                "Aggressive"
            ) {

                return 700000;

            }


            if (
                personality ===
                "Collaborative"
            ) {

                return 650000;

            }


            return 625000;

        }


        return n.startingPrice;

    }




    if (
        state.scenario ===
        "budget"
    ) {

        if (
            agentNumber === 1
        ) {

            if (
                personality ===
                "Aggressive"
            ) {

                return 1500000;

            }


            if (
                personality ===
                "Collaborative"
            ) {

                return 1400000;

            }


            return 1350000;

        }


        return n.startingPrice;

    }


    return n.startingPrice;

}

// COUNTER OFFER

function calculateCounterOffer(
    state,
    agentNumber
) {

    const n =
        scenarios[
            state.scenario
        ].negotiation;


    const personality =
        state.agentPersonality[
            `agent${agentNumber}`
        ];


    const previous =
        getLastOffer(
            state,
            agentNumber
        );


    const otherAgent =
        agentNumber === 1
            ? 2
            : 1;


    const otherOffer =
        getLastOffer(
            state,
            otherAgent
        );


    if (
        previous === null ||
        previous === undefined
    ) {

        return calculateInitialOffer(
            state,
            agentNumber
        );

    }


    if (
        otherOffer === null ||
        otherOffer === undefined
    ) {

        return calculateInitialOffer(
            state,
            agentNumber
        );

    }


    const definition =
        personalityDefinitions[
            personality
        ];


    const rate =
        definition
            ? definition.concessionRate
            : 0.35;


    let offer =
        Number(previous);


    //VENDOR

    if (
        state.scenario ===
        "vendor"
    ) {

        if (
            agentNumber === 1
        ) {

            const difference =
                Number(otherOffer) -
                Number(previous);


            offer =
                Number(previous) +
                Math.round(
                    difference * rate
                );


            offer =
                Math.min(
                    n.buyerWalkAway,
                    offer
                );


            offer =
                Math.max(
                    n.buyerTarget,
                    offer
                );

        } else {

            const difference =
                Number(previous) -
                Number(otherOffer);


            offer =
                Number(previous) -
                Math.round(
                    difference * rate
                );


            offer =
                Math.max(
                    n.vendorMinimum,
                    offer
                );


            offer =
                Math.min(
                    n.startingPrice,
                    offer
                );

        }

    }


    // JOB
    

    if (
        state.scenario ===
        "job"
    ) {

        if (
            agentNumber === 1
        ) {

            const difference =
                Number(previous) -
                Number(otherOffer);


            offer =
                Number(previous) -
                Math.round(
                    difference * rate
                );


            offer =
                Math.max(
                    n.candidateWalkAway,
                    offer
                );


            offer =
                Math.min(
                    n.candidateTarget,
                    offer
                );

        } else {

            const difference =
                Number(otherOffer) -
                Number(previous);


            offer =
                Number(previous) +
                Math.round(
                    difference * rate
                );


            offer =
                Math.min(
                    n.hrMaximum,
                    offer
                );


            offer =
                Math.max(
                    n.hrTarget,
                    offer
                );

        }

    }


    //BUDGET

    if (
        state.scenario ===
        "budget"
    ) {

        if (
            agentNumber === 1
        ) {

            const difference =
                Number(previous) -
                Number(otherOffer);


            offer =
                Number(previous) -
                Math.round(
                    difference * rate
                );


            offer =
                Math.max(
                    n.managerMinimum,
                    offer
                );


            offer =
                Math.min(
                    n.managerTarget,
                    offer
                );

        } else {

            const difference =
                Number(otherOffer) -
                Number(previous);


            offer =
                Number(previous) +
                Math.round(
                    difference * rate
                );


            offer =
                Math.min(
                    n.financeMaximum,
                    offer
                );


            offer =
                Math.max(
                    n.financeTarget,
                    offer
                );

        }

    }


    return roundToIncrement(
        offer,
        n.increment
    );

}


// ROUND TO INCREMENT

function roundToIncrement(
    value,
    increment
) {

    if (!increment) {

        return Math.round(
            value
        );

    }


    return Math.round(
        Number(value) /
        Number(increment)
    ) *
    Number(increment);

}

// CREATE OFFER OBJECT

function createOfferObject(
    state,
    agentNumber,
    value,
    reason,
    metadata = {}
) {

    return {

        id:
            `offer-${Date.now()}-${Math.random()
                .toString(36)
                .slice(2, 8)}`,

        agent:
            agentNumber,

        agentName:
            agentNumber === 1
                ? getAgent1()
                : getAgent2(),

        round:
            state.currentRound,

        value:
            value,

        offerValue:
            value,

        reason:
            reason,

        metadata:
            metadata,

        timestamp:
            new Date().toISOString(),

        decision:
            null

    };

}


//  CONCESSION TRACKING

function trackConcession(
    state,
    agentNumber,
    value
) {

    const key =
        `agent${agentNumber}`;


    const previous =
        state.lastOfferByAgent[key];


    if (
        previous === null ||
        previous === undefined
    ) {

        state.concessions[key].push({

            from: null,

            to: value,

            change: 0,

            round:
                state.currentRound

        });

        return;

    }


    let change = 0;


    

    if (
        agentNumber === 1
    ) {

        change =
            Math.max(
                0,
                Number(previous) -
                Number(value)
            );

    }



    else {

        change =
            Math.max(
                0,
                Number(value) -
                Number(previous)
            );

    }


    state.concessions[key].push({

        from:
            previous,

        to:
            value,

        change:
            change,

        round:
            state.currentRound

    });

}


//  CREATE OFFER

function createOffer(
    state,
    agentNumber
) {

    const n =
        scenarios[
            state.scenario
        ].negotiation;


    const previous =
        getLastOffer(
            state,
            agentNumber
        );


    let value;


  

    if (
        previous === null ||
        previous === undefined
    ) {

        value =
            calculateInitialOffer(
                state,
                agentNumber
            );

    } else {

        value =
            calculateCounterOffer(
                state,
                agentNumber
            );

    }


    value =
        Number(value);


    if (
        !Number.isFinite(value)
    ) {

        value =
            Number(n.startingPrice);

    }


    // SCENARIO LIMITS

    if (
        state.scenario ===
        "vendor"
    ) {

        if (
            agentNumber === 1
        ) {

            value =
                Math.max(
                    n.buyerTarget,
                    Math.min(
                        n.buyerWalkAway,
                        value
                    )
                );

        } else {

            

            value =
                Math.max(
                    n.vendorMinimum,
                    Math.min(
                        n.startingPrice,
                        value
                    )
                );

        }

    }


    if (
        state.scenario ===
        "job"
    ) {

        if (
            agentNumber === 1
        ) {

            value =
                Math.max(
                    n.candidateWalkAway,
                    Math.min(
                        n.candidateTarget,
                        value
                    )
                );

        } else {

            value =
                Math.max(
                    n.hrTarget,
                    Math.min(
                        n.hrMaximum,
                        value
                    )
                );

        }

    }


    if (
        state.scenario ===
        "budget"
    ) {

        if (
            agentNumber === 1
        ) {

            value =
                Math.max(
                    n.managerMinimum,
                    Math.min(
                        n.managerTarget,
                        value
                    )
                );

        } else {

            value =
                Math.max(
                    n.financeTarget,
                    Math.min(
                        n.financeMaximum,
                        value
                    )
                );

        }

    }


    value =
        roundToIncrement(
            value,
            n.increment
        );



    if (
        state.scenario ===
        "vendor"
    ) {

        if (
            agentNumber === 1
        ) {

            value =
                Math.max(
                    n.buyerTarget,
                    Math.min(
                        n.buyerWalkAway,
                        value
                    )
                );

        } else {

            value =
                Math.max(
                    n.vendorMinimum,
                    Math.min(
                        n.startingPrice,
                        value
                    )
                );

        }

    }


    if (
        state.scenario ===
        "job"
    ) {

        if (
            agentNumber === 1
        ) {

            value =
                Math.max(
                    n.candidateWalkAway,
                    Math.min(
                        n.candidateTarget,
                        value
                    )
                );

        } else {

            value =
                Math.max(
                    n.hrTarget,
                    Math.min(
                        n.hrMaximum,
                        value
                    )
                );

        }

    }


    if (
        state.scenario ===
        "budget"
    ) {

        if (
            agentNumber === 1
        ) {

            value =
                Math.max(
                    n.managerMinimum,
                    Math.min(
                        n.managerTarget,
                        value
                    )
                );

        } else {

            value =
                Math.max(
                    n.financeTarget,
                    Math.min(
                        n.financeMaximum,
                        value
                    )
                );

        }

    }


  

    const duplicate =
        state.usedOffers.some(
            offer =>
                offer.agent ===
                    agentNumber &&
                Number(offer.value) ===
                    Number(value)
        );


    if (duplicate) {

        const possibleMoves =
            agentNumber === 1

                ? [
                    value + n.increment,
                    value + n.increment * 2,
                    value - n.increment
                ]

                : [
                    value - n.increment,
                    value - n.increment * 2,
                    value + n.increment
                ];


        for (
            const candidate
            of possibleMoves
        ) {

            let valid = true;


            if (
                state.scenario ===
                "vendor"
            ) {

                if (
                    agentNumber === 1
                ) {

                    valid =
                        candidate >=
                            n.buyerTarget &&
                        candidate <=
                            n.buyerWalkAway;

                } else {

                    valid =
                        candidate >=
                            n.vendorMinimum &&
                        candidate <=
                            n.startingPrice;

                }

            }


            if (
                state.scenario ===
                "job"
            ) {

                if (
                    agentNumber === 1
                ) {

                    valid =
                        candidate >=
                            n.candidateWalkAway &&
                        candidate <=
                            n.candidateTarget;

                } else {

                    valid =
                        candidate >=
                            n.hrTarget &&
                        candidate <=
                            n.hrMaximum;

                }

            }


            if (
                state.scenario ===
                "budget"
            ) {

                if (
                    agentNumber === 1
                ) {

                    valid =
                        candidate >=
                            n.managerMinimum &&
                        candidate <=
                            n.managerTarget;

                } else {

                    valid =
                        candidate >=
                            n.financeTarget &&
                        candidate <=
                            n.financeMaximum;

                }

            }


            const alreadyUsed =
                state.usedOffers.some(
                    offer =>
                        offer.agent ===
                            agentNumber &&
                        Number(
                            offer.value
                        ) ===
                            Number(
                                candidate
                            )
                );


            if (
                valid &&
                !alreadyUsed
            ) {

                value =
                    candidate;

                break;

            }

        }

    }



    if (
        state.scenario ===
            "vendor" &&
        agentNumber === 2
    ) {

        value =
            Math.max(
                n.vendorMinimum,
                Math.min(
                    n.startingPrice,
                    value
                )
            );

    }


    return value;

}


//  OFFER REASON

function generateOfferReason(
    state,
    agentNumber,
    value
) {

    const previous =
        getLastOffer(
            state,
            agentNumber
        );


    const otherAgent =
        agentNumber === 1
            ? 2
            : 1;


    const otherOffer =
        getLastOffer(
            state,
            otherAgent
        );


    if (
        previous === null ||
        previous === undefined
    ) {

        return "Initial negotiation position";

    }


    if (
        otherOffer !== null &&
        otherOffer !== undefined
    ) {

        return "Responding to the previous offer";

    }


    return "Adjusting negotiation position";

}


// DECISION ENGINE



function decideOffer(
    state,
    agentNumber,
    incomingOffer
) {

    const n =
        scenarios[
            state.scenario
        ].negotiation;


    const personality =
        state.agentPersonality[
            `agent${agentNumber}`
        ];


    const round =
        Number(
            state.currentRound || 1
        );


    const value =
        Number(incomingOffer);


    if (
        !Number.isFinite(value)
    ) {

        return "Counteroffer";

    }


    // VENDOR PRICING

    if (
        state.scenario ===
        "vendor"
    ) {

       

        if (
            agentNumber === 1
        ) {

            const acceptLimit =
                getBuyerAcceptanceLimit(
                    personality
                );


            if (
                value <=
                acceptLimit
            ) {

                return "Accept";

            }



            if (
                round >= 2 &&
                value >
                    n.buyerWalkAway +
                    n.increment * 2
            ) {

                return "Reject";

            }


            return "Counteroffer";

        }


        

        const vendorAcceptLimit =
            getVendorAcceptanceLimit(
                personality
            );


        if (
            value >=
            vendorAcceptLimit
        ) {

            return "Accept";

        }


       

        const extremeLow =
            n.vendorMinimum -
            n.increment * 2;


        if (
            round >= 3 &&
            value <
                extremeLow
        ) {

            return "Reject";

        }


        return "Counteroffer";

    }


    //  JOB OFFER

    if (
        state.scenario ===
        "job"
    ) {

     

        if (
            agentNumber === 1
        ) {

            if (
                value >=
                n.candidateWalkAway +
                25000
            ) {

                return "Accept";

            }


            if (
                round >= 3 &&
                value <
                    n.candidateWalkAway -
                    25000
            ) {

                return "Reject";

            }


            return "Counteroffer";

        }


        if (
            value >=
                n.hrTarget &&
            value <=
                n.hrMaximum
        ) {

            if (
                personality ===
                "Collaborative"
            ) {

                return "Accept";

            }


            if (
                value <=
                600000
            ) {

                return "Accept";

            }

        }


        if (
            round >= 3 &&
            value >
                n.hrMaximum +
                n.increment
        ) {

            return "Reject";

        }


        return "Counteroffer";

    }

// PROJECT BUDGET

    if (
        state.scenario ===
        "budget"
    ) {

        //MANAGER evaluates Finance's budget.
        

        if (
            agentNumber === 1
        ) {

            if (
                value >=
                1350000
            ) {

                return "Accept";

            }


            if (
                round >= 3 &&
                value <
                    n.managerMinimum -
                    n.increment
            ) {

                return "Reject";

            }


            return "Counteroffer";

        }


        //FINANCE evaluates Manager's request.
         

        if (
            value <=
            n.financeMaximum
        ) {

            if (
                value >=
                1250000
            ) {

                return "Accept";

            }


            if (
                personality ===
                    "Collaborative" &&
                value >=
                    1200000
            ) {

                return "Accept";

            }

        }


        if (
            round >= 3 &&
            value >
                n.financeMaximum +
                n.increment
        ) {

            return "Reject";

        }


        return "Counteroffer";

    }


    return "Counteroffer";

}


//AGREEMENT CHECK

function checkAgreement(
    state,
    value,
    agentNumber
) {

    const otherAgent =
        agentNumber === 1
            ? 2
            : 1;


    const otherOffer =
        getLastOffer(
            state,
            otherAgent
        );


    if (
        otherOffer === null ||
        otherOffer === undefined
    ) {

        return false;

    }


    const difference =
        Math.abs(
            Number(value) -
            Number(otherOffer)
        );


    if (
        state.scenario ===
        "vendor"
    ) {

        return (
            Number(value) >= 800 &&
            Number(value) <= 850 &&
            difference <= 25
        );

    }


    if (
        state.scenario ===
        "job"
    ) {

        return (
            Number(value) >= 575000 &&
            Number(value) <= 625000 &&
            difference <= 25000
        );

    }


    if (
        state.scenario ===
        "budget"
    ) {

        return (
            Number(value) >= 1250000 &&
            Number(value) <= 1350000 &&
            difference <= 50000
        );

    }


    return false;

}
//  RECORD OFFER

function recordOffer(
    state,
    agentNumber,
    text,
    value
) {

    const reason =
        generateOfferReason(
            state,
            agentNumber,
            value
        );


    const otherAgent =
        agentNumber === 1
            ? 2
            : 1;


    const incomingOffer =
        getLastOffer(
            state,
            otherAgent
        );


    const offer =
        createOfferObject(
            state,
            agentNumber,
            value,
            reason,
            {

                scenario:
                    state.scenario,

                negotiationRound:
                    state.currentRound

            }
        );


    state.previousOffer =
        state.currentOffer;


    state.currentOffer =
        offer;


    state.lastOfferByAgent[
        `agent${agentNumber}`
    ] =
        value;


    state.offerHistory.push(
        offer
    );


    state.usedOffers.push({

        agent:
            agentNumber,

        value:
            value

    });


    state.negotiationHistory.push({

        round:
            state.currentRound,

        agent:
            agentNumber,

        agentName:
            agentNumber === 1
                ? getAgent1()
                : getAgent2(),

        text:
            text,

        offerValue:
            value,

        timestamp:
            offer.timestamp

    });


    trackConcession(
        state,
        agentNumber,
        value
    );

    let decision =
        "Counteroffer";


    if (
        incomingOffer !== null &&
        incomingOffer !== undefined
    ) {

        decision =
            decideOffer(
                state,
                agentNumber,
                incomingOffer
            );

    }



    let agreementValue =
        null;


    if (
        decision ===
        "Accept"
    ) {

        agreementValue =
            Number(incomingOffer);

    }


    offer.decision =
        decision;


    state.decisions.push({

        agent:
            agentNumber,

        agentName:
            agentNumber === 1
                ? getAgent1()
                : getAgent2(),

        round:
            state.currentRound,

        decision:
            decision,

        offerValue:
            value,

        incomingOffer:
            incomingOffer,

        timestamp:
            offer.timestamp

    });


    return {

        offer:
            offer,

        decision:
            decision,

        incomingOffer:
            incomingOffer,

        agreementValue:
            agreementValue

    };

}



function finalizeDecision(
    state,
    result,
    agentNumber,
    value
) {

    const decision =
        result.decision;


    if (
        decision ===
        "Accept"
    ) {

        state.negotiationStatus =
            NEGOTIATION_STATUS.AGREEMENT;


        state.agreementValue =
            result.agreementValue !==
                null &&
            result.agreementValue !==
                undefined

                ? result.agreementValue

                : value;


        state.completedAt =
            new Date().toISOString();


        return;

    }



    if (
        decision ===
        "Reject"
    ) {

        state.negotiationStatus =
            NEGOTIATION_STATUS.REJECTED;


        state.rejectionReason =
            `${
                agentNumber === 1
                    ? getAgent1()
                    : getAgent2()
            } rejected the offer because it falls outside the acceptable negotiation constraint.`;


        return;

    }


    // DEADLOCK

    if (
        detectDeadlock(
            state
        )
    ) {

        state.negotiationStatus =
            NEGOTIATION_STATUS.DEADLOCK;


        state.deadlockReason =
            "The agents could not move within an acceptable negotiation range.";


        return;

    }


    /*
     * NORMAL NEGOTIATION
     */

    state.negotiationStatus =
        NEGOTIATION_STATUS.IN_PROGRESS;

}


// DEADLOCK DETECTION

function detectDeadlock(
    state
) {

    if (!state) {

        return false;

    }



    if (
        state.currentRound <=
        state.maxRounds
    ) {

        return false;

    }


    return false;

}


//MESSAGE GENERATOR 

function generateNegotiationMessage(
    state,
    agentNumber,
    offerValue,
    type
) {

    const data =
        scenarios[
            state.scenario
        ];


    const agent =
        data.agents[
            agentNumber - 1
        ];


    const personality =
        state.agentPersonality[
            `agent${agentNumber}`
        ];


    const otherName =
        agentNumber === 1
            ? getAgent2()
            : getAgent1();


    const previous =
        getLastOffer(
            state,
            agentNumber
        );


    // INITIAL OFFER
     

    if (
        type ===
        "initial"
    ) {

        if (
            personality ===
            "Aggressive"
        ) {

            return `
                I'm opening at ${formatCurrency(offerValue)}.
                This is a firm starting position, ${otherName}.
            `.replace(/\s+/g, " ").trim();

        }


        if (
            personality ===
            "Collaborative"
        ) {

            return `
                I'd like to start at ${formatCurrency(offerValue)}.
                I'm open to working together to reach a fair agreement.
            `.replace(/\s+/g, " ").trim();

        }


        if (
            personality ===
            "Risk-Averse"
        ) {

            return `
                My initial position is ${formatCurrency(offerValue)}.
                I want to proceed carefully and evaluate each proposal.
            `.replace(/\s+/g, " ").trim();

        }


        return `
            My opening position is ${formatCurrency(offerValue)}.
            Let's see if we can reach a competitive deal.
        `.replace(/\s+/g, " ").trim();

    }


   // counter offer
    if (
        previous !== null &&
        previous !== undefined
    ) {

        if (
            personality ===
            "Aggressive"
        ) {

            return `
                I've adjusted my position to ${formatCurrency(offerValue)},
                but I expect a meaningful response in return.
            `.replace(/\s+/g, " ").trim();

        }


        if (
            personality ===
            "Collaborative"
        ) {

            return `
                I can move to ${formatCurrency(offerValue)}.
                That is a constructive step toward a mutually beneficial agreement.
            `.replace(/\s+/g, " ").trim();

        }


        if (
            personality ===
            "Risk-Averse"
        ) {

            return `
                After reviewing the previous proposal,
                I can cautiously move to ${formatCurrency(offerValue)}.
            `.replace(/\s+/g, " ").trim();

        }


        return `
            I'm revising my offer to ${formatCurrency(offerValue)}.
            This is my current position.
        `.replace(/\s+/g, " ").trim();

    }


    return `
        ${agent.name} proposes ${formatCurrency(offerValue)}.
    `.replace(/\s+/g, " ").trim();

}


function createAgentInputStructure(state, agentNumber) {

    if (!state) {
        return null;
    }

    const data = scenarios[state.scenario];

    if (!data || !data.agents[agentNumber - 1]) {
        return null;
    }

    const agent = data.agents[agentNumber - 1];
    const opponentAgentNumber = agentNumber === 1 ? 2 : 1;

    return {
    agentNumber: agentNumber,
    agentPersona: state.agentPersonality[`agent${agentNumber}`],
    role: agent.role,
    goals: agent.goal,
    constraints: agent.constraint,
    currentNegotiationState: state,
    previousConversationHistory: state.negotiationHistory,
    currentOpponentOffer: getLastOffer(state, opponentAgentNumber)
};
}
function generate_agent_response(
    agent_profile,
    negotiation_state,
    history
) {

    if (
        !agent_profile ||
        !negotiation_state
    ) {
        return null;
    }

    const agentNumber =
        agent_profile.agentNumber;

    if (
        agentNumber !== 1 &&
        agentNumber !== 2
    ) {
        return null;
    }

    const offerValue =
        createOffer(
            negotiation_state,
            agentNumber
        );

    const previous =
        getLastOffer(
            negotiation_state,
            agentNumber
        );

    const type =
        previous === null ||
        previous === undefined
            ? "initial"
            : "counter";

    const message =
        generateNegotiationMessage(
            negotiation_state,
            agentNumber,
            offerValue,
            type
        );

    return {
        agentNumber: agentNumber,
        offerValue: offerValue,
        message: message,
        type: type,
        history: history || []
    };
}
// ORCHESTRATOR
const Orchestrator = {


    getCurrentAgent(state) {

        return state.currentAgentTurn;

    },


    getCurrentRound(state) {

        return state.currentRound;

    },


    getHistory(state) {

        return state.negotiationHistory;

    },


    getCurrentState(state) {

        return state.negotiationStatus;

    },


    getNextAgent(state) {

        return state.currentAgentTurn === 1
            ? 2
            : 1;

    },
        buildAgentInput(state) {

        const agentNumber =
            this.getCurrentAgent(state);

        return createAgentInputStructure(
            state,
            agentNumber
        );

    },


    getAgentResponse(state) {

        const agentInput =
            this.buildAgentInput(state);

        return generate_agent_response(
            agentInput,
            state,
            state.negotiationHistory
        );

    },

    nextTurn(state) {

        state.currentAgentTurn =
            state.currentAgentTurn === 1
                ? 2
                : 1;

    },


    nextRound(state) {

        state.currentRound =
            Number(
                state.currentRound
            ) + 1;


        state.currentAgentTurn =
            1;

    }

};

//  MESSAGE TYPING

function typeMessage(
    text,
    element,
    speed = 8,
    callback
) {

    if (!element) {

        return;

    }


    let index = 0;


    element.textContent = "";


    function typing() {

        if (
            index <
            text.length
        ) {

            element.textContent +=
                text.charAt(index);


            index++;


            setTimeout(
                typing,
                speed
            );

        } else if (
            callback
        ) {

            callback();

        }

    }


    typing();

}

// ADD CHAT MESSAGE

function addMessage(
    name,
    text,
    side,
    avatar,
    decision = null,
    offerValue = null
) {

    const chat =
        document.getElementById(
            "chatBox"
        );


    if (!chat) {

        return;

    }


    const message =
        document.createElement(
            "div"
        );


    message.className =
        `message ${side}`;


    const messageAvatar =
        document.createElement(
            "div"
        );


    messageAvatar.className =
        "message-avatar";


    messageAvatar.textContent =
        avatar ||
        (
            side === "left"
                ? "👤"
                : "🤖"
        );


    const content =
        document.createElement(
            "div"
        );


    content.className =
        "message-content";


    const sender =
        document.createElement(
            "div"
        );


    sender.className =
        "sender-name";


    sender.textContent =
        name;


    const textElement =
        document.createElement(
            "div"
        );


    textElement.className =
        "message-text";


    content.appendChild(
        sender
    );


    content.appendChild(
        textElement
    );


    if (
        offerValue !== null
    ) {

        const offerLabel =
            document.createElement(
                "div"
            );


        offerLabel.className =
            "offer-value";


        offerLabel.textContent =
            `Offer: ${formatCurrency(
                offerValue
            )}`;


        content.appendChild(
            offerLabel
        );

    }


    if (decision) {

        const badge =
            document.createElement(
                "span"
            );


        badge.className =
            `decision-badge decision-${decision.toLowerCase()}`;


        badge.textContent =
            decision;


        content.appendChild(
            badge
        );

    }


    message.appendChild(
        messageAvatar
    );


    message.appendChild(
        content
    );


    chat.appendChild(
        message
    );


    chat.scrollTop =
        chat.scrollHeight;


    typeMessage(
        text,
        textElement,
        6
    );

}

// SYSTEM MESSAGE

function addSystemMessage(
    text
) {

    const chat =
        document.getElementById(
            "chatBox"
        );


    if (!chat) {

        return;

    }


    const message =
        document.createElement(
            "div"
        );


    message.className =
        "message system";


    message.innerHTML = `

        <div class="message-avatar">
            ℹ️
        </div>

        <div class="message-content">

            <div class="sender-name">
                Negotiation System
            </div>

            <div class="message-text">
                ${text}
            </div>

        </div>
    `;


    chat.appendChild(
        message
    );


    chat.scrollTop =
        chat.scrollHeight;

}

//   TYPING INDICATOR

function showTyping(
    name,
    side,
    avatar
) {

    const chat =
        document.getElementById(
            "chatBox"
        );


    if (!chat) {

        return;

    }


    removeTyping();


    const typing =
        document.createElement(
            "div"
        );


    typing.id =
        "typingIndicator";


    typing.className =
        `message ${side}`;


    typing.innerHTML = `

        <div class="message-avatar">

            ${
                avatar ||
                (
                    side === "left"
                        ? "👤"
                        : "🤖"
                )
            }

        </div>

        <div class="typing-content">

            <div class="sender-name">
                ${name}
            </div>

            <div class="typing-dots">

                <span></span>
                <span></span>
                <span></span>

            </div>

        </div>
    `;


    chat.appendChild(
        typing
    );


    chat.scrollTop =
        chat.scrollHeight;

}


function removeTyping() {

    const typing =
        document.getElementById(
            "typingIndicator"
        );


    if (typing) {

        typing.remove();

    }

}

//  METRICS

function updateNegotiationMetrics(
    state
) {

    const offers =
        document.getElementById(
            "metricOffers"
        );


    const concessions =
        document.getElementById(
            "metricConcessions"
        );


    const gap =
        document.getElementById(
            "metricGap"
        );


    if (offers) {

        offers.textContent =
            state.offerHistory.length;

    }


    if (concessions) {

        let total = 0;


        [
            "agent1",
            "agent2"
        ].forEach(key => {

            if (
                !state.concessions[key]
            ) {

                return;

            }


            state.concessions[key]
                .forEach(item => {

                    if (
                        item.change > 0
                    ) {

                        total++;

                    }

                });

        });


        concessions.textContent =
            total;

    }


    if (gap) {

        const a =
            state.lastOfferByAgent
                .agent1;


        const b =
            state.lastOfferByAgent
                .agent2;


        if (
            a !== null &&
            b !== null
        ) {

            gap.textContent =
                formatCurrency(
                    Math.abs(
                        Number(a) -
                        Number(b)
                    )
                );

        } else {

            gap.textContent =
                "—";

        }

    }

}


//  UI UPDATE

function updateNegotiationUI(
    state
) {

    if (!state) {

        return;

    }


    const roundDisplay =
        document.getElementById(
            "roundDisplay"
        );


    if (roundDisplay) {

        const shownRound =
            Math.min(
                state.currentRound,
                state.maxRounds
            );


        roundDisplay.textContent =
            `${shownRound}/${state.maxRounds}`;

    }


    const turnDisplay =
        document.getElementById(
            "turnDisplay"
        );


    if (turnDisplay) {

        turnDisplay.textContent =
            state.currentAgentTurn === 1
                ? getAgent1()
                : getAgent2();

    }


    const statusDisplay =
        document.getElementById(
            "statusDisplay"
        );


    if (statusDisplay) {

        statusDisplay.textContent =
            state.negotiationStatus;

    }


    const stateInfo =
        document.getElementById(
            "stateInfo"
        );


    if (stateInfo) {

        if (
            state.agreementValue !==
            null
        ) {

            stateInfo.textContent =
                `Agreement reached at ${formatCurrency(
                    state.agreementValue
                )}`;

        } else {

            stateInfo.textContent =
                `Negotiation State: ${state.negotiationStatus}`;

        }

    }


    const info =
        document.getElementById(
            "chatInfo"
        );


    if (info) {

        info.textContent =
            `${state.scenarioTitle} • ${getAgent1()} (${state.agentPersonality.agent1}) vs ${getAgent2()} (${state.agentPersonality.agent2}) • ${state.maxRounds} rounds • Autonomous`;

    }


    const agentInfo =
        document.getElementById(
            "agentInfo"
        );


    if (agentInfo) {

        const data =
            scenarios[
                state.scenario
            ];


        const p1 =
            state.agentPersonality.agent1;


        const p2 =
            state.agentPersonality.agent2;


        const d1 =
            personalityDefinitions[p1];


        const d2 =
            personalityDefinitions[p2];


        agentInfo.innerHTML = `

            <div class="chat-agent-card">

                <strong>
                    ${data.agents[0].icon}
                    ${getAgent1()}
                </strong>

                <p>
                    <b>Role:</b>
                    ${data.agents[0].role}
                </p>

                <p>
                    <b>Goal:</b>
                    ${state.agentGoals.agent1}
                </p>

                <p>
                    <b>Constraint:</b>
                    ${state.agentConstraints.agent1}
                </p>

                <p>
                    <b>Personality:</b>
                    ${d1 ? d1.icon : ""}
                    ${p1}
                </p>

            </div>


            <div class="chat-agent-card">

                <strong>
                    ${data.agents[1].icon}
                    ${getAgent2()}
                </strong>

                <p>
                    <b>Role:</b>
                    ${data.agents[1].role}
                </p>

                <p>
                    <b>Goal:</b>
                    ${state.agentGoals.agent2}
                </p>

                <p>
                    <b>Constraint:</b>
                    ${state.agentConstraints.agent2}
                </p>

                <p>
                    <b>Personality:</b>
                    ${d2 ? d2.icon : ""}
                    ${p2}
                </p>

            </div>
        `;

    }


    updateNegotiationMetrics(
        state
    );

}

// REBUILD CHAT

function rebuildChatFromHistory(
    state
) {

    const chat =
        document.getElementById(
            "chatBox"
        );


    if (!chat) {

        return;

    }


    chat.innerHTML = "";


    addSystemMessage(
        `Negotiation resumed: ${state.scenarioTitle}.`
    );


    state.negotiationHistory
        .forEach(item => {

            const name =
                item.agent === 1
                    ? getAgent1()
                    : getAgent2();


            const side =
                item.agent === 1
                    ? "left"
                    : "right";


            const avatar =
                item.agent === 1

                    ? scenarios[
                        state.scenario
                    ].agents[0].icon

                    : scenarios[
                        state.scenario
                    ].agents[1].icon;


            const decisionRecord =
                state.decisions.find(
                    d =>
                        d.agent ===
                            item.agent &&
                        d.round ===
                            item.round
                );


            addMessage(

                name,

                item.text,

                side,

                avatar,

                decisionRecord
                    ? decisionRecord.decision
                    : null,

                item.offerValue

            );

        });

}


//  AUTONOMOUS SCHEDULER

function scheduleAutonomousTurn(
    delay = 1100
) {

    if (
        autonomousTimer !== null ||
        negotiationCompleted
    ) {

        return;

    }


    const state =
        getNegotiationState();


    if (!state) {

        return;

    }


    if (
        state.negotiationStatus !==
        NEGOTIATION_STATUS.IN_PROGRESS
    ) {

        finishNegotiation();

        return;

    }


    if (
        state.currentRound >
        state.maxRounds
    ) {

        finishNegotiation();

        return;

    }


    autonomousTimer =
        setTimeout(
            () => {

                autonomousTimer =
                    null;

                nextMessage();

            },
            delay
        );

}


//  NEXT MESSAGE

function nextMessage() {

    if (
        processingMessage ||
        negotiationCompleted ||
        messageTimer !== null
    ) {

        return;

    }


    const state =
        getNegotiationState();


    if (!state) {

        return;

    }


    if (
        state.negotiationStatus !==
        NEGOTIATION_STATUS.IN_PROGRESS
    ) {

        finishNegotiation();

        return;

    }


    if (
        state.currentRound >
        state.maxRounds
    ) {

        finishNegotiation();

        return;

    }


    processingMessage =
        true;


    const agentNumber =
        Orchestrator.getCurrentAgent(
            state
        );


    const data =
        scenarios[
            state.scenario
        ];


    const agent =
        data.agents[
            agentNumber - 1
        ];


        const response =
    Orchestrator.getAgentResponse(
        state
    );


if (!response) {

    processingMessage =
        false;

    return;

}


const offerValue =
    response.offerValue;


const type =
    response.type;


const text =
    response.message;

    const side =
        agentNumber === 1
            ? "left"
            : "right";


    const button =
        document.getElementById(
            "nextBtn"
        );


    if (button) {

        button.disabled =
            true;


        button.textContent =
            `🤖 ${agent.name} is thinking...`;

    }


    showTyping(
        agent.name,
        side,
        agent.icon
    );


    const runId =
        ++autonomousRunId;


    messageTimer =
        setTimeout(
            () => {

                messageTimer =
                    null;


                if (
                    runId !==
                    autonomousRunId
                ) {

                    processingMessage =
                        false;

                    return;

                }


                removeTyping();


                const currentState =
                    getNegotiationState();


                if (!currentState) {

                    processingMessage =
                        false;

                    return;

                }


                const result =
                    recordOffer(
                        currentState,
                        agentNumber,
                        text,
                        offerValue
                    );


               

                const finalTurn =
                    agentNumber === 2 &&
                    currentState.currentRound ===
                        currentState.maxRounds;


           

                if (!finalTurn) {

                    result.decision =
                        "Counteroffer";


                    if (
                        currentState.decisions.length
                    ) {

                        currentState.decisions[
                            currentState.decisions.length - 1
                        ].decision =
                            "Counteroffer";

                    }


                    if (
                        currentState.offerHistory.length
                    ) {

                        currentState.offerHistory[
                            currentState.offerHistory.length - 1
                        ].decision =
                            "Counteroffer";

                    }


                    currentState.negotiationStatus =
                        NEGOTIATION_STATUS.IN_PROGRESS;

                }


               

                finalizeDecision(
                    currentState,
                    result,
                    agentNumber,
                    offerValue
                );


                

                if (
                    finalTurn &&
                    result.decision ===
                        "Counteroffer"
                ) {

                    currentState.negotiationStatus =
                        NEGOTIATION_STATUS.COMPLETED;

                }


                saveNegotiationState(
                    currentState
                );


                addMessage(
                    agent.name,
                    text,
                    side,
                    agent.icon,
                    result.decision,
                    offerValue
                );


                updateNegotiationUI(
                    currentState
                );


                // AGREEMENT

                if (
                    currentState.negotiationStatus ===
                    NEGOTIATION_STATUS.AGREEMENT
                ) {

                    negotiationCompleted =
                        true;


                    addSystemMessage(
                        `🎉 Agreement reached at ${formatCurrency(
                            currentState.agreementValue
                        )}.`
                    );


                    showOutcome(
                        currentState
                    );


                    disableNegotiationButton(
                        "✓ Agreement Reached"
                    );


                    processingMessage =
                        false;


                    return;

                }


                // REJECTION

                if (
                    currentState.negotiationStatus ===
                    NEGOTIATION_STATUS.REJECTED
                ) {

                    negotiationCompleted =
                        true;


                    addSystemMessage(
                        currentState.rejectionReason ||
                        "Negotiation rejected."
                    );


                    showOutcome(
                        currentState
                    );


                    disableNegotiationButton(
                        "✕ Negotiation Rejected"
                    );


                    processingMessage =
                        false;


                    return;

                }


                //   DEADLOCK

                if (
                    currentState.negotiationStatus ===
                    NEGOTIATION_STATUS.DEADLOCK
                ) {

                    negotiationCompleted =
                        true;


                    addSystemMessage(
                        currentState.deadlockReason ||
                        "Negotiation reached a deadlock."
                    );


                    showOutcome(
                        currentState
                    );


                    disableNegotiationButton(
                        "⚠ Deadlock"
                    );


                    processingMessage =
                        false;


                    return;

                }


                //  COMPLETED

                if (
                    currentState.negotiationStatus ===
                    NEGOTIATION_STATUS.COMPLETED
                ) {

                    negotiationCompleted =
                        true;


                    currentState.completedAt =
                        currentState.completedAt ||
                        new Date().toISOString();


                    saveNegotiationState(
                        currentState
                    );


                    addSystemMessage(
                        `✓ Negotiation completed after ${currentState.maxRounds} rounds. Final positions have been recorded.`
                    );


                    showOutcome(
                        currentState
                    );


                    disableNegotiationButton(
                        "✓ Negotiation Completed"
                    );


                    processingMessage =
                        false;


                    updateNegotiationUI(
                        currentState
                    );


                    return;

                }


                /*
                 * MOVE TO NEXT TURN.
                 */

                if (
                    agentNumber === 1
                ) {

                    /*
                     * Agent 1 -> Agent 2
                     */

                    Orchestrator.nextTurn(
                        currentState
                    );

                } else {

                    /*
                     * Agent 2 -> Next round -> Agent 1
                     */

                    Orchestrator.nextRound(
                        currentState
                    );

                }


                saveNegotiationState(
                    currentState
                );


                updateNegotiationUI(
                    currentState
                );


                processingMessage =
                    false;


                if (
                    currentState.currentRound >
                    currentState.maxRounds
                ) {

                    finishNegotiation();

                    return;

                }


                updateButtonText(
                    currentState
                );


                scheduleAutonomousTurn(
                    1100
                );

            },

            1000
        );

}

// START CHAT

function startChat() {

    const chat =
        document.getElementById(
            "chatBox"
        );


    if (
        !chat ||
        chatInitialized
    ) {

        return;

    }


    chatInitialized =
        true;


    const scenarioKey =
        getCurrentScenario();


    const data =
        scenarios[
            scenarioKey
        ];


    if (!data) {

        window.location.href =
            "index.html";

        return;

    }


    let state =
        getNegotiationState();


    if (!state) {

        window.location.href =
            "agents.html";

        return;

    }


    if (
        !state.agentPersonality ||
        !state.agentPersonality.agent1 ||
        !state.agentPersonality.agent2
    ) {

        window.location.href =
            "agents.html";

        return;

    }


    state.maxRounds =
        getSelectedRounds();


    if (
        state.negotiationStatus ===
        NEGOTIATION_STATUS.NOT_STARTED
    ) {

        state.negotiationStatus =
            NEGOTIATION_STATUS.IN_PROGRESS;


        state.startedAt =
            new Date().toISOString();


        saveNegotiationState(
            state
        );

    }


    updateNegotiationUI(
        state
    );


    if (
        state.negotiationHistory.length >
        0
    ) {

        rebuildChatFromHistory(
            state
        );

    } else {

        addSystemMessage(
            `Negotiation started between ${getAgent1()} and ${getAgent2()}.`
        );


        addSystemMessage(
            `🤖 Autonomous mode enabled • ${state.maxRounds} rounds • ${state.maxRounds * 2} agent turns maximum.`
        );

    }


    updateButtonText(
        state
    );


    if (
        state.negotiationStatus ===
        NEGOTIATION_STATUS.IN_PROGRESS
    ) {

        scheduleAutonomousTurn(
            700
        );

    }

}


// BUTTON STATUS

function updateButtonText(
    state
) {

    const button =
        document.getElementById(
            "nextBtn"
        );


    if (!button) {

        return;

    }


    if (
        state.negotiationStatus !==
        NEGOTIATION_STATUS.IN_PROGRESS
    ) {

        return;

    }


    const name =
        state.currentAgentTurn === 1
            ? getAgent1()
            : getAgent2();


    button.textContent =
        `🤖 Autonomous • ${name} is next`;


    button.disabled =
        true;

}

// DISABLE NEGOTIATION BUTTON

function disableNegotiationButton(
    text
) {

    const button =
        document.getElementById(
            "nextBtn"
        );


    if (button) {

        button.textContent =
            text;


        button.disabled =
            true;

    }

}


//  FINISH NEGOTIATION

function finishNegotiation() {

    if (
        negotiationCompleted
    ) {

        return;

    }


    const state =
        getNegotiationState();


    if (!state) {

        return;

    }


    negotiationCompleted =
        true;


    /*
     * If the simulation reaches the maximum
     * configured rounds without an agreement,
     * this is COMPLETED — NOT REJECTED.
     */

    if (
        state.negotiationStatus ===
        NEGOTIATION_STATUS.IN_PROGRESS
    ) {

        state.negotiationStatus =
            NEGOTIATION_STATUS.COMPLETED;

    }


    state.completedAt =
        new Date().toISOString();


    saveNegotiationState(
        state
    );


    if (
        state.negotiationStatus ===
        NEGOTIATION_STATUS.AGREEMENT
    ) {

        addSystemMessage(
            `🎉 Agreement reached at ${formatCurrency(
                state.agreementValue
            )}.`
        );


        disableNegotiationButton(
            "✓ Agreement Reached"
        );

    }


    else if (
        state.negotiationStatus ===
        NEGOTIATION_STATUS.REJECTED
    ) {

        addSystemMessage(
            state.rejectionReason ||
            "Negotiation rejected."
        );


        disableNegotiationButton(
            "✕ Negotiation Rejected"
        );

    }


    else if (
        state.negotiationStatus ===
        NEGOTIATION_STATUS.DEADLOCK
    ) {

        addSystemMessage(
            state.deadlockReason ||
            "Negotiation reached a deadlock."
        );


        disableNegotiationButton(
            "⚠ Deadlock"
        );

    }


    else {

        addSystemMessage(
            `✓ Negotiation completed after ${state.maxRounds} rounds. No agreement was reached, but both agents' final positions have been recorded.`
        );


        disableNegotiationButton(
            "✓ Negotiation Completed"
        );

    }


    showOutcome(
        state
    );


    updateNegotiationUI(
        state
    );

}


//  OUTCOME

function showOutcome(
    state
) {

    const panel =
        document.getElementById(
            "outcomePanel"
        );


    const content =
        document.getElementById(
            "outcomeContent"
        );


    if (
        !panel ||
        !content
    ) {

        return;

    }


    let outcomeTitle =
        state.negotiationStatus;


    let outcomeDescription =
        "";


    if (
        state.negotiationStatus ===
        NEGOTIATION_STATUS.AGREEMENT
    ) {

        outcomeDescription =
            `The agents reached an agreement at ${formatCurrency(
                state.agreementValue
            )}.`;


    }


    else if (
        state.negotiationStatus ===
        NEGOTIATION_STATUS.REJECTED
    ) {

        outcomeDescription =
            state.rejectionReason ||
            "The negotiation was rejected.";


    }


    else if (
        state.negotiationStatus ===
        NEGOTIATION_STATUS.DEADLOCK
    ) {

        outcomeDescription =
            state.deadlockReason ||
            "The agents could not reach common ground.";


    }


    else {

        outcomeDescription =
            "The negotiation completed all configured rounds without an agreement.";

    }


    const agent1Concessions =
        getTotalConcession(
            state,
            "agent1"
        );


    const agent2Concessions =
        getTotalConcession(
            state,
            "agent2"
        );


    content.innerHTML = `

        <div class="outcome-status">

            <span>
                Status
            </span>

            <strong>
                ${outcomeTitle}
            </strong>

        </div>


        <p class="outcome-description">
            ${outcomeDescription}
        </p>


        <div class="outcome-grid">

            <div>

                <span>
                    Rounds Used
                </span>

                <strong>
                    ${Math.min(
                        state.currentRound,
                        state.maxRounds
                    )}
                    /
                    ${state.maxRounds}
                </strong>

            </div>


            <div>

                <span>
                    Total Offers
                </span>

                <strong>
                    ${state.offerHistory.length}
                </strong>

            </div>


            <div>

                <span>
                    ${getAgent1()} Concession
                </span>

                <strong>
                    ${formatCurrency(
                        agent1Concessions
                    )}
                </strong>

            </div>


            <div>

                <span>
                    ${getAgent2()} Concession
                </span>

                <strong>
                    ${formatCurrency(
                        agent2Concessions
                    )}
                </strong>

            </div>

        </div>


        <div class="outcome-history">

            <h3>
                Decision History
            </h3>

            ${createDecisionHistory(
                state
            )}

        </div>
    `;


    panel.classList.remove(
        "hidden"
    );

}


// TOTAL CONCESSION

function getTotalConcession(
    state,
    agentKey
) {

    if (
        !state.concessions ||
        !state.concessions[agentKey]
    ) {

        return 0;

    }


    return state.concessions[
        agentKey
    ].reduce(
        (
            total,
            item
        ) => {

            return total +
                (
                    Number(
                        item.change
                    ) || 0
                );

        },
        0
    );

}


// DECISION HISTORY

function createDecisionHistory(
    state
) {

    if (
        !state.decisions ||
        !state.decisions.length
    ) {

        return `

            <p>
                No decisions recorded.
            </p>

        `;

    }


    return state.decisions
        .map(
            decision => {

                return `

                    <div class="decision-history-item">

                        <span>
                            Round ${decision.round}
                        </span>

                        <strong>
                            ${decision.agentName}
                        </strong>

                        <span>
                            ${formatCurrency(
                                decision.offerValue
                            )}
                        </span>

                        <b>
                            ${decision.decision}
                        </b>

                    </div>

                `;

            }
        )
        .join("");

}


//RESTART NEGOTIATION

function restartNegotiation() {

    if (
        autonomousTimer !== null
    ) {

        clearTimeout(
            autonomousTimer
        );


        autonomousTimer =
            null;

    }


    autonomousRunId++;


    if (
        messageTimer !== null
    ) {

        clearTimeout(
            messageTimer
        );


        messageTimer =
            null;

    }


    processingMessage =
        false;


    negotiationCompleted =
        false;


    chatInitialized =
        false;


    localStorage.removeItem(
        "negotiationState"
    );


    const state =
        createNegotiationState();


    const chat =
        document.getElementById(
            "chatBox"
        );


    if (chat) {

        chat.innerHTML =
            "";

    }


    const panel =
        document.getElementById(
            "outcomePanel"
        );


    if (panel) {

        panel.classList.add(
            "hidden"
        );

    }


    const button =
        document.getElementById(
            "nextBtn"
        );


    if (button) {

        button.disabled =
            true;


        button.textContent =
            "🤖 Autonomous Negotiation";

    }


    if (state) {

        startChat();

    }

}


// DEBUG

function showNegotiationState() {

    const state =
        getNegotiationState();


    console.log(
        "NEGOTIATION STATE",
        state
    );


    if (!state) {

        return;

    }


    console.log(
        "Current Agent:",
        Orchestrator.getCurrentAgent(
            state
        )
    );


    console.log(
        "Current Round:",
        Orchestrator.getCurrentRound(
            state
        )
    );


    console.log(
        "Current Status:",
        Orchestrator.getCurrentState(
            state
        )
    );


    console.log(
        "History:",
        Orchestrator.getHistory(
            state
        )
    );


    console.log(
        "Next Agent:",
        Orchestrator.getNextAgent(
            state
        )
    );


    console.log(
        "Concessions:",
        state.concessions
    );


    console.log(
        "Decisions:",
        state.decisions
    );

}


// CLEAR DATA

function clearNegotiationData() {

    localStorage.removeItem(
        "scenario"
    );


    localStorage.removeItem(
        "agentPersonalities"
    );


    localStorage.removeItem(
        "negotiationRounds"
    );


    localStorage.removeItem(
        "negotiationState"
    );


    window.location.href =
        "index.html";

}

//GO TO READY

function goToReady() {

    const personalities =
        getAgentPersonalities();


    if (
        !personalities.agent1 ||
        !personalities.agent2
    ) {

        alert(
            "Please select a personality for both agents before continuing."
        );


        return;

    }


    const rounds =
        getSelectedRounds();


    if (
        rounds < 3 ||
        rounds > 10
    ) {

        alert(
            "Please select between 3 and 10 negotiation rounds."
        );


        return;

    }


    const state =
        createNegotiationState();


    if (!state) {

        alert(
            "Unable to create negotiation state."
        );


        return;

    }


    window.location.href =
        "ready.html";

}


// PAGE INITIALIZATION

document.addEventListener(
    "DOMContentLoaded",
    function () {

        // Agent configuration page
         

        if (
            document.getElementById(
                "agents"
            )
        ) {

            loadAgentConfiguration();

        }


        // Negotiation page
    

        if (
            document.getElementById(
                "chatBox"
            )
        ) {

            startChat();

        }

    }
);


//   GLOBAL FUNCTIONS

window.selectScenario =
    selectScenario;


window.selectRoundPreset =
    selectRoundPreset;


window.setCustomRounds =
    setCustomRounds;


window.selectAgentPersonality =
    selectAgentPersonality;


window.goToReady =
    goToReady;


window.startChat =
    startChat;


window.nextMessage =
    nextMessage;


window.restartNegotiation =
    restartNegotiation;


window.showNegotiationState =
    showNegotiationState;


window.clearNegotiationData =
    clearNegotiationData;


//   FINAL LOAD MESSAGE

console.log(
    "✓ Negotiation System loaded successfully."
);

console.log(
    "✓ Clean decision engine active."
);

console.log(
    "✓ Maximum-round completion enabled."
);

console.log(
    "✓ Premature rejection protection enabled."
);

console.log(
    "✓ Vendor minimum-price protection enabled."
);