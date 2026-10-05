"""Thirteen distinct tool plans; generated guidance never fabricates observations."""
from datetime import date
from decimal import Decimal, ROUND_FLOOR
from .registry import REGISTRY, FinanceInputs, MarketInputs
from .schemas import Result
from venture_forge.product.core.tools import calculate

LESSONS = {
    "purpose": ("Purpose and stakeholders", "Separate the user, buyer and beneficiary. Keep missing roles unknown.", "Name the user and buyer; identify one missing role."),
    "problem": ("A testable problem", "Ask what happened recently, how the person responded and what it cost.", "Write one falsifiable problem hypothesis."),
    "customer": ("Non-leading discovery", "Ask for a recent example before discussing your solution. Preserve contrary cases.", "Write three questions about a recent real experience."),
    "research": ("Claim and source", "Relevance is not support. Keep the exact excerpt, date, location and limitation.", "Find a passage and explain the precise claim it supports."),
    "market": ("One buying unit", "Use accounts or people consistently. SOM is capped by reach and delivery capacity.", "Explain your buying unit and one exclusion."),
    "competition": ("The status quo competes", "Doing nothing, spreadsheets and manual work can be substitutes.", "Describe why a customer would switch from the status quo."),
    "model": ("Value created and captured", "Identify who receives value, who pays, who approves and how delivery works.", "Compare two plausible relationship models."),
    "pricing": ("A price is a hypothesis", "Willingness to pay is different from an actual purchase. Predeclare an observed pricing test.", "Define the behaviour that would support your price."),
    "finance": ("Margin is not cash", "Gross margin = (revenue - direct cost) / revenue. Uncollected revenue cannot pay costs.", "Calculate the gross margin from the supplied financial model."),
    "experiments": ("Lock before observing", "Predeclare intervention, metric, sample, threshold and stop rule; failed instruments are inconclusive.", "Write a metric and a decision threshold before collecting results."),
    "ecosystem": ("Fit and freshness", "A programme listing is not an award. Check the official call, eligibility and expiry.", "Identify one unknown eligibility requirement and its official source."),
    "funding": ("Capital serves a milestone", "Compare financing alternatives and show negative findings alongside approved figures.", "Explain the milestone, amount and evidence needed before fundraising."),
}


def artifact_data(artifact):
    result = artifact["result"]
    return result.get("data", result)


def latest(context, capability):
    return next((a for a in reversed(context["artifacts"]) if a["capability"] == capability), None)


def execute(agent_id, parameters, context):
    spec = REGISTRY[agent_id]
    evidence = context["evidence"]
    known_sources = {r["id"]: r for r in evidence}
    artifact_ids = [a["id"] for a in context["artifacts"]]
    unknowns, blockers = [], []
    limits = ["This is a proposal for founder review. Source attribution and acceptance do not establish truth."]
    tools = list(spec.tools)
    cls = "FOUNDER_ASSUMPTION"
    summary = spec.description
    action = "Review the proposal and choose the next evidence mission."
    data = {}
    p = parameters
    if agent_id == "home":
        fields = {"purpose": context["concept"].get("idea", "unknown"), "user": context["concept"].get("customer_segment", "unknown"), "geography": context["concept"].get("geography", "unknown"), **p}
        unknowns = [f"{k} is unknown" for k, v in fields.items() if v == "unknown"]
        data = {"fields": {k: {"value": v, "status": "unknown" if v == "unknown" else "founder_stated"} for k, v in fields.items()}, "mission": {"objective": context["objective"], "completion": "Review sources or a real observation, then record a founder decision"}}
        action = "Confirm the Concept Map and choose an evidence question."
    elif agent_id == "research":
        cls = "SOURCE_REPORTED"
        entries = []
        for r in evidence:
            age = (date.today() - date.fromisoformat(r["collected_on"])).days
            entries.append({"source_id": r["id"], "title": r["title"], "excerpt": r["content"], "locator": r["locator"], "captured_on": r["collected_on"], "content_hash": r["content_hash"], "relation": r["relation"], "fresh": age <= p["freshness_days"], "limitations": r["limitations"]})
        if not entries: blockers.append("Add at least one permitted source receipt to answer this question.")
        stale = [e["source_id"] for e in entries if not e["fresh"]]
        if stale: unknowns.append("Some supplied sources exceed the requested freshness window.")
        data = {"question": context["objective"], "source_registry": entries, "claim_ledger": [{"statement": r["content"], "source_id": r["id"], "locator": r["locator"], "status": "source_reported", "relation": r["relation"]} for r in evidence], "contradictions": [r["id"] for r in evidence if r["relation"] == "contradicts"], "refresh_source_ids": stale}
        limits.append("This local research tool reviews supplied receipts; it does not fetch or verify a live web source.")
        action = "Check exact claim support and investigate conflicting or stale sources."
    elif agent_id == "market":
        cls = "CALCULATED"
        inputs = MarketInputs.model_validate(p)
        data = {"definition": {"unit": inputs.unit, "geography": context["concept"].get("geography", "unknown"), "period": inputs.period}, "drivers": inputs.model_dump(mode="json"), "sizing": calculate("market", inputs)}
        unknowns.append("Account counts and price remain assumptions unless supported by linked sources.")
        action = "Select a beachhead and test whether its buyers can be reached."
    elif agent_id == "customer":
        cls = "CUSTOMER_REPORTED"
        interviews = [r for r in evidence if r["kind"] == "interview" and r["consent"] in {"notes_only", "quote_permitted"}]
        unique = {r["participant_code"] for r in interviews}
        if not interviews: blockers.append("Capture a consented real interview before accepting a customer synthesis.")
        invited = p["invited"] or len(unique)
        if invited < len(unique): blockers.append("Invited denominator cannot be smaller than the distinct interviewed participants.")
        data = {"invited": invited, "interviewed": len(unique), "nonresponse": max(0, invited - len(unique)), "observation_ledger": [{"source_id": r["id"], "participant_code": r["participant_code"], "notes": r["content"], "consent": r["consent"], "relation": r["relation"], "limitations": r["limitations"]} for r in interviews], "contrary_receipts": [r["id"] for r in interviews if r["relation"] == "contradicts"], "interview_guide": ["Tell me about the last time this happened.", "What did you do, and what did it cost?", "What alternatives did you try?", "Who decided or paid for the current solution?"], "purchase_evidence": "unknown"}
        limits.append("Notes-only consent permits private processing, not quotation in an outgoing package.")
        action = "Compare actual behaviour and contrary cases; choose a falsifiable follow-up test."
    elif agent_id == "competitor":
        rows = []
        for item in p["alternatives"]:
            supported = item["source_id"] in known_sources
            rows.append({**item, "price_inr": item["price_inr"] if supported else None, "status": "source_reported" if supported else "founder_assumption"})
            if not supported: unknowns.append(f"{item['name']} lacks a selected source; its price stays unknown.")
        if not rows: blockers.append("Name at least one alternative or status quo and link its source where available.")
        data = {"alternative_map": rows, "status_quo_included": any(r["kind"] == "status_quo" for r in rows), "switching_test": "Ask a customer to demonstrate their current workflow and the concrete cost of switching."}
        if not data["status_quo_included"]: unknowns.append("The status quo is not yet included.")
        action = "Test a specific switching barrier before claiming differentiation."
    elif agent_id == "model":
        inherited = latest(context, "home")
        inherited_buyer = artifact_data(inherited).get("fields", {}).get("buyer", "unknown") if inherited else "unknown"
        if isinstance(inherited_buyer, dict): inherited_buyer = inherited_buyer.get("value", "unknown")
        buyer = p["buyer"] if p["buyer"] != "unknown" else inherited_buyer
        fields = {"Buyer": buyer, "User": context["concept"].get("customer_segment", "unknown"), "Value proposition": p["value_proposition"], "Customer relationships": p["relationship"], "Channels": p["channel"], "Key activities": "unknown", "Key resources": "unknown", "Key partners": "unknown", "Cost structure": "unknown", "Revenue streams": "unknown", "Pricing hypothesis": p["price_inr"] if p["price_inr"] is not None else "unknown"}
        unknowns = [f"{k} is untested or unknown" for k, v in fields.items() if v == "unknown"]
        data = {"fields": fields, "model_options": [{"relationship": x, "status": "hypothesis"} for x in ([p["relationship"], "direct" if p["relationship"] != "direct" else "subscription"] if p["relationship"] != "unknown" else ["direct", "subscription"])], "pricing_test": "Present a dated offer to the stated buyer and record actual commitments or purchases."}
        action = "Choose the buyer and relationship; test the price before treating it as observed revenue."
    elif agent_id == "finance":
        cls = "CALCULATED"
        inputs = FinanceInputs.model_validate(p)
        data = {"drivers": inputs.model_dump(mode="json"), "financials": calculate("finance", inputs), "actuals_status": "Founder-entered planning assumptions; no transaction source was verified."}
        unknowns.append("Volume, price, costs and cash collection require independent evidence or actual records.")
        action = "Review collection timing and cost drivers; test the most uncertain economic assumption."
    elif agent_id == "experiment":
        cls = "EXPERIMENT_RESULT" if context["experiments"] else "FOUNDER_ASSUMPTION"
        if context["experiments"]:
            data = {"locked_results": context["experiments"], "protocol_edit_allowed": False}
            if any(e["result"]["outcome"] == "INCONCLUSIVE" for e in context["experiments"]): unknowns.append("A locked experiment is inconclusive; do not upgrade it to validated demand.")
            action = "Record continue, revise or stop against the locked result in Experiment Lab."
        else:
            missing = [k for k, v in p.items() if v is None or v == "unknown"]
            if missing: blockers.append("Complete the draft protocol: " + ", ".join(missing))
            data = {"protocol_draft": p, "hypothesis": context["hypothesis"], "mvp_boundary": "Only build what the selected intervention requires.", "non_goals": ["Production scale", "New features without a measurement need"], "locked": False}
            action = "Use the reviewed draft in Experiment Lab, then explicitly approve and lock it before observations."
        limits.append("Accepting this proposal does not lock a protocol or count as a completed real-world test.")
    elif agent_id == "simulation":
        cls = "SIMULATED"
        finance = latest(context, "finance")
        if not finance:
            blockers.append("Select an accepted FinancePilot financial model before simulating.")
            data = {"status": "SIMULATED", "rounds": []}
        else:
            base = artifact_data(finance)
            drivers = base.get("drivers", finance["inputs"])
            inputs = FinanceInputs.model_validate(drivers)
            modified = inputs.model_copy(deep=True)
            modified.price *= Decimal(p["price_factor"])
            if modified.average_revenue_per_customer is not None:
                modified.average_revenue_per_customer *= Decimal(p["price_factor"])
            modified.volume = int((Decimal(inputs.volume) * Decimal(p["volume_factor"])).to_integral_value(rounding=ROUND_FLOOR))
            data = {"source_finance_id": finance["id"], "starting_drivers": inputs.model_dump(mode="json"), "decisions": p, "formula_version": "finance-decimal-v2", "baseline": calculate("simulation", inputs), "round": calculate("simulation", modified), "status": "SIMULATED", "reality_gap": "Price changes also scale assumed average revenue per customer. Price response, retention and volume changes are assumptions, not observed customer behaviour."}
            action = "Compare the replay, then predeclare a real test of its uncertain driver."
        limits.append("Simulation cannot satisfy customer, traction or financial-actual evidence gates.")
    elif agent_id == "academy":
        cls = "PRACTICE"
        title, lesson, exercise = LESSONS[p["topic"]]
        assessment = "pending_independent_work" if not p["independent_answer"] else "submitted_for_review"
        feedback = "A written answer alone does not demonstrate independent transfer."
        if p["topic"] == "finance" and p["independent_answer"]:
            finance = latest(context, "finance")
            if finance:
                result = artifact_data(finance)
                expected = result.get("financials", result).get("gross_margin_percent")
                try:
                    value = Decimal(p["independent_answer"].strip().rstrip("%"))
                    if value.is_finite() and expected is not None:
                        assessment = "practice_correct" if abs(value - Decimal(expected)) <= Decimal("0.01") else "practice_revise"
                        feedback = "Compare profit with revenue; cash collections are a separate measure."
                except Exception: feedback = "Submit a numeric margin percentage for this practice exercise."
        data = {"topic": p["topic"], "lesson_title": title, "lesson": lesson, "applied_exercise": exercise, "answer": p["independent_answer"], "hints_used": p["hints_used"], "assessment": assessment, "feedback": feedback, "return_to": p["return_to"], "transfer_status": "Requires a later independent task; no mastery claim."}
        action = f"Complete the exercise and return to {REGISTRY[p['return_to']].workspace}."
    elif agent_id == "ecosystem":
        cls = "SOURCE_REPORTED"
        matches = []
        for item in p["opportunities"]:
            today = date.today()
            checked = date.fromisoformat(item["last_checked"])
            expired = date.fromisoformat(item["closes_on"]) < today
            source_ok = item["source_id"] in known_sources
            fresh = 0 <= (today - checked).days <= 30
            valid_url = item["official_url"].startswith("https://")
            status = "expired" if expired else "mismatch" if item["eligibility"] == "mismatch" else "possible" if item["eligibility"] == "unknown" or not fresh or not source_ok or not valid_url else "founder_verified_fit"
            matches.append({**item, "status": status, "fresh": fresh, "source_linked": source_ok, "fit_reason": "Founder-supplied eligibility, geography and current source; official acceptance remains unknown."})
        matches.sort(key=lambda m: {"founder_verified_fit": 0, "possible": 1, "mismatch": 2, "expired": 3}[m["status"]])
        if not matches: blockers.append("Supply current official opportunity records and their selected source receipts.")
        data = {"shortlist": matches[:5], "excluded_expired": sum(m["status"] == "expired" for m in matches), "ranking": "Fresh, source-linked founder eligibility before possible, mismatch and expired; no paid ranking.", "application_checklist": ["Verify current official call", "Resolve unknown eligibility", "Review evidence and disclose only approved fields"]}
        action = "Recheck official terms and choose one application mission; no application is submitted here."
        limits.append("No live programme registry is connected; supplied records are not independently certified.")
    elif agent_id == "investor":
        cls = "DERIVED_VIEW"
        gaps = []
        for cap in ["market", "finance"]:
            if not latest(context, cap): gaps.append(f"Missing accepted {REGISTRY[cap].name} output")
        if p["milestone"] == "unknown": gaps.append("Funding milestone is unknown")
        if p["amount_inr"] is None: gaps.append("Required capital is unknown")
        if not p["ownership_reviewed"]: gaps.append("Ownership review is missing")
        if not p["ip_reviewed"]: gaps.append("IP review is missing")
        negative = [e["id"] for e in context["experiments"] if e["result"]["outcome"] == "THRESHOLD_NOT_MET"]
        data = {"funding_milestone": p["milestone"], "amount_inr": p["amount_inr"], "readiness_gaps": gaps, "reviewed_figures": [{"artifact_id": a["id"], "capability": a["capability"], "result": artifact_data(a)} for a in context["artifacts"] if a["capability"] in {"market", "finance"}], "negative_experiments": negative, "capital_alternatives": ["Operating revenue", "Verified non-dilutive programme", "Milestone-linked investment"], "outreach_enabled": False}
        unknowns.extend(gaps)
        action = "Resolve the named evidence and diligence gaps before choosing a funding route."
        limits.append("This readiness checklist does not provide an investment probability, legal advice or permission to share.")
    else:
        cls = "DERIVED_VIEW"
        data = {"accepted_artifact_ids": artifact_ids, "active_evidence_ids": list(known_sources), "readiness": {"reviewed_artifacts": len(artifact_ids), "locked_experiments": len(context["experiments"]), "scope": context["objective"]}, "evidence_confidence": {"source_count": len(evidence), "contrary_sources": sum(r["relation"] == "contradicts" for r in evidence), "independently_verified": False}, "founder_capability": {"practice_records": sum(a["capability"] == "academy" for a in context["artifacts"]), "independent_transfer": "unknown"}, "versions": [{"artifact_id": a["id"], "hash": a["hash"]} for a in context["artifacts"]]}
        action = "Review the evidence trail, keep assumptions visible and select the next real mission."
    return Result(agent_id=agent_id, specialist=spec.name, output_type=spec.output, status="NEEDS_INPUT" if blockers else "PROPOSED", summary=summary, data=data, evidence_ids=list(known_sources), artifact_ids=artifact_ids, unknowns=blockers + unknowns, limitations=limits, next_action=action, handoffs=list(spec.sends), evidence_class=cls), tools
