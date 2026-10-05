# Deterministic Finance Lab

FinancePilot, Finance Lab worksheets and VentureSim use Python Decimal functions in `product/core/tools.py`. Models receive the calculated result for interpretation. A model cannot return replacement financial fields, and the specialist output contract independently checks that its figures match the calculation from its recorded drivers. Accepted versions retain their inputs and formula version.

## Explicit inputs and formulas

All monetary inputs use INR. Revenue, costs and collections use the same selected period. Units sold do not implicitly mean customers: enter the customer inputs separately.

| Output | Deterministic formula |
| --- | --- |
| Revenue | Price per unit × units sold |
| Gross profit | Revenue − direct delivery cost |
| Gross margin percentage | Gross profit ÷ revenue × 100 |
| Cash change | Collected cash − direct cost − fixed cost |
| Ending cash | Starting cash + cash change |
| Runway periods | Starting cash ÷ positive net cash burn |
| CAC in INR | Acquisition spend ÷ new paying customers |
| Revenue LTV in INR | Average customer revenue per period × customer lifetime periods |
| Gross-profit LTV in INR | Revenue LTV × the unrounded scenario gross margin |

CAC follows the same-period acquisition-cost definition in [Stripe's CAC guide](https://stripe.com/resources/more/cac-in-saas). Revenue LTV uses explicit average revenue and customer lifespan; the separate gross-profit estimate accounts for delivery costs, consistent with the distinctions in [Stripe's customer lifetime value guide](https://stripe.com/resources/more/customer-lifetime-value). The application does not infer customer lifespan or ARPU from an LLM, interview count or units sold.

The four optional inputs are `acquisition_spend`, `new_customers`, `average_revenue_per_customer` and `customer_lifetime_periods`. Leave them blank when unknown. A zero customer count makes CAC undefined; zero acquisition spend with a positive count produces a valid zero CAC. Missing LTV drivers produce `null`, and zero scenario revenue leaves gross margin and gross-profit LTV undefined. Nonpositive net burn leaves runway undefined rather than returning an invented infinity.

Acquisition spend classifies costs already included in the scenario's direct/fixed costs. It cannot exceed that total and is not deducted again from cash. Include acquisition costs in the appropriate cost bucket before using the CAC field. Costs are assumed paid during the period; this calculator does not model payment schedules or reconcile transactions.

LTV requires month or year units, with average revenue and customer lifetime in the same units. The `cohort` period can be used for other calculations but cannot carry LTV inputs. Lifetime estimates assume constant customer revenue and gross margin, with no discounting or changing retention/growth model. Negative gross profit can produce a negative gross-profit LTV. These are founder-entered planning assumptions, not observed demand or verified actuals.

Decimal arithmetic rounds only final displayed money using half-up rounding. Gross-profit LTV uses the raw margin fraction, so a displayed 58.33% does not replace an underlying 7/12 margin. Specialist forms preserve decimal amounts as strings until server parsing.

## Example

For price ₹100, volume 10, direct cost ₹400, fixed cost ₹300, collected cash ₹800 and starting cash ₹2,000, the tool returns ₹1,000 revenue, 60% gross margin, ₹100 cash change and ₹2,100 ending cash. Classification of ₹500 of those existing costs as acquisition spend for five new customers gives ₹100 CAC. An assumed ₹100 per customer per month for 12 months gives ₹1,200 revenue LTV and ₹720 gross-profit LTV. Changing the acquisition classification does not charge the cash model a second time.

VentureSim reads accepted finance drivers. Its price factor also scales assumed average customer revenue; customer count, acquisition spend and lifetime otherwise remain explicit carried assumptions. Simulation cannot count as a real experiment or validated hypothesis.

The current formula version is `finance-decimal-v2`. Existing saved outputs remain historical records; new runs calculate the current version. No transaction feed, payment action or paid model request is required for these tools.
