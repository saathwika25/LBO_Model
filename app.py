import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO

st.set_page_config(page_title="LBO Deal Studio", layout="wide")
st.title("💼 LBO Deal Studio")

with st.expander("📘 What is an LBO? (Click to Expand)", expanded=False):
    st.markdown("""
**Leveraged Buyout (LBO)** is a strategy where an investor (usually a private equity firm) acquires a company using a significant amount of debt.  
The debt is repaid over time using the company’s cash flows, and the investor aims to generate a high return on equity when exiting the deal.

**Key Concepts:**
- 🔹 High Debt: Fund most of the deal with borrowed money
- 🔹 Free Cash Flows: Used to repay debt
- 🔹 Exit: Sell the company after a few years at a profit
- 🔹 Goal: Maximize IRR (Internal Rate of Return) and MOIC (Multiple on Invested Capital)

**Real Example:**  
Imagine buying a ₹1000 Cr company using ₹700 Cr debt and ₹300 Cr equity.  
If you grow the company and sell it for ₹2000 Cr, you repay the debt and keep the profit — often earning 2–3x your money.
""")

with st.expander("📊 Where to Get Inputs From (Data Sources)", expanded=False):
    st.markdown("""
You can pull most of the financials from:

- **[Screener.in](https://www.screener.in/)** → Download company data (.CSV)
- **Annual Reports** → See EBITDA, CapEx, Revenue
- **Investor Presentations / Earnings Calls**
- **Industry Reports** → For average EBITDA multiples

**Common Ranges:**
| Input | Typical Range | Notes |
|------|---------------|-------|
| EBITDA Multiple | 6x–12x | Depends on industry, growth |
| Debt-to-Equity | 50–80% debt | More debt = more risk & return |
| EBITDA Margin | 10–25% | Varies widely by sector |
| CapEx % of Revenue | 5–15% | Higher for capital-heavy businesses |
| Tax Rate | 25–30% | Standard for Indian companies |
""")

# ---------- IRR Function ----------
def calculate_irr(cash_flows, iterations=100):
    rate = 0.1
    for _ in range(iterations):
        denominator = [(1 + rate) ** i for i in range(len(cash_flows))]
        value = sum([cf / d for cf, d in zip(cash_flows, denominator)])
        derivative = sum([-i * cf / ((1 + rate) ** (i + 1)) for i, cf in enumerate(cash_flows)])
        rate -= value / derivative
    return rate

# ---------- Autofill ----------
company_data = {
    "DMart": {
        "purchase_price": 70000,
        "entry_ebitda": 3000,
        "entry_multiple": 23,
        "debt_ratio": 30,
        "tax_rate": 25,
        "capex_pct": 6,
        "ebitda_margin": 9
    },
    "Zomato": {
        "purchase_price": 50000,
        "entry_ebitda": 100,
        "entry_multiple": 50,
        "debt_ratio": 10,
        "tax_rate": 0,
        "capex_pct": 4,
        "ebitda_margin": 1
    }
}

# ---------- Sidebar Inputs ----------
st.sidebar.header("📊 Deal Setup")
company_choice = st.sidebar.selectbox("🔍 Load Company Template", ["None"] + list(company_data.keys()))

if company_choice != "None":
    preset = company_data[company_choice]
    st.session_state.purchase_price = preset["purchase_price"]
    st.session_state.entry_ebitda = preset["entry_ebitda"]
    st.session_state.entry_multiple = preset["entry_multiple"]
    st.session_state.debt_ratio = preset["debt_ratio"]
    st.session_state.tax_rate = preset["tax_rate"]
    st.session_state.capex_pct = preset["capex_pct"]
    st.session_state.ebitda_margin = preset["ebitda_margin"]

company_name = st.sidebar.text_input("Target Company Name", "SampleCo")

purchase_price = st.sidebar.number_input("Purchase Price (₹ Cr)", value=st.session_state.get("purchase_price", 1000.0))
transaction_fee_pct = st.sidebar.number_input("Transaction Fee (%)", value=2.0) / 100
entry_ebitda = st.sidebar.number_input("Entry EBITDA (₹ Cr)", value=st.session_state.get("entry_ebitda", 100.0))
entry_multiple = st.sidebar.number_input("Entry EBITDA Multiple (x)", value=st.session_state.get("entry_multiple", 8.0))
holding_period = st.sidebar.slider("Holding Period (Years)", 1, 10, 5)

# ---------- Financing ----------
st.sidebar.header("💰 Financing Assumptions")
debt_ratio = st.sidebar.slider("Debt-to-Equity Ratio (%)", 0, 100, value=st.session_state.get("debt_ratio", 70))
interest_rate = st.sidebar.number_input("Interest Rate on Debt (%)", value=8.0) / 100
amort_years = st.sidebar.number_input("Amortization Period (Years)", value=5)
tax_rate = st.sidebar.number_input("Corporate Tax Rate (%)", value=st.session_state.get("tax_rate", 25.0)) / 100

# ---------- Operations ----------
st.sidebar.header("📈 Operating Assumptions")
ebitda_margin = st.sidebar.number_input("EBITDA Margin (%)", value=st.session_state.get("ebitda_margin", 20.0)) / 100
capex_pct = st.sidebar.number_input("CapEx as % of Revenue", value=st.session_state.get("capex_pct", 10.0)) / 100
depreciation_pct = st.sidebar.number_input("Depreciation as % of CapEx", value=60.0) / 100
wc_pct = st.sidebar.number_input("Working Capital Change (% of Revenue)", value=5.0) / 100

# ---------- Scenarios ----------
st.sidebar.header("🔁 Scenario Modeling")
scenario_inputs = {
    "Base Case": {
        "growth_rate": st.sidebar.number_input("Base EBITDA Growth Rate (%)", value=5.0) / 100,
        "exit_multiple": st.sidebar.number_input("Base Exit Multiple (x)", value=10.0)
    },
    "Upside Case": {
        "growth_rate": st.sidebar.number_input("Upside EBITDA Growth Rate (%)", value=7.0) / 100,
        "exit_multiple": st.sidebar.number_input("Upside Exit Multiple (x)", value=12.0)
    },
    "Downside Case": {
        "growth_rate": st.sidebar.number_input("Downside EBITDA Growth Rate (%)", value=3.0) / 100,
        "exit_multiple": st.sidebar.number_input("Downside Exit Multiple (x)", value=8.0)
    }
}

# ---------- LBO Logic ----------
def run_lbo(growth_rate, exit_multiple):
    fee = purchase_price * transaction_fee_pct
    total_price = purchase_price + fee
    debt = total_price * (debt_ratio / 100)
    equity = total_price - debt
    debt_remaining = debt
    cash_flows = [-equity]
    table = []

    for year in range(1, holding_period + 1):
        ebitda = entry_ebitda * ((1 + growth_rate) ** (year - 1))
        revenue = ebitda / ebitda_margin
        capex = revenue * capex_pct
        depreciation = capex * depreciation_pct
        wc_change = revenue * wc_pct
        interest = debt_remaining * interest_rate
        taxable_income = ebitda - interest - depreciation
        tax = max(taxable_income, 0) * tax_rate
        net_income = taxable_income - tax
        fcf = net_income + depreciation - capex - wc_change
        amort = debt / amort_years if year <= amort_years else 0
        debt_remaining = max(debt_remaining - amort, 0)
        cash_flows.append(fcf)

        table.append({
            "Year": year,
            "EBITDA": ebitda,
            "Revenue": revenue,
            "CapEx": capex,
            "Depreciation": depreciation,
            "Interest": interest,
            "Tax": tax,
            "FCF": fcf,
            "Debt Remaining": debt_remaining
        })

    exit_ebitda = entry_ebitda * ((1 + growth_rate) ** holding_period)
    exit_value = exit_ebitda * exit_multiple
    proceeds = exit_value - debt_remaining
    cash_flows[-1] += proceeds

    irr = calculate_irr(cash_flows) * 100
    moic = proceeds / equity
    return irr, moic, pd.DataFrame(table)

# ---------- Output Section ----------
st.subheader(f"📈 IRR & MOIC Results for {company_name}")
results = []
tables = {}
for scenario, params in scenario_inputs.items():
    irr, moic, table = run_lbo(**params)
    results.append({"Scenario": scenario, "IRR (%)": irr, "MOIC (x)": moic})
    tables[scenario] = table

df_results = pd.DataFrame(results)
st.dataframe(df_results.style.format({"IRR (%)": "{:.2f}", "MOIC (x)": "{:.2f}"}), use_container_width=True)

# ---------- Chart ----------
st.subheader("📊 IRR by Scenario")
fig = go.Figure()
fig.add_trace(go.Bar(
    x=df_results["Scenario"],
    y=df_results["IRR (%)"],
    marker_color=["#1f77b4", "#2ca02c", "#d62728"]
))
fig.update_layout(template="plotly_white", yaxis_title="IRR (%)")
st.plotly_chart(fig, use_container_width=True)

# ---------- Cash Flow Table ----------
st.subheader("🧾 Cash Flow Table (Base Case)")
base_table = tables["Base Case"]
st.dataframe(base_table.style.format("{:.2f}"), use_container_width=True)

# ---------- Excel Export ----------
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="LBO_CashFlows", index=False)
    return output.getvalue()

excel_data = to_excel(base_table)
st.download_button("📥 Download Excel", data=excel_data, file_name="LBO_CashFlows_BaseCase.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------- Sensitivity Table ----------
st.subheader("📊 IRR Sensitivity (Exit Multiple × Holding Period)")
exit_range = np.arange(8, 16)
hold_range = np.arange(3, 11)
base_growth = scenario_inputs["Base Case"]["growth_rate"]

irr_grid = []
for h in hold_range:
    row = []
    for x in exit_range:
        exit_ebitda = entry_ebitda * ((1 + base_growth) ** h)
        exit_val = exit_ebitda * x
        total_equity = purchase_price * (1 - debt_ratio / 100) + (purchase_price * transaction_fee_pct)
        cash_flows = [-total_equity]
        for y in range(h):
            cash_flows.append(entry_ebitda * ((1 + base_growth) ** y))
        cash_flows[-1] += exit_val
        irr_val = calculate_irr(cash_flows) * 100
        row.append(irr_val)
    irr_grid.append(row)

irr_df = pd.DataFrame(irr_grid, index=hold_range, columns=exit_range)
st.dataframe(irr_df.style.background_gradient(cmap='Greens').format("{:.1f}"), use_container_width=True)
