"""Golden cases and workflow boundaries for deterministic financial arithmetic."""
import pytest
from pydantic import ValidationError
from venture_forge.product.core.workflow_schemas import FinanceInputs
from venture_forge.product.core.tools import calculate
from venture_forge.product.agents.outputs import FinancialModel
from test_evidence_cycle import cycle
from test_specialists import run_and_accept


def inputs(**values):
    return FinanceInputs(**{"price": "100", "volume": 10, "direct_cost": "400", "fixed_cost": "300", "collected_cash": "800", "cash_balance": "2000", "acquisition_spend": "500", "new_customers": 5, "average_revenue_per_customer": "100", "customer_lifetime_periods": "12", **values})


def test_cac_ltv_cash_and_runway_golden_case():
    result = calculate("finance", inputs())
    assert {k: result[k] for k in ("revenue", "gross_margin_percent", "cac_inr", "ltv_revenue_inr", "ltv_gross_profit_inr", "cash_change", "ending_cash", "runway_periods")} == {
        "revenue": "1000.00", "gross_margin_percent": "60.00", "cac_inr": "100.00", "ltv_revenue_inr": "1200.00", "ltv_gross_profit_inr": "720.00", "cash_change": "100.00", "ending_cash": "2100.00", "runway_periods": None,
    }
    assert result["formula_version"] == "finance-decimal-v2" and result["status"] == "ASSUMPTIONS"
    # Acquisition spend is a classification of existing costs, not another cash deduction.
    assert calculate("finance", inputs(acquisition_spend="600"))["cash_change"] == "100.00"


def test_round_only_final_money_and_use_unrounded_margin_for_ltv():
    result = calculate("finance", inputs(price="120000", volume=1, direct_cost="50000", acquisition_spend="1", new_customers=8, average_revenue_per_customer="100", customer_lifetime_periods="3"))
    assert result["cac_inr"] == "0.13"  # Half-up rounding of 0.125.
    assert result["gross_margin_percent"] == "58.33"
    assert result["ltv_revenue_inr"] == "300.00" and result["ltv_gross_profit_inr"] == "175.00"


def test_unknown_inputs_zero_denominators_and_zero_values_are_distinct():
    empty = inputs(acquisition_spend=None, new_customers=None, average_revenue_per_customer=None, customer_lifetime_periods=None)
    result = calculate("finance", empty)
    assert result["cac_inr"] is None and result["ltv_revenue_inr"] is None and result["ltv_gross_profit_inr"] is None
    assert calculate("finance", inputs(new_customers=None))["cac_inr"] is None
    assert calculate("finance", inputs(new_customers=0))["cac_inr"] is None
    assert calculate("finance", inputs(acquisition_spend="0"))["cac_inr"] == "0.00"
    result = calculate("finance", inputs(price="0", average_revenue_per_customer="0", collected_cash="0", cash_balance="0"))
    assert result["ltv_revenue_inr"] == "0.00" and result["ltv_gross_profit_inr"] is None
    assert result["gross_margin_percent"] is None and result["ending_cash"] == "-700.00"


@pytest.mark.parametrize("values", [{"acquisition_spend": "-1"}, {"acquisition_spend": "NaN"}, {"acquisition_spend": "800"}, {"new_customers": 1.5}, {"customer_lifetime_periods": "0"}, {"period": "cohort"}])
def test_invalid_financial_values_and_mixed_lifetime_units_are_rejected(values):
    with pytest.raises(ValidationError): inputs(**values)


def test_financial_output_contract_rejects_replaced_figures():
    drivers = inputs()
    figures = calculate("finance", drivers)
    figures["cac_inr"] = "0.00"
    with pytest.raises(ValidationError, match="deterministic calculation"):
        FinancialModel(drivers=drivers, financials=figures, actuals_status="Planning assumptions")


def test_reviewed_finance_drivers_flow_into_a_deterministic_simulation(cycle):
    client, app, p = cycle
    p, finance = run_and_accept(client, app, p, "finance", parameters=inputs().model_dump(mode="json"))
    assert finance["result"]["data"]["financials"]["cac_inr"] == "100.00"
    p, simulation = run_and_accept(client, app, p, "simulation", artifact_ids=[finance["artifact_id"]], parameters={"price_factor": "2", "volume_factor": "1"})
    data = simulation["result"]["data"]
    assert data["formula_version"] == "finance-decimal-v2" and data["status"] == "SIMULATED"
    assert data["baseline"]["ltv_revenue_inr"] == "1200.00"
    assert data["round"]["ltv_revenue_inr"] == "2400.00" and data["round"]["ltv_gross_profit_inr"] == "1920.00"
    assert data["round"]["cac_inr"] == "100.00" and data["round"]["cash_change"] == "100.00"
    assert p["completed_cycles"] == 0 and all(h["status"] == "unvalidated" for h in p["hypotheses"])
