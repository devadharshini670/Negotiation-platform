// ======================================================
// NEGOTIATION DATA
// ======================================================

const scenarios = {

    vendor: {

        title: "Vendor Pricing",

        agents: [

            {
                name: "Buyer",
                role: "Customer",
                goal: "Get the lowest possible price",
                constraint: "Limited budget"
            },

            {
                name: "Vendor",
                role: "Seller",
                goal: "Maximize profit",
                constraint: "Minimum selling price"
            }

        ],

        messages: {

            Aggressive: [

                {
                    sender: 2,
                    text: "My initial price is ₹1,000."
                },

                {
                    sender: 1,
                    text: "₹1,000 is too high. I can offer ₹700."
                },

                {
                    sender: 2,
                    text: "I cannot go that low. I can reduce it to ₹900."
                },

                {
                    sender: 1,
                    text: "That's still above my budget. My final offer is ₹800."
                },

                {
                    sender: 2,
                    text: "I can accept ₹800. We have a deal."
                }

            ],

            Collaborative: [

                {
                    sender: 2,
                    text: "The product is priced at ₹1,000."
                },

                {
                    sender: 1,
                    text: "My budget is around ₹750. Can we find a middle ground?"
                },

                {
                    sender: 2,
                    text: "I can reduce the price to ₹900."
                },

                {
                    sender: 1,
                    text: "If you can offer ₹850, I can confirm the purchase."
                },

                {
                    sender: 2,
                    text: "₹850 works for both of us. Let's close the deal."
                }

            ],

            "Risk-Averse": [

                {
                    sender: 2,
                    text: "The standard price is ₹1,000."
                },

                {
                    sender: 1,
                    text: "I need to stay within a safe budget of ₹750."
                },

                {
                    sender: 2,
                    text: "The lowest price I can confidently offer is ₹900."
                },

                {
                    sender: 1,
                    text: "Can you reduce it slightly to ₹850?"
                },

                {
                    sender: 2,
                    text: "₹850 is acceptable. We can proceed."
                }

            ]

        }

    },


    job: {

        title: "Job Offer",

        agents: [

            {
                name: "Candidate",
                role: "Job Seeker",
                goal: "Get better compensation",
                constraint: "Experience and skills"
            },

            {
                name: "HR",
                role: "Employer",
                goal: "Control hiring cost",
                constraint: "Company budget"
            }

        ],

        messages: {

            Aggressive: [

                {
                    sender: 2,
                    text: "We can offer you a salary of ₹5,00,000 per year."
                },

                {
                    sender: 1,
                    text: "Considering my skills, I am looking for ₹7,00,000."
                },

                {
                    sender: 2,
                    text: "₹7,00,000 is above our current budget. I can offer ₹5,75,000."
                },

                {
                    sender: 1,
                    text: "I would need at least ₹6,50,000 to accept the offer."
                },

                {
                    sender: 2,
                    text: "Let's settle at ₹6,25,000 per year."
                }

            ],

            Collaborative: [

                {
                    sender: 2,
                    text: "Our initial offer is ₹5,00,000 per year."
                },

                {
                    sender: 1,
                    text: "I was expecting around ₹6,50,000 based on my skills."
                },

                {
                    sender: 2,
                    text: "We may be able to stretch the budget to ₹5,75,000."
                },

                {
                    sender: 1,
                    text: "If there are additional benefits, ₹6,00,000 would work for me."
                },

                {
                    sender: 2,
                    text: "We can offer ₹6,00,000 along with additional benefits."
                }

            ],

            "Risk-Averse": [

                {
                    sender: 2,
                    text: "Our standard offer is ₹5,00,000 per year."
                },

                {
                    sender: 1,
                    text: "I would prefer something closer to ₹6,00,000."
                },

                {
                    sender: 2,
                    text: "We can safely increase the offer to ₹5,50,000."
                },

                {
                    sender: 1,
                    text: "₹5,75,000 would be a comfortable middle ground."
                },

                {
                    sender: 2,
                    text: "We can approve ₹5,75,000 per year."
                }

            ]

        }

    },


    budget: {

        title: "Project Budget",

        agents: [

            {
                name: "Manager",
                role: "Project Lead",
                goal: "Get sufficient project funding",
                constraint: "Approval requirements"
            },

            {
                name: "Finance",
                role: "Financial Controller",
                goal: "Control project spending",
                constraint: "Budget limit"
            }

        ],

        messages: {

            Aggressive: [

                {
                    sender: 2,
                    text: "The approved budget is ₹10,00,000."
                },

                {
                    sender: 1,
                    text: "We need at least ₹15,00,000 to complete the project properly."
                },

                {
                    sender: 2,
                    text: "₹15,00,000 is too high. I can approve ₹12,00,000."
                },

                {
                    sender: 1,
                    text: "₹12,00,000 will not be enough. I need ₹14,00,000."
                },

                {
                    sender: 2,
                    text: "I can approve ₹13,50,000 as the final budget."
                }

            ],

            Collaborative: [

                {
                    sender: 2,
                    text: "The current project budget is ₹10,00,000."
                },

                {
                    sender: 1,
                    text: "Based on the project requirements, we need around ₹14,00,000."
                },

                {
                    sender: 2,
                    text: "I can increase the budget to ₹12,00,000."
                },

                {
                    sender: 1,
                    text: "If we reduce some optional features, ₹13,00,000 should work."
                },

                {
                    sender: 2,
                    text: "₹13,00,000 is reasonable. I approve the revised budget."
                }

            ],

            "Risk-Averse": [

                {
                    sender: 2,
                    text: "The approved budget is ₹10,00,000."
                },

                {
                    sender: 1,
                    text: "We estimate the project will require ₹13,00,000."
                },

                {
                    sender: 2,
                    text: "I can safely increase the budget to ₹11,50,000."
                },

                {
                    sender: 1,
                    text: "₹12,50,000 would give us enough room for unexpected costs."
                },

                {
                    sender: 2,
                    text: "₹12,00,000 is the maximum safe budget I can approve."
                }

            ]

        }

    }

};


// ======================================================
// SELECT SCENARIO
// ======================================================

function selectScenario(type) {

    localStorage.setItem("scenario", type);

    // Reset previous personality
    localStorage.removeItem("personality");

    window.location.href = "agents.html";
}


// ======================================================
// LOAD AGENTS
// ======================================================

const agentsContainer =
    document.getElementById("agents");


if (agentsContainer) {

    const scenarioKey =
        localStorage.getItem("scenario");

    const data =
        scenarios[scenarioKey];


    // Safety check
    if (!data) {

        window.location.href = "index.html";

    } else {

        // Scenario name

        const scenarioName =
            document.getElementById("scenarioName");

        if (scenarioName) {

            scenarioName.textContent =
                data.title;

        }


        // Create agent cards

        data.agents.forEach((agent, index) => {

            agentsContainer.innerHTML += `

                <div class="agent-card">

                    <div class="agent-number">
                        Agent ${index + 1}
                    </div>

                    <div class="agent-icon">
                        ${index === 0 ? "👤" : "🤖"}
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

                </div>

            `;

        });

    }

}


// ======================================================
// PERSONALITY
// ======================================================

function setPersonality(element, personality) {

    document
        .querySelectorAll(".personality-card")
        .forEach(card => {

            card.classList.remove("selected");

        });


    element.classList.add("selected");


    localStorage.setItem(
        "personality",
        personality
    );

}


// ======================================================
// GO TO NEGOTIATION
// ======================================================

function goToReady() {

    let personality =
        localStorage.getItem("personality");


    // Default personality
    if (!personality) {

        personality = "Collaborative";

        localStorage.setItem(
            "personality",
            personality
        );

    }


    window.location.href =
        "ready.html";

}


// ======================================================
// GET AGENTS
// ======================================================

function getCurrentScenario() {

    return localStorage.getItem("scenario");

}


function getAgent1() {

    const key =
        getCurrentScenario();

    return scenarios[key].agents[0].name;

}


function getAgent2() {

    const key =
        getCurrentScenario();

    return scenarios[key].agents[1].name;

}


// ======================================================
// CHAT VARIABLES
// ======================================================

let chatStep = 0;

let negotiationCompleted = false;


// ======================================================
// TYPING EFFECT
// ======================================================

function typeMessage(
    text,
    element,
    speed = 25,
    callback
) {

    let index = 0;

    element.textContent = "";


    function typing() {

        if (index < text.length) {

            element.textContent +=
                text.charAt(index);

            index++;

            setTimeout(
                typing,
                speed
            );

        } else {

            if (callback) {

                callback();

            }

        }

    }


    typing();

}


// ======================================================
// ADD MESSAGE
// ======================================================

function addMessage(
    name,
    text,
    side
) {

    const chat =
        document.getElementById("chatBox");


    if (!chat) return;


    const message =
        document.createElement("div");


    message.className =
        `message ${side}`;


    const avatar =
        document.createElement("div");


    avatar.className =
        "message-avatar";


    avatar.textContent =
        side === "left" ? "👤" : "🤖";


    const content =
        document.createElement("div");


    content.className =
        "message-content";


    const sender =
        document.createElement("div");


    sender.className =
        "sender-name";


    sender.textContent =
        name;


    const textElement =
        document.createElement("div");


    textElement.className =
        "message-text";


    content.appendChild(sender);

    content.appendChild(textElement);


    message.appendChild(avatar);

    message.appendChild(content);


    chat.appendChild(message);


    chat.scrollTop =
        chat.scrollHeight;


    typeMessage(
        text,
        textElement
    );

}


// ======================================================
// TYPING INDICATOR
// ======================================================

function showTyping(
    name,
    side
) {

    const chat =
        document.getElementById("chatBox");


    const typing =
        document.createElement("div");


    typing.id =
        "typingIndicator";


    typing.className =
        `message ${side}`;


    typing.innerHTML = `

        <div class="message-avatar">
            🤖
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


    chat.appendChild(typing);


    chat.scrollTop =
        chat.scrollHeight;

}


// ======================================================
// REMOVE TYPING
// ======================================================

function removeTyping() {

    const typing =
        document.getElementById(
            "typingIndicator"
        );


    if (typing) {

        typing.remove();

    }

}


// ======================================================
// START CHAT
// ======================================================

function startChat() {

    const chat =
        document.getElementById(
            "chatBox"
        );


    if (!chat) return;


    const key =
        getCurrentScenario();


    const personality =
        localStorage.getItem(
            "personality"
        ) || "Collaborative";


    const data =
        scenarios[key];


    if (!data) {

        window.location.href =
            "index.html";

        return;

    }


    // Update chat information

    const info =
        document.getElementById(
            "chatInfo"
        );


    if (info) {

        info.textContent =
            `${data.title} • ${personality} personality`;

    }


    // Initial message

    addMessage(
        getAgent1(),
        "Hello! Let's work together and see if we can reach a good agreement.",
        "left"
    );

}


// ======================================================
// NEXT NEGOTIATION MESSAGE
// ======================================================

function nextMessage() {

    if (negotiationCompleted) {

        return;

    }


    const key =
        getCurrentScenario();


    const personality =
        localStorage.getItem(
            "personality"
        ) || "Collaborative";


    const data =
        scenarios[key];


    const messages =
        data.messages[personality];


    // Negotiation finished

    if (chatStep >= messages.length) {

        negotiationCompleted = true;


        addMessage(
            "System",
            "Negotiation completed successfully! 🎉",
            "system"
        );


        const button =
            document.getElementById(
                "nextBtn"
            );


        if (button) {

            button.textContent =
                "Negotiation Complete";

            button.disabled =
                true;

        }


        return;

    }


    const message =
        messages[chatStep];


    const name =
        message.sender === 1
            ? getAgent1()
            : getAgent2();


    const side =
        message.sender === 1
            ? "left"
            : "right";


    showTyping(
        name,
        side
    );


    setTimeout(() => {

        removeTyping();


        addMessage(
            name,
            message.text,
            side
        );


        chatStep++;


        // Change button after final message

        if (
            chatStep ===
            messages.length
        ) {

            const button =
                document.getElementById(
                    "nextBtn"
                );


            if (button) {

                button.textContent =
                    "Finish Negotiation";

            }

        }

    }, 1000);

}


// ======================================================
// RESTART
// ======================================================

function restartNegotiation() {

    chatStep = 0;

    negotiationCompleted = false;


    const chat =
        document.getElementById(
            "chatBox"
        );


    if (chat) {

        chat.innerHTML = "";

    }


    const button =
        document.getElementById(
            "nextBtn"
        );


    if (button) {

        button.disabled = false;

        button.textContent =
            "Generate Next Offer";

    }


    startChat();

}


// ======================================================
// AUTO START CHAT PAGE
// ======================================================

if (
    document.getElementById(
        "chatBox"
    )
) {

    startChat();

}