"""Evidence-aware MVP workflows. Calculations run in Python; no external actions."""
from collections import defaultdict
from hashlib import sha256
from datetime import date
from decimal import Decimal
from .workspace_contracts import WorkspaceReport
from venture_forge.product.core.tools import money


def section(key, title, rows, description=""):
    return {"key": key, "title": title, "description": description, "rows": rows}


def check_references(parameters, context):
    """A nested form cannot introduce records outside the explicitly selected context."""
    source_ids = {r["id"] for r in context["evidence"]}
    artifact_ids = {a["id"] for a in context["artifacts"]}
    def visit(value):
        if isinstance(value, dict):
            if value.get("source_id") and value["source_id"] not in source_ids:
                raise ValueError("SOURCE_NOT_SCOPED")
            if value.get("artifact_id") and value["artifact_id"] not in artifact_ids:
                raise ValueError("ARTIFACT_NOT_SCOPED")
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(parameters)


def provenance(item, sources):
    source = sources.get(item.get("source_id"))
    if not source: return "assumption"
    quote = item.get("quote", "")
    if quote and (quote in source["content"] or sha256(quote.encode()).hexdigest() in source.get("selected_quote_hashes", [])): return "quoted_source"
    return "quote_mismatch" if quote else "source_linked_review_needed"


def source_rows(items, sources):
    return [{**{k: v for k, v in item.items() if not isinstance(v, (dict, list))}, "evidence_status": provenance(item, sources)} for item in items]


def tasks(items, sources):
    return [{**item, "status": "needs_completion_evidence" if item["status"] == "completed" and item.get("source_id") not in sources else "needs_reason" if item["status"] == "abandoned" and not item["resolution"] else item["status"]} for item in items]


def build_report(agent, p, w, context, data):
    sources = {r["id"]: r for r in context["evidence"]}
    artifacts = context["artifacts"]
    sections, gaps = [], []
    action = "Review the evidence, record your decision and choose one next task."
    if agent == "home":
        fields = [{"field": k, **v} for k, v in data["fields"].items()]
        fields += [{"field": k, "value": w[k], "status": "founder_stated" if w[k] else "unknown"} for k in ["entry_path", "founder_goal"]]
        fields += [{"field": k, "value": w[k], "status": "unknown" if w[k] == "unknown" else "founder_stated"} for k in ["payer", "approver"]]
        unknowns = sorted(w["unknowns"], key=lambda x: (bool(x["deferred_reason"]), -x["impact"] * x["uncertainty"]))
        if not unknowns:
            unknowns = [{"question": "What evidence would support: " + context["hypothesis"], "impact": 3, "uncertainty": 3, "owner": "Founder", "due_on": None, "deferred_reason": ""}]
        ranked = [{**u, "priority": u["impact"] * u["uncertainty"]} for u in unknowns]
        next_unknown = next((u for u in ranked if not u["deferred_reason"]), None)
        mission = {"objective": context["objective"], "reason": w["mission_reason"] or (next_unknown["question"] if next_unknown else "All listed unknowns are deferred; choose a new question."), "completion": w["mission_completion"] or "Add an original source or consented observation, then record what it changes.", "available_hours": w["available_hours"], "budget_inr": w["budget_inr"], "suggested_workspace": "research" if not sources else "customer"}
        sections = [section("concept", "Concept and stakeholders", fields), section("unknowns", "Prioritized unknowns", ranked, "Priority = founder-rated impact × uncertainty (1-5 each). This is task priority, not a success score."), section("mission", "One next mission", [mission]), section("tasks", "Mission tasks", tasks(w["tasks"], sources))]
        action = mission["completion"]
    elif agent == "research":
        reviews = {r["source_id"]: r for r in w["source_reviews"]}
        registry = []
        seen = set()
        for src in sources.values():
            review = reviews.get(src["id"], {})
            ttl = min(p["freshness_days"], 7 if review.get("volatility") == "deadline" else 30 if review.get("volatility") in {"price", "policy"} else p["freshness_days"])
            age = (date.today() - date.fromisoformat(src["collected_on"])).days
            duplicate = src["content_hash"] in seen
            seen.add(src["content_hash"])
            registry.append({"source_id": src["id"], "title": src["title"], "locator": src["locator"], "publisher": review.get("publisher", "unknown"), "source_type": review.get("source_type", "unknown"), "method": review.get("method", "unknown"), "geography": review.get("geography", "unknown"), "captured_on": src["collected_on"], "freshness": "current_capture" if 0 <= age <= ttl else "recheck", "duplicate_content": duplicate})
        claims = source_rows(w["claims"], sources)
        for claim in claims:
            if claim["claim_type"] == "source_reported" and claim["evidence_status"] != "quoted_source":
                gaps.append("A source-reported claim needs an exact passage from a selected source: " + claim["statement"][:100])
        questions = w["subquestions"] or [context["objective"]]
        geography = w["geography"] or context["concept"].get("geography", "")
        queries = [{"question": q, "query": f"{q} {geography} {w['period']}".strip(), "source_target": "Original publication or official authority", "status": "planned_query"} for q in questions]
        sections = [section("brief", "Research brief", [{"decision": w["decision"] or context["objective"], "scope": w["scope"], "exclusions": w["exclusions"], "geography": geography, "period": w["period"]}]), section("queries", "Source plan", queries), section("sources", "Source quality and freshness", registry, "Source quality labels are founder reviews. Capture date does not establish publication recency."), section("claims", "Claim ledger", claims), section("memo", "Evidence memo", [{"question": context["objective"], "registered_sources": len(sources), "distinct_contents": len(seen), "contrary_sources": sum(r["relation"] == "contradicts" for r in sources.values()), "conclusion": "Review the claim ledger and contrary evidence before adopting an answer."}])]
        if not claims: gaps.append("Write atomic claims and link exact supporting or contrary passages before using this memo for a decision.")
        action = "Resolve the claim gaps and approve only the wording supported by the source passages."
    elif agent == "market":
        segments = source_rows(w["segments"], sources)
        selected = next((r for r in segments if r["name"] == w["selected_segment"]), None)
        if w["selected_segment"] and not selected: gaps.append("The selected beachhead must name a recorded segment.")
        refs = {d["driver"]: d for d in w["driver_sources"]}
        drivers = [{"driver": key, "value": str(p[key]), "unit": "INR per buying unit per " + p["period"] if key == "price" else p["unit"], "evidence_status": provenance(refs.get(key, {}), sources), "source_id": refs.get(key, {}).get("source_id"), "definition": refs.get(key, {}).get("definition", "Founder-entered planning driver")} for key in ["total_accounts", "serviceable_accounts", "reachable_accounts", "capacity", "price"]]
        sections = [section("definition", "Counted market", [{"category": w["category"], "buyer": w["buyer"], "unit": p["unit"], "geography": context["concept"].get("geography", "unknown"), "period": p["period"], "inclusions": w["inclusions"], "exclusions": w["exclusions"]}]), section("value_chain", "Value-chain sketch", w["value_chain"]), section("segments", "Candidate segments", segments), section("beachhead", "Beachhead decision", [{"selected_segment": w["selected_segment"] or "unknown", "reason": w["selection_reason"], "status": "founder_hypothesis"}]), section("drivers", "Sizing driver ledger", drivers), section("sizing", "Reproducible market sizing", [data["sizing"]], "SOM is capped by reachable accounts, delivery capacity and SAM. Export these same drivers to Finance Lab.")]
        if not w["inclusions"] or not w["exclusions"]: gaps.append("Define market inclusions and exclusions before reusing the sizing claim.")
        if not selected: gaps.append("Select a recorded segment and explain why the founder can reach it.")
    elif agent == "customer":
        guide = w["guide"] or [{"question": q, "purpose": "Learn about a real past event and its buying context."} for q in data["interview_guide"]]
        observations, themes = [], defaultdict(list)
        for item in w["observations"]:
            source = sources.get(item["source_id"])
            status = provenance(item, sources)
            valid = bool(source and source["kind"] == "interview" and source["consent"] in {"notes_only", "quote_permitted"} and status == "quoted_source")
            row = {**item, "participant_code": source["participant_code"] if source else None, "evidence_status": status if valid else "needs_source_review"}
            observations.append(row)
            if valid: themes[item["theme"]].append(row)
            else: gaps.append("A coded observation must quote its selected consented interview: " + item["theme"])
        counts = [{"theme": theme, "participants": len({r["participant_code"] for r in rows}), "observations": len(rows), "roles": ", ".join(sorted({r["role"] for r in rows})), "sources": ", ".join(sorted({r["source_id"] for r in rows})), "behavioral_observations": sum(r["kind"] not in {"opinion", "hypothetical_intent"} for r in rows)} for theme, rows in themes.items()]
        sections = [section("plan", "Discovery plan", [{"decision": w["decision"] or context["objective"], "hypothesis": context["hypothesis"], "target_segment": w["target_segment"] or context["concept"].get("customer_segment", "unknown"), "recruitment_criteria": w["recruitment_criteria"], "recruitment_bias": w["recruitment_bias"], "mode": w["mode"]}]), section("guide", "Interview guide", guide), section("coding", "Coded observations", observations, "Private notes remain scoped to this venture. Quote permission is separate from processing permission."), section("themes", "Theme synthesis", counts, "Counts describe this sample only; they are not population estimates."), section("decision", "Discovery decision", [{"choice": w["decision_choice"], "reason": w["decision_reason"], "next_test": w["next_test"]}])]
        if w["mode"] == "synthesis" and not counts: gaps.append("Code exact observations into themes before treating this as a customer synthesis.")
        if w["decision_choice"] != "pending" and not w["decision_reason"]: gaps.append("Explain what evidence changed the discovery decision.")
        action = "Capture consented interviews." if w["mode"] == "plan" else w["next_test"] or "Choose continue, revise, pivot, stop or another discovery round with an evidence-based reason."
    elif agent == "competitor":
        profiles = {r["alternative"]: r for r in w["profiles"]}
        rows = []
        for alt in data["alternative_map"]:
            profile = profiles.get(alt["name"], {})
            trusted = provenance(profile, sources) == "quoted_source"
            period = profile.get("price_period", "unknown")
            price = Decimal(alt["price_inr"]) if alt["price_inr"] is not None and trusted else None
            annual = price * 12 if price is not None and period == "month" else price if period == "year" else None
            rows.append({"alternative": alt["name"], "kind": alt["kind"], "workflow": profile.get("workflow", "unknown"), "capabilities": profile.get("capabilities", "unknown"), "annual_price_inr": money(annual) if annual is not None else None, "price_period": period, "price_unit": profile.get("price_unit", "unknown"), "tier": profile.get("customer_tier", "unknown"), "included_services": profile.get("included_services", "unknown"), "setup_fee_inr": profile.get("setup_fee_inr"), "switching_barrier": alt["switching_barrier"], "source_id": profile.get("source_id"), "evidence_status": provenance(profile, sources)})
        for kind, title in [("status_quo", "Current workflow"), ("non_consumption", "Doing nothing")]:
            if not any(r["kind"] == kind for r in rows):
                rows.append({"alternative": title, "kind": kind, "workflow": w[kind], "evidence_status": "unknown" if w[kind] == "unknown" else "founder_assumption"})
        sections = [section("universe", "Competitor and substitute comparison", rows, "Compare prices only when unit, tier and included services match. Unknown or one-time prices are not annualized."), section("differentiation", "Falsifiable differentiation", source_rows(w["differentiation"], sources))]
        if not w["differentiation"]: gaps.append("Name a customer benefit, required proof and a test that could disprove the differentiation.")
        action = "Test the switching benefit with the selected segment before using it as a positioning claim."
    elif agent == "model":
        blocks = ["customer_segments", "value_propositions", "channels", "customer_relationships", "revenue_streams", "key_resources", "key_activities", "key_partners", "cost_structure"]
        entered = {r["block"]: r for r in w["canvas"]}
        canvas = [{"block": block, "value": entered.get(block, {}).get("value", "unknown"), "evidence_status": provenance(entered.get(block, {}), sources), "source_id": entered.get(block, {}).get("source_id"), "owner": entered.get(block, {}).get("owner", "Founder"), "next_test": entered.get(block, {}).get("test", "")} for block in blocks]
        options = []
        for option in w["options"]:
            warnings = []
            if option["relationship"] in {"b2b", "b2b2c"}: warnings.append("Test budget owner, procurement, security review and implementation cycle.")
            if option["operating"] == "marketplace": warnings.append("Test supply, demand, trust, liquidity and take-rate pressure separately.")
            if option["pricing"] == "freemium": warnings.append("Identify the paying customer and conversion trigger; free use is not revenue.")
            revenue = Decimal(option["price_inr"]) * option["units_per_period"] if option["price_inr"] is not None and option["units_per_period"] is not None else None
            options.append({**option, "revenue_hypothesis_inr": money(revenue) if revenue is not None else None, "formula": "price per revenue unit × units per period", "status": "selected_hypothesis" if option["name"] == w["selected_option"] else "alternative_hypothesis", "checks": " ".join(warnings)})
        selected = next((o for o in options if o["name"] == w["selected_option"]), None)
        if selected:
            data["fields"]["Buyer"] = selected["payer"]
            data["fields"]["Customer relationships"] = selected["relationship"]
            data["fields"]["Channels"] = selected["channel"]
            data["fields"]["Pricing hypothesis"] = selected["price_inr"] if selected["price_inr"] is not None else "unknown"
        for entry in canvas:
            if entry["value"] != "unknown": data["fields"][entry["block"].replace("_", " ").capitalize()] = entry["value"]
        sections = [section("stakeholders", "Stakeholder economics", w["stakeholders"]), section("canvas", "Business Model Canvas", canvas), section("options", "Three-option comparison", options, "Relationship, operation, delivery and pricing are separate choices. Prices and volumes are hypotheses."), section("memo", "Model decision memo", [{"selected_option": w["selected_option"] or "unknown", "reason": w["decision_reason"], "pricing_behavior": w["pricing_behavior"], "pricing_threshold": w["pricing_threshold"]}]), section("finance_handoff", "Revenue drivers for Finance Lab", [selected] if selected else [])]
        if len(options) < 2: gaps.append("Compare at least two plausible options; the MVP supports three.")
        if not selected: gaps.append("Select a model option and record the decision rationale.")
        if not w["pricing_behavior"] or not w["pricing_threshold"]: gaps.append("Predeclare the observed behavior and decision threshold for the price test.")
        action = "Review the chosen model, export its explicit drivers to Finance Lab and run the price test."
    else:
        from .workspace_reports_remaining import remaining_report
        sections, gaps, action = remaining_report(agent, p, w, context, data)
    return WorkspaceReport(sections=sections, gaps=gaps, next_action=action).model_dump(mode="json")
