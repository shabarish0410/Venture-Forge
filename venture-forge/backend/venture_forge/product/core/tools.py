"""Versioned, deterministic tools. Inputs are assumptions, never observed demand."""
from decimal import Decimal, ROUND_HALF_UP

CAPABILITIES = [
    ("home", "Mentor Home", "ForgeGuide", "experience"),
    ("research", "Research Desk", "EvidenceScout", "evidence"),
    ("market", "Market Lab", "MarketMapper", "economics"),
    ("customer", "Customer Lab", "CustomerLens", "customer"),
    ("competitor", "Competitor Room", "RivalRadar", "evidence"),
    ("model", "Model Studio", "ModelArchitect", "economics"),
    ("finance", "Finance Lab", "FinancePilot", "economics"),
    ("experiment", "MVP and Experiment Lab", "MVPForge", "customer"),
    ("simulation", "Simulation Arena", "VentureSim", "economics"),
    ("academy", "Founder Academy", "SkillCoach", "experience"),
    ("ecosystem", "Ecosystem Hub", "EcosystemNavigator", "pathways"),
    ("investor", "Investor Room", "InvestorRoom", "pathways"),
    ("passport", "Venture Passport", "PassportKeeper", "record"),
]


def money(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def unit_economics(inputs, revenue, gross_profit):
    cac = None
    if inputs.acquisition_spend is not None and inputs.new_customers is not None and inputs.new_customers > 0:
        cac = money(inputs.acquisition_spend / inputs.new_customers)
    lifetime_revenue = None
    if inputs.average_revenue_per_customer is not None and inputs.customer_lifetime_periods is not None:
        lifetime_revenue = inputs.average_revenue_per_customer * inputs.customer_lifetime_periods
    notes = ["Acquisition spend classifies existing scenario costs; it is not deducted again from cash.", "Lifetime value assumes constant revenue and gross margin; it does not model discounting, churn changes or future growth."]
    if cac is None: notes.append("CAC is undefined without acquisition spend and a positive count of new paying customers in the same period.")
    if lifetime_revenue is None: notes.append("LTV is unknown without average customer revenue and customer lifetime in the same month/year units.")
    elif not revenue: notes.append("Gross-profit LTV is undefined because the scenario has no revenue from which to calculate gross margin.")
    return {
        "cac_inr": cac,
        "ltv_revenue_inr": money(lifetime_revenue) if lifetime_revenue is not None else None,
        "ltv_gross_profit_inr": money(lifetime_revenue * gross_profit / revenue) if lifetime_revenue is not None and revenue else None,
        "unit_economics_notes": notes,
    }


def calculate(capability, inputs):
    if capability in {"finance", "simulation"}:
        revenue = inputs.price * inputs.volume
        cost = inputs.direct_cost
        profit = revenue - cost
        margin = money(profit / revenue * 100) if revenue else None
        burn = inputs.fixed_cost + cost - inputs.collected_cash
        return {
            "revenue": money(revenue), "direct_cost": money(cost),
            "gross_profit": money(profit), "gross_margin_percent": margin,
            "cash_change": money(-burn),
            "ending_cash": money(inputs.cash_balance - burn),
            "runway_periods": money(inputs.cash_balance / burn) if burn > 0 else None,
            **unit_economics(inputs, revenue, profit),
            "currency": "INR", "period": inputs.period,
            "formula_version": "finance-decimal-v2",
            "formula": "revenue = price × volume; profit = revenue - direct cost; cash = collected cash - direct cost - fixed cost; CAC = acquisition spend / new paying customers; revenue LTV = average revenue per customer per period × customer lifetime periods; gross-profit LTV = revenue LTV × unrounded gross margin",
            "status": "SIMULATED" if capability == "simulation" else "ASSUMPTIONS",
        }
    units = min(inputs.reachable_accounts, inputs.capacity, inputs.serviceable_accounts)
    return {
        "tam": money(inputs.total_accounts * inputs.price),
        "sam": money(inputs.serviceable_accounts * inputs.price),
        "som": money(units * inputs.price), "som_accounts": units,
        "currency": "INR", "period": inputs.period, "unit": inputs.unit,
        "formula": "TAM = accounts × price; SAM = serviceable accounts × price; SOM = min(reach, capacity, serviceable accounts) × price",
        "status": "ASSUMPTIONS",
    }
