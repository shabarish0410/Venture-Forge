"""Founder MVP teaching content, drawn from the supplied specification (pp. 32-35)."""

MODEL_FAMILIES = [
    ("relationship", "b2b", "Business to business", "An organization buys; users and approvers can differ.", "Sales cycle, annual contract value, retention", "Identify the budget owner and test a paid pilot."),
    ("relationship", "b2c", "Business to consumer", "An individual buys for personal use.", "Conversion, acquisition cost, repeat purchase", "Test an offer at a real price with a narrow audience."),
    ("relationship", "c2c", "Consumer to consumer", "Individuals exchange value with each other.", "Match rate, time to match, disputes", "Test one category with verified participants."),
    ("relationship", "b2b2c", "Business to business to consumer", "A partner buys, embeds or distributes access for end users.", "Partner adoption, activation, renewal", "Test partner commitment and end-user activation separately."),
    ("relationship", "d2c", "Direct to consumer", "A producer sells directly to consumers.", "Order value, returns, fulfillment margin", "Test paid orders including acquisition and delivery costs."),
    ("operating", "marketplace", "Marketplace", "Coordinate supply, demand, trust and transactions.", "Liquidity, GMV, take rate, disputes", "Manually fulfill one dense segment before expanding."),
    ("operating", "api_platform", "API / platform", "Others build on a repeatable programmable capability.", "Active integrations, time to value, reliability", "Test a paid design-partner integration."),
    ("operating", "franchise", "Franchise", "Operators license a repeatable brand and operating system.", "Unit payback, closures, quality", "Prove company-operated unit economics first."),
    ("operating", "wholesale", "Wholesale", "Sell in volume to resellers or institutions.", "Order value, receivable days, sell-through", "Test small orders and payment terms."),
    ("operating", "retail", "Retail", "Sell through physical or digital storefronts.", "Conversion, basket size, inventory turns", "Test a narrow catalogue or pop-up."),
    ("operating", "manufacturing", "Manufacturing", "Transform inputs and control production quality and capacity.", "Yield, utilization, defects, lead time", "Test prototypes and paid pilot orders."),
    ("delivery", "saas", "SaaS", "Deliver ongoing access to a software workflow.", "Activation, churn, recurring revenue", "Test repeated use and paid renewal."),
    ("delivery", "licensing", "Licensing", "Grant defined rights to use intellectual property.", "License value, renewal, support cost", "Test a standard scope with one customer."),
    ("delivery", "data_insights", "Data / insights", "Deliver lawful, current, decision-relevant information.", "Accuracy, freshness, decision impact", "Test a paid insight and its effect on a decision."),
    ("delivery", "ai_service", "AI as a Service", "Deliver a bounded model-assisted capability.", "Task success, correction, latency, cost", "Compare a real task with a human baseline."),
    ("pricing", "subscription", "Subscription", "Charge repeatedly for continuing value.", "Renewal, churn, recurring margin", "Test renewal after actual use."),
    ("pricing", "freemium", "Freemium", "Offer a free tier with an explicit paid conversion trigger.", "Activation, paid conversion, free-user cost", "Test the paywall with activated users."),
    ("pricing", "usage_based", "Usage based", "Charge for measurable consumption.", "Revenue and margin per unit, bill predictability", "Test metering and customer comprehension."),
    ("pricing", "per_user", "Per user", "Charge for authorized or active seats.", "Paid seats, utilization, expansion", "Test who needs access and a second paid seat."),
    ("pricing", "commission", "Commission / take rate", "Keep a share of transacted value.", "GMV, net revenue, leakage, disputes", "Test whether trust and workflow justify the fee."),
    ("pricing", "transaction_fee", "Transaction fee", "Charge for a completed transaction or event.", "Frequency, fee, contribution, refunds", "Test a real transaction with total cost visible."),
    ("pricing", "lead_generation", "Lead generation", "Charge for an agreed qualified prospect.", "Lead acceptance, conversion, rejection", "Agree qualification rules and track outcomes."),
    ("pricing", "advertising", "Advertising", "Advertisers pay for access to an audience.", "Reach, engagement, revenue, user churn", "Test a disclosed sponsor and user response."),
    ("pricing", "outcome_based", "Outcome based", "Charge against a verified result and agreed baseline.", "Attribution, realization time, disputes", "Test measurement and settlement for one outcome."),
    ("combination", "hybrid", "Hybrid", "Combine explicit streams while keeping each stream's economics visible.", "Revenue mix, margin by stream, complexity", "Test each stream before testing the bundle."),
]

PATTERNS = {
    "concierge": ("Deliver a service manually to learn the customer's workflow.", "Value and willingness to engage", "Automation or scale"),
    "wizard_of_oz": ("Use a manual backend behind a clearly scoped trial experience.", "Interaction and workflow", "Technical feasibility at scale"),
    "landing_page": ("Present a dated offer with an explicit response event.", "Offer response in the reached audience", "Payment, retention or delivery"),
    "prototype": ("Let participants attempt one job using a prototype.", "Usability and task comprehension", "Demand, reliability or willingness to pay"),
    "smoke_test": ("Measure a real offer response with availability clearly disclosed.", "Initial behavioral interest", "Retention or fulfilled value"),
    "pre_order": ("Offer clear delivery/refund terms before taking a commitment.", "A specific purchase commitment", "Successful delivery or repeat purchase"),
    "pilot": ("Operate a bounded paid or unpaid trial with stated criteria.", "Value within the pilot's conditions", "Repeatable growth beyond the sample"),
    "no_code": ("Assemble only the workflow needed for measurement.", "Workflow use", "Production security or scale"),
    "manual_service": ("Run the job directly with a small participant group.", "Service value and operational steps", "Software economics"),
    "single_feature": ("Build one feature tied to one observable outcome.", "A narrow behavior", "A complete product-market fit claim"),
}

PAGES = {"home": "9-12", "research": "13-16", "market": "17-20", "customer": "21-24", "competitor": "25-28", "model": "29-36", "finance": "37-40", "experiment": "41-44", "simulation": "45-48", "academy": "49-53", "ecosystem": "54-57", "investor": "58-61", "passport": "62-65"}

MODULES = {
    "home": ["Concept map", "Stakeholders", "Unknowns", "Next mission"],
    "research": ["Research brief", "Sources", "Claims", "Cited memo"],
    "market": ["Market definition", "Value chain", "Segments", "Sizing drivers"],
    "customer": ["Discovery plan", "Interview guide", "Consent and notes", "Themes and decision"],
    "competitor": ["Alternative universe", "Source profiles", "Comparable pricing", "Differentiation"],
    "model": ["Stakeholders", "Model families", "Nine-block canvas", "Options and pricing test"],
    "finance": ["Assumptions", "Monthly cash", "Break-even", "Three scenarios"],
    "experiment": ["Risk ranking", "MVP patterns", "Scope", "Locked protocol and decision"],
    "simulation": ["Monthly scenario", "Decisions", "Replay", "Debrief"],
    "academy": ["Diagnostic", "Lesson", "Exercise and rubric", "Skill evidence"],
    "ecosystem": ["Supplied registry", "Geography", "Eligibility", "Saved opportunities"],
    "investor": ["Funding need", "Readiness", "One-pager", "Q&A and checklist"],
    "passport": ["Evidence and versions", "Decisions", "Three signals", "Owner export"],
}


def library(agent):
    return {
        "source_pages": PAGES[agent], "release": "founder_mvp", "modules": MODULES[agent],
        "model_families": [dict(zip(["layer", "id", "name", "definition", "metrics", "first_test"], row)) for row in MODEL_FAMILIES] if agent == "model" else [],
        "patterns": [{"id": key, "description": value[0], "can_test": value[1], "cannot_prove": value[2]} for key, value in PATTERNS.items()] if agent == "experiment" else [],
    }
