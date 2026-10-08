"""Small usable MVPs for the seven supporting applications; no collaboration/feed APIs."""
from datetime import date
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, localcontext
from urllib.parse import urlsplit
from .workspace_library import PATTERNS
from .workspace_reports import section, source_rows, tasks, provenance
from venture_forge.product.core.tools import money


def monthly_schedule(p, w, factor=Decimal(1)):
    with localcontext() as arithmetic:
        arithmetic.prec = 60
        return _monthly_schedule(p, w, factor)


def _monthly_schedule(p, w, factor):
    price, starting_volume = Decimal(p["price"]), int(p["volume"])
    if p["period"] != "month" or starting_volume == 0:
        return []
    unit_cost = Decimal(p["direct_cost"]) / starting_volume
    rate = Decimal(w["collection_percent"]) / 100 if w["collection_percent"] is not None else min(Decimal(1), Decimal(p["collected_cash"]) / (price * starting_volume)) if price else Decimal(0)
    cash, rows, revenues = Decimal(p["cash_balance"]), [], []
    growth = 1 + Decimal(w["monthly_volume_growth_percent"]) / 100
    for month in range(w["months"]):
        volume = int((Decimal(starting_volume) * factor * (growth ** month if month else 1)).to_integral_value(rounding=ROUND_FLOOR))
        revenue = price * volume
        revenues.append(revenue)
        receipt_month = month - w["collection_delay_months"]
        receipts = revenues[receipt_month] * rate if receipt_month >= 0 else Decimal(0)
        direct = unit_cost * volume
        expenses = direct + Decimal(p["fixed_cost"])
        ending = cash + receipts - expenses
        rows.append({"month": month + 1, "units": volume, "revenue_inr": money(revenue), "direct_cost_inr": money(direct), "fixed_cost_inr": money(Decimal(p["fixed_cost"])), "gross_profit_inr": money(revenue - direct), "opening_cash_inr": money(cash), "receipts_inr": money(receipts), "ending_cash_inr": money(ending), "negative_cash": ending < 0, "classification": "forecast_assumption"})
        cash = ending
    return rows


def simulation_rounds(drivers, parameters, workspace):
    if drivers["period"] != "month": return []
    base_volume = int(drivers["volume"])
    price = Decimal(drivers["price"])
    direct_cost = Decimal(drivers["direct_cost"])
    unit_cost = direct_cost / base_volume if base_volume else Decimal(0)
    receipts_rate = min(Decimal(1), Decimal(drivers["collected_cash"]) / (price * base_volume)) if price * base_volume else Decimal(0)
    cash, rows = Decimal(drivers["cash_balance"]), []
    rounds = workspace["rounds"] or [{"price_factor": parameters["price_factor"], "demand_factor": parameters["volume_factor"], "channel_spend_inr": "0", "channel_customers": 0, "event": "none", "rationale": "Replay the supplied price and volume assumptions.", "debrief": ""}]
    for index, decision in enumerate(rounds):
        demand = int((Decimal(base_volume) * Decimal(decision["demand_factor"])).to_integral_value(rounding=ROUND_FLOOR)) + decision["channel_customers"]
        if decision["event"] == "demand_down_20": demand = int(Decimal(demand) * Decimal("0.8"))
        volume = min(demand, workspace["capacity"]) if workspace["capacity"] is not None else demand
        effective_price = price * Decimal(decision["price_factor"])
        cost = unit_cost * volume if base_volume else direct_cost
        if decision["event"] == "direct_cost_up_20": cost *= Decimal("1.2")
        revenue = effective_price * volume
        receipts = revenue * receipts_rate
        outflow = cost + Decimal(drivers["fixed_cost"]) + Decimal(decision["channel_spend_inr"])
        ending = cash + receipts - outflow
        rows.append({"round": index + 1, "price_inr": money(effective_price), "demand": demand, "served": volume, "unserved": demand - volume, "revenue_inr": money(revenue), "gross_profit_inr": money(revenue - cost), "opening_cash_inr": money(cash), "receipts_inr": money(receipts), "cash_outflow_inr": money(outflow), "ending_cash_inr": money(ending), "event": decision["event"], "channel_spend_inr": decision["channel_spend_inr"], "rationale": decision["rationale"], "debrief": decision["debrief"], "classification": "SIMULATED"})
        cash = ending
    return rows


def remaining_report(agent, p, w, context, data):
    with localcontext() as arithmetic:
        arithmetic.prec = 60
        return _remaining_report(agent, p, w, context, data)


def _remaining_report(agent, p, w, context, data):
    sources = {r["id"]: r for r in context["evidence"]}
    artifacts = context["artifacts"]
    sections, gaps = [], []
    action = "Review the proposal and choose the next evidence task."
    if agent == "finance":
        schedule = monthly_schedule(p, w)
        if not schedule: gaps.append("Monthly schedules require a month period and a positive base volume; no conversion is assumed.")
        costs = Decimal(p["direct_cost"]) / p["volume"] if p["volume"] else None
        contribution = Decimal(p["price"]) - costs if costs is not None else None
        breakeven = int((Decimal(p["fixed_cost"]) / contribution).to_integral_value(rounding=ROUND_CEILING)) if contribution is not None and contribution > 0 else None
        cases = []
        for name, factor in [("low", Decimal(w["low_volume_factor"])), ("base", Decimal(1)), ("high", Decimal(w["high_volume_factor"]))]:
            rows = monthly_schedule(p, w, factor)
            if rows:
                cases.append({"scenario": name, "volume_factor": str(factor), "total_revenue_inr": money(sum(Decimal(r["revenue_inr"]) for r in rows)), "ending_cash_inr": rows[-1]["ending_cash_inr"], "first_negative_month": next((r["month"] for r in rows if r["negative_cash"]), None), "classification": "forecast_assumption"})
        refs = {r["driver"]: r for r in w["assumption_sources"]}
        ledger = [{"driver": key, "value": str(value) if value is not None else None, "evidence_status": provenance(refs.get(key, {}), sources), "source_id": refs.get(key, {}).get("source_id"), "owner": refs.get(key, {}).get("owner", "Founder")} for key, value in p.items()]
        sections = [section("assumptions", "Financial assumptions", ledger), section("schedule", "Monthly revenue, cost and cash", schedule, "Forecast: revenue = price × units; direct cost scales with units; fixed cost stays constant. Receipts follow the stated collection rate and delay; opening receivables are not modeled."), section("break_even", "Break-even", [{"contribution_per_unit_inr": money(contribution) if contribution is not None else None, "break_even_units": breakeven, "formula": "ceil(fixed cost / (price - direct cost per unit))", "status": "planning_assumption"}]), section("scenarios", "Low, base and high", cases, "Volume responses are assumptions. They do not establish demand or financial actuals.")]
        action = "Export and review the monthly schedule; test the most uncertain volume or collection assumption."
    elif agent == "experiment":
        ranked = sorted(w["risks"], key=lambda r: -(r["impact"] * r["uncertainty"]))
        pattern = PATTERNS[w["pattern"]]
        sections = [section("risks", "Assumption ranking", [{**r, "priority": r["impact"] * r["uncertainty"]} for r in ranked], "Priority = founder-rated impact × uncertainty; it does not measure validation."), section("pattern", "Chosen MVP pattern", [{"pattern": w["pattern"], "description": pattern[0], "can_test": pattern[1], "cannot_prove": pattern[2]}]), section("scope", "MVP boundary", [{"customer": w["target_customer"], "promise": w["core_promise"], "included": w["included_scope"], "non_goals": w["non_goals"]}]), section("tasks", "Build and launch tasks", tasks(w["tasks"], sources)), section("launch", "Before locking the real test", [{"check": item, "status": "founder_check_required"} for item in ["Participant consent and safe procedure", "Primary metric measures the assumed behavior", "Instrument checked before collecting results", "Sample, threshold and stop rule declared", "Scope and non-goals accepted"]])]
        action = "Use Experiment Lab to approve and lock the protocol before collecting real observations."
    elif agent == "simulation":
        drivers = data.get("starting_drivers")
        rounds = simulation_rounds(drivers, p, w) if drivers else []
        if drivers and drivers["period"] != "month": gaps.append("The V0 simulation supports monthly service economics only; select a monthly Finance Lab model.")
        sections = [section("scenario", "Simulation assumptions", [{"family": "recurring per-unit service", "learning_objective": w["learning_objective"], "branch": w["replay_label"], "formula_version": "service-monthly-v1", "seed": "none: fully deterministic", "classification": "SIMULATED"}]), section("rounds", "Locked decision rounds", rounds, "Every round starts from the previous ending cash. Demand and channel gains are declared assumptions; price does not secretly change conversion. Accepted runs preserve decisions and results. Create another run with the same finance input for a counterfactual replay."), section("debrief", "Reality gap and next test", [{"reality_gap": "No calibrated demand response, staffing or market forecast is modeled.", "next_test": "Test the assumed demand or channel response with a real experiment.", "evidence_type": "SIMULATED; excluded from validation gates"}])]
        action = "Explain the cash effect, then rerun alternative decisions from the same accepted finance version."
    elif agent == "academy":
        rubric = [{"criterion": "Identify the decision", "requirement": "Name the real venture task and what must be decided."}, {"criterion": "Apply the concept", "requirement": "Use the relevant definition or formula with stated inputs."}, {"criterion": "Explain uncertainty", "requirement": "Distinguish evidence, assumptions and remaining unknowns."}, {"criterion": "Choose a test", "requirement": "Propose a next action that could change the decision."}]
        events = []
        for artifact in artifacts:
            if artifact["capability"] != "academy": continue
            prior = artifact["result"].get("data", artifact["result"])
            events.append({"topic": prior.get("topic", "unknown"), "assessment": prior.get("assessment", "submitted_for_review"), "artifact_id": artifact["id"], "assessor": "rule check / founder review", "evidence_level": "practice", "confidence": "limited to this task"})
        sections = [section("diagnostic", "Starting point", [{"task": w["current_task"], "founder_understanding": w["diagnostic"], "evidence_level": "self_report"}]), section("lesson", "Contextual micro-lesson", [{"title": data["lesson_title"], "concept": data["lesson"], "venture_example": "Apply this to " + context["concept"].get("customer_segment", "your customer") + ": " + context["hypothesis"], "non_example": "Completing this lesson alone does not validate the venture or demonstrate mastery."}]), section("exercise", "Independent application", [{"exercise": data["applied_exercise"], "answer": p["independent_answer"], "rationale": w["rationale"], "hints_used": p["hints_used"], "assessment": data["assessment"], "feedback": data["feedback"]}]), section("rubric", "Transparent review rubric", rubric), section("skills", "Skill evidence", events + [{"topic": p["topic"], "assessment": data["assessment"], "evidence_level": "assisted_practice" if p["hints_used"] else "practice", "confidence": "limited to this task", "assessor": "deterministic check where applicable; founder review otherwise"}]), section("next", "Return to venture work", [{"workspace": p["return_to"], "application": w["next_application"], "transfer_status": "not assessed"}])]
        if p["independent_answer"] and not w["rationale"]: gaps.append("Add your own reasoning before treating the response as applied skill evidence.")
        action = "Use the rubric to review your reasoning, then apply it in the originating workspace."
    elif agent == "ecosystem":
        rules = defaultdict(list)
        for rule in w["eligibility_rules"]: rules[rule["opportunity"]].append(rule)
        included, excluded = [], []
        for item in p["opportunities"]:
            src = sources.get(item["source_id"])
            try:
                official = urlsplit(item["official_url"])
                source_url = urlsplit(src["locator"].split()[0]) if src else None
                verified = bool(source_url and src["consent"] == "public_source" and official.scheme == "https" and not official.username and official.hostname == source_url.hostname)
            except ValueError: verified = False
            age = (date.today() - date.fromisoformat(item["last_checked"])).days
            expired = date.fromisoformat(item["closes_on"]) < date.today()
            checks = rules[item["name"]]
            failed = item["eligibility"] == "mismatch" or any(r["result"] == "fail" for r in checks)
            passed = bool(checks) and all(r["result"] == "pass" and r["evidence"] and provenance(r, sources) == "quoted_source" for r in checks)
            geo = item["geography"].casefold()
            national = geo in {"india", "all india", "national"}
            matches_geo = (not w["national_only"] or national) and (not w["state_or_ut"] or national or w["state_or_ut"].casefold() in geo)
            reason = "expired" if expired else "stale_or_future_verification" if not 0 <= age <= 30 else "eligibility_mismatch" if failed else "geography_mismatch" if not matches_geo else ""
            row = {**item, "eligibility_result": "pass_on_recorded_rules" if passed and verified else "unknown", "official_source_linked": verified, "saved": item["name"] in w["saved_opportunities"], "fit_reason": "Matches selected geography; verify support need and all official criteria.", "status": reason or "current_candidate"}
            (excluded if reason else included).append(row)
        included.sort(key=lambda r: (r["eligibility_result"] != "pass_on_recorded_rules", r["closes_on"], r["name"]))
        # The canonical shortlist must use the same exclusions as the workspace view.
        data["shortlist"] = included[:5]
        data["excluded_expired"] = sum(r["status"] == "expired" for r in excluded)
        data["ranking"] = "Current matching geography, documented eligibility, then closing date; no commercial factor."
        sections = [section("needs", "Support need", [{"need": w["need"], "state_or_ut": w["state_or_ut"], "national_only": w["national_only"]}]), section("shortlist", "Current opportunity shortlist", included[:5], "Owner-supplied registry. Linked official sources are not independent certification; unknown eligibility remains unknown."), section("rules", "Eligibility checklist", source_rows(w["eligibility_rules"], sources)), section("excluded", "Excluded registry records", excluded)]
        if not included: gaps.append("No current opportunity matches these filters. Add or recheck an official record.")
        action = "Review the missing eligibility evidence and use the official link for the selected opportunity."
    elif agent == "investor":
        valid, blocked = [], []
        artifact_by_id = {a["id"]: a for a in artifacts}
        for claim in w["pitch_claims"]:
            evidence_status = provenance(claim, sources)
            artifact = artifact_by_id.get(claim["artifact_id"])
            allowed = claim["classification"] == "assumption" or (claim["classification"] == "source_reported" and evidence_status == "quoted_source")
            # A source ID or model ID alone does not validate arbitrary prose/numbers.
            if claim["classification"] == "projection":
                allowed = False
            row = {**claim, "review_status": "labelled_assumption" if claim["classification"] == "assumption" else "exact_quote_requires_wording_review" if allowed else "blocked_unsupported", "artifact_reference": artifact["id"] if artifact else None}
            (valid if allowed else blocked).append(row)
        sections = [section("strategy", "Funding need and alternatives", [{"milestone": p["milestone"], "amount_inr": p["amount_inr"], "why_now": w["why_now"], "use_of_funds": w["use_of_funds"], "alternative_plan": w["alternative_plan"], "capital_choices": ", ".join(data["capital_alternatives"])}]), section("one_pager", "Evidence-backed one-pager draft", valid, "All claims require founder review. Projections are included only as the original calculated figures below, never arbitrary claimed numbers."), section("blocked", "Claims needing repair", blocked), section("diligence", "Readiness and data-room checklist", [{"item": item, "status": "missing"} for item in data["readiness_gaps"]] + [{"item": "Permission and source index for every outgoing document", "status": "owner_review_required"}]), section("questions", "Investor Q&A practice", [{"question": q, "status": "practice_only"} for q in ["Why is funding needed now rather than revenue or a grant?", "Which customer behavior is observed and which is assumed?", "What would make the current model fail?", "Which milestone does this amount buy?"]]), section("rehearsal", "Your rehearsal answers", [{**r, "status": "submitted_for_founder_review"} for r in w["rehearsal"]])]
        figures = []
        for artifact in artifacts:
            result = artifact["result"].get("data", artifact["result"])
            values = result.get("financials", {}) if artifact["capability"] == "finance" else result.get("sizing", {}) if artifact["capability"] == "market" else {}
            for field, value in values.items():
                if isinstance(value, (str, int)) or value is None:
                    figures.append({"artifact_id": artifact["id"], "version_hash": artifact["hash"], "application": artifact["capability"], "field": field, "value": value, "classification": "reviewed_planning_assumption_not_actual"})
        sections.insert(2, section("figures", "Exact reviewed planning figures", figures, "Copied from the selected accepted market and finance versions. These calculations are not traction, actual revenue or a funding forecast."))
        sections.append(section("negative_findings", "Negative experiment findings", [{"experiment_id": ident, "finding": "Predeclared threshold not met"} for ident in data["negative_experiments"]]))
        gaps += ["Repair or remove unsupported pitch claims before using the one-pager."] if blocked else []
        action = "Resolve readiness gaps and review the one-pager. No outreach or external collaboration is enabled."
    else:
        caps = {a["capability"] for a in artifacts}
        interviews = [r for r in sources.values() if r["kind"] == "interview" and r["consent"] in {"notes_only", "quote_permitted"}]
        requirements = {"customer_discovery": [("Concept framed", "home" in caps), ("Hypothesis recorded", bool(context["hypothesis"]))], "mvp_test": [("Customer observations available", bool(interviews)), ("Model reviewed", "model" in caps), ("Experiment plan reviewed", "experiment" in caps)], "financial_planning": [("Model drivers reviewed", "model" in caps), ("Market definition reviewed", "market" in caps)], "funding_preparation": [("Finance reviewed", "finance" in caps), ("Market reviewed", "market" in caps), ("Real completed experiment", any(e["result"]["outcome"] in {"THRESHOLD_MET", "THRESHOLD_NOT_MET"} for e in context["experiments"]))]}
        checks = [{"requirement": title, "status": "present_for_review" if present else "missing", "scope": "Selected records only"} for title, present in requirements[w["next_action"]]]
        gaps = [r["requirement"] for r in checks if r["status"] == "missing"]
        sections = [section("readiness", "Readiness for " + w["next_action"].replace("_", " "), checks, "Presence checks support a founder decision; they do not validate quality or predict success. Simulation and practice never satisfy real evidence requirements."), section("confidence", "Evidence confidence", [{"active_sources": len(sources), "distinct_content_hashes": len({r["content_hash"] for r in sources.values()}), "contradictions": sum(r["relation"] == "contradicts" for r in sources.values()), "independence": "not established by source count", "directness": "Review source method and sampled population"}]), section("capability", "Founder capability", [{"accepted_practice_artifacts": sum(a["capability"] == "academy" for a in artifacts), "independent_transfer": "unknown", "human_verification": "not recorded"}]), section("lineage", "Selected approved versions", [{"artifact_id": a["id"], "application": a["capability"], "hash": a["hash"]} for a in artifacts])]
        action = "Resolve the named gaps and export only the reviewed records required for your purpose."
    return sections, gaps, action
