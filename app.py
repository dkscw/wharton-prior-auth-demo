from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from prior_auth.engine import BaseInputs, ModelInputs, simulate_current_workflow, simulate_model_workflow

st.set_page_config(page_title="Prior Authorization AI Economics", page_icon="🩺", layout="wide")

st.markdown(
    """
<style>
html, body, [class*="css"] {
    font-size: 19px;
}
.stMarkdown, .stCaption, .stText, .stDataFrame, .stMetric, .stSlider, .stNumberInput {
    font-size: 1.08rem;
}
h1 {
    font-size: 2.8rem !important;
}
h2 {
    font-size: 2.25rem !important;
}
h3 {
    font-size: 1.8rem !important;
}
h4 {
    font-size: 1.4rem !important;
}
button, input, label, [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {
    font-size: 1.08rem !important;
}
[data-testid="stCaptionContainer"] {
    font-size: 1rem !important;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Prior Authorization AI: Model Metrics → Business Value")
st.caption(
    "A teaching simulator for connecting workflow economics to model evaluation."
)


def pct(x: float) -> str:
    return f"{100*x:.1f}%"


def money(x: float) -> str:
    return f"${x:,.0f}"


def cases(x: float) -> str:
    return f"{x:,.0f}"


def workflow_table(result: dict) -> pd.DataFrame:
    df = pd.DataFrame(result["stages"])
    for c in ["cases", "appropriate", "inappropriate"]:
        df[c] = df[c].map(cases)
    return df.rename(columns={"stage": "Stage", "cases": "Cases", "appropriate": "Appropriate", "inappropriate": "Inappropriate"})


def current_workflow_table(result: dict) -> pd.DataFrame:
    df = pd.DataFrame(result["stages"])
    df["cases"] = df["cases"].map(cases)
    return df.rename(columns={"stage": "Stage", "cases": "Cases"})


def current_workflow_graph(result: dict) -> str:
    def node_label(label: str, value: float) -> str:
        return f"{label}\\n{value:,.0f}"

    initial_cases = result["initial_cases"]
    rn_reviewed = result["portal_queue"]
    md_reviewed = result["md_reviewed"]

    portal_rate = result["portal_approved"] / initial_cases if initial_cases else 0
    rn_review_rate = rn_reviewed / initial_cases if initial_cases else 0
    rn_approval_rate = result["rn_approved"] / rn_reviewed if rn_reviewed else 0
    md_review_rate = md_reviewed / rn_reviewed if rn_reviewed else 0
    md_approval_rate = result["md_approved"] / md_reviewed if md_reviewed else 0
    denial_rate = result["final_denials"] / md_reviewed if md_reviewed else 0

    return f"""
digraph {{
    graph [rankdir=LR, bgcolor="transparent", pad="0.25", nodesep="0.7", ranksep="1.0"];
    node [shape=box, style="rounded,filled", width=2.35, height=0.95, fixedsize=true, fontname="Helvetica", fontsize=18, color="#9ca3af", fillcolor="#f9fafb"];
    edge [color="#9ca3af", arrowsize=0.8, fontsize=15, fontname="Helvetica"];

    initial [label="{node_label("Initial cases", result["initial_cases"])}"];
    portal [label="{node_label("Portal approved", result["portal_approved"])}"];
    rn_review [label="{node_label("RN review", result["portal_queue"])}"];
    rn_approved [label="{node_label("RN approved", result["rn_approved"])}"];
    md_review [label="{node_label("MD review", result["md_reviewed"])}"];
    md_approved [label="{node_label("MD approved", result["md_approved"])}"];
    denied [label="{node_label("Deemed inappropriate", result["final_denials"])}", fillcolor="#fef2f2", color="#fca5a5"];

    initial -> portal [label="{portal_rate:.0%}"];
    initial -> rn_review [label="{rn_review_rate:.0%}"];
    rn_review -> rn_approved [label="{rn_approval_rate:.0%}"];
    rn_review -> md_review [label="{md_review_rate:.0%}"];
    md_review -> md_approved [label="{md_approval_rate:.0%}"];
    md_review -> denied [label="{denial_rate:.0%}"];
}}
"""


def current_inputs() -> BaseInputs:
    st.markdown("#### Workflow assumptions")
    st.caption("Case volume: 1,000")
    portal_approval_rate = st.slider("Portal self-approval rate", 0.0, 90.0, 70.0, 1.0, format="%.0f%%", key="current_portal") / 100
    rn_approval_rate = st.slider("RN approval rate", 0.0, 100.0, 60.0, 1.0, format="%.0f%%", key="current_rn_approval") / 100
    md_approval_rate = st.slider("MD approval rate", 0.0, 100.0, 50.0, 1.0, format="%.0f%%", key="current_md_approval") / 100

    st.markdown("#### Economics assumptions")
    rn_cost = st.number_input("RN cost per review", 0.0, 500.0, 20.0, 5.0, key="current_rn_cost")
    md_cost = st.number_input("MD cost per review", 0.0, 1000.0, 100.0, 10.0, key="current_md_cost")
    savings_per_denial = st.number_input("Savings per case deemed inappropriate", 0.0, 100000.0, 1000.0, 100.0, key="current_save")
    outsourced_price = st.number_input("Client cost per case", 0.0, 500.0, 25.0, 5.0, key="current_price")

    return BaseInputs(
        initial_cases=1000.0,
        portal_approval_rate=portal_approval_rate,
        rn_approval_rate=rn_approval_rate,
        md_approval_rate=md_approval_rate,
        rn_cost=rn_cost,
        md_cost=md_cost,
        savings_per_denial=savings_per_denial,
        outsourced_price_per_case=outsourced_price,
    )


def model_base_inputs() -> BaseInputs:
    st.markdown("#### Workflow assumptions")
    st.caption("Case volume: 1,000")
    portal_approval_rate = st.slider("Portal self-approval rate", 0.0, 90.0, 70.0, 1.0, format="%.0f%%", key="model_portal") / 100
    rn_approval_rate = st.slider("RN approval rate", 0.0, 100.0, 60.0, 1.0, format="%.0f%%", key="model_rn_approval") / 100
    md_approval_rate = st.slider("MD approval rate", 0.0, 100.0, 50.0, 1.0, format="%.0f%%", key="model_md_approval") / 100

    st.markdown("#### Economics assumptions")
    rn_cost = st.number_input("RN cost per review", 0.0, 500.0, 20.0, 5.0, key="model_rn_cost")
    md_cost = st.number_input("MD cost per review", 0.0, 1000.0, 100.0, 10.0, key="model_md_cost")
    savings_per_denial = st.number_input("Savings per case deemed inappropriate", 0.0, 100000.0, 1000.0, 100.0, key="model_save")
    outsourced_price = st.number_input("Client cost per case", 0.0, 500.0, 25.0, 5.0, key="model_price")

    return BaseInputs(
        initial_cases=1000.0,
        portal_approval_rate=portal_approval_rate,
        rn_approval_rate=rn_approval_rate,
        md_approval_rate=md_approval_rate,
        rn_cost=rn_cost,
        md_cost=md_cost,
        savings_per_denial=savings_per_denial,
        outsourced_price_per_case=outsourced_price,
    )


def model_workflow_graph(result: dict) -> str:
    def node_label(label: str, value: float) -> str:
        return f"{label}\\n{value:,.0f}"

    def edge_rate(part: float, whole: float) -> str:
        return f"{part / whole:.0%}" if whole else "0%"

    initial_cases = result.get("initial_cases", 1000.0)
    rn_model_total = result["portal_queue"]
    portal_approved = result.get("portal_approved", initial_cases - rn_model_total)
    rn_reviewed = result["rn_reviewed"]
    md_model_total = result["md_queue"]
    human_md_reviewed = result["human_md_reviewed"]

    return f"""
digraph {{
    graph [rankdir=LR, bgcolor="transparent", pad="0.25", nodesep="0.7", ranksep="1.0"];
    node [shape=box, style="rounded,filled", width=2.35, height=0.95, fixedsize=true, fontname="Helvetica", fontsize=18, color="#9ca3af", fillcolor="#f9fafb"];
    edge [color="#9ca3af", arrowsize=0.8, fontsize=15, fontname="Helvetica"];

    initial [label="{node_label("Initial cases", initial_cases)}"];
    portal [label="{node_label("Portal approved", portal_approved)}"];
    rn_model [label="{node_label("RN model", rn_model_total)}", fillcolor="#eff6ff", color="#93c5fd"];
    rn_model_approved [label="{node_label("RN model approved", result["nurse_model_autoapproved"])}", fillcolor="#eff6ff", color="#93c5fd"];
    rn_review [label="{node_label("RN review", rn_reviewed)}"];
    rn_approved [label="{node_label("RN approved", result["rn_approved"])}"];
    md_model [label="{node_label("MD model", md_model_total)}", fillcolor="#eff6ff", color="#93c5fd"];
    md_model_approved [label="{node_label("MD model approved", result["md_model_autoapproved"])}", fillcolor="#eff6ff", color="#93c5fd"];
    md_review [label="{node_label("MD review", human_md_reviewed)}"];
    md_approved [label="{node_label("MD approved", result["human_md_approved"])}"];
    denied [label="{node_label("Deemed inappropriate", result["final_denials"])}", fillcolor="#fef2f2", color="#fca5a5"];

    initial -> portal [label="{edge_rate(portal_approved, initial_cases)}"];
    initial -> rn_model [label="{edge_rate(rn_model_total, initial_cases)}"];
    rn_model -> rn_model_approved [label="{edge_rate(result["nurse_model_autoapproved"], rn_model_total)}"];
    rn_model -> rn_review [label="{edge_rate(rn_reviewed, rn_model_total)}"];
    rn_review -> rn_approved [label="{edge_rate(result["rn_approved"], rn_reviewed)}"];
    rn_review -> md_model [label="{edge_rate(md_model_total, rn_reviewed)}"];
    md_model -> md_model_approved [label="{edge_rate(result["md_model_autoapproved"], md_model_total)}"];
    md_model -> md_review [label="{edge_rate(human_md_reviewed, md_model_total)}"];
    md_review -> md_approved [label="{edge_rate(result["human_md_approved"], human_md_reviewed)}"];
    md_review -> denied [label="{edge_rate(result["final_denials"], human_md_reviewed)}"];
}}
"""


def show_current_metrics(result: dict) -> None:
    a, b, c, d = st.columns(4)
    a.metric("Total cases", cases(result["initial_cases"]))
    b.metric("Deemed inappropriate", cases(result["final_denials"]))
    c.metric("Total review cost", money(result["review_cost"]))
    d.metric("Net value", money(result["net_savings"]))


def model_economics_table(result: dict, base: BaseInputs) -> pd.DataFrame:
    rn_automated = result["nurse_model_autoapproved"]
    md_automated = result["md_model_autoapproved"]
    rn_missed = result["missed_nurse_model"]
    md_missed = result["missed_md_model"]
    rows = [
        ("RN model", rn_automated, rn_automated * base.rn_cost, rn_missed),
        ("MD model", md_automated, md_automated * base.md_cost, md_missed),
    ]
    table = pd.DataFrame(
        rows,
        columns=["Model", "Cases automated", "Review cost saved", "Inappropriate cases missed"],
    )
    table["Lost deemed-inappropriate value"] = table["Inappropriate cases missed"] * base.savings_per_denial
    table["Net model value"] = table["Review cost saved"] - table["Lost deemed-inappropriate value"]
    table["Cases automated"] = table["Cases automated"].map(cases)
    table["Review cost saved"] = table["Review cost saved"].map(money)
    table["Inappropriate cases missed"] = table["Inappropriate cases missed"].map(cases)
    table["Lost deemed-inappropriate value"] = table["Lost deemed-inappropriate value"].map(money)
    table["Net model value"] = table["Net model value"].map(money)
    return table


def workflow_economics_table(result: dict) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Metric": [
                "Gross savings from deemed inappropriate cases",
                "RN review cost",
                "MD review cost",
                "Total review cost",
                "Net value",
                "Gross savings / review cost",
                "Client cost",
                "Client ROI",
                "PA margin",
            ],
            "Value": [
                money(result["gross_savings"]),
                money(result["rn_review_cost"]),
                money(result["md_review_cost"]),
                money(result["review_cost"]),
                money(result["net_savings"]),
                f'{result["roi"]:.2f}x',
                money(result["client_cost"]),
                f'{result["client_roi"]:.2f}x',
                pct(result["vendor_margin"]),
            ],
        }
    )


def model_economics_html(table: pd.DataFrame) -> str:
    headers = "".join(f"<th>{escape(column)}</th>" for column in table.columns)
    rows = []
    for row in table.itertuples(index=False):
        cells = "".join(f"<td>{escape(str(value))}</td>" for value in row)
        rows.append(f"<tr>{cells}</tr>")
    return f"""
<style>
.model-econ-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 1.35rem;
    line-height: 1.3;
}}
.model-econ-table th,
.model-econ-table td {{
    border-bottom: 1px solid #e5e7eb;
    padding: 0.65rem 0.8rem;
    text-align: right;
    vertical-align: middle;
}}
.model-econ-table th:first-child,
.model-econ-table td:first-child {{
    text-align: left;
    font-weight: 600;
}}
.model-econ-table th {{
    color: #374151;
    font-weight: 700;
}}
</style>
<table class="model-econ-table">
    <thead><tr>{headers}</tr></thead>
    <tbody>{''.join(rows)}</tbody>
</table>
"""


current_tab, model_tab = st.tabs(["1 · Existing workflow", "2 · Add nurse + MD models"])

with current_tab:
    st.subheader("Existing workflow: portal → RN → MD")
    st.write(
        "The default values reproduce the workbook baseline: 1,000 initial cases, 700 portal approvals, "
        "300 RN reviews, 120 MD reviews, 60 deemed inappropriate, $18k review cost, and $60k gross savings."
    )
    base = current_inputs()
    current = simulate_current_workflow(base)
    show_current_metrics(current)

    c1, c2 = st.columns([1.35, 1])
    with c1:
        st.markdown("#### Case flow")
        st.dataframe(current_workflow_table(current), use_container_width=True, hide_index=True)
    with c2:
        st.markdown("#### Economics")
        st.dataframe(workflow_economics_table(current), use_container_width=True, hide_index=True)
    st.caption("Workflow visualization")
    st.graphviz_chart(current_workflow_graph(current), use_container_width=True)

with model_tab:
    st.subheader("Proposed workflow: nurse model + human RN + MD model")
    st.write(
        "The RN model can approve or send to RN. The MD model can approve or send to MD."
    )

    base_m = model_base_inputs()

    st.markdown("#### Model assumptions")
    st.caption("Sensitivity: % of inappropriate cases correctly sent to human review. Specificity: % of appropriate cases correctly approved by the model.")
    rn_model_col, md_model_col = st.columns(2)
    with rn_model_col:
        st.markdown("**RN model**")
        nurse_sens = st.slider("RN model sensitivity", 0.0, 100.0, 90.0, 1.0, format="%.0f%%", key="nurse_sens") / 100
        nurse_spec = st.slider("RN model specificity", 0.0, 100.0, 70.0, 1.0, format="%.0f%%", key="nurse_spec") / 100

    with md_model_col:
        st.markdown("**MD model**")
        md_sens = st.slider("MD model sensitivity", 0.0, 100.0, 90.0, 1.0, format="%.0f%%", key="md_sens") / 100
        md_spec = st.slider("MD model specificity", 0.0, 100.0, 70.0, 1.0, format="%.0f%%", key="md_spec") / 100

    model_inputs = ModelInputs(
        nurse_model_sensitivity=nurse_sens,
        nurse_model_specificity=nurse_spec,
        md_model_sensitivity=md_sens,
        md_model_specificity=md_spec,
    )
    modeled = simulate_model_workflow(base_m, model_inputs)

    with st.expander("Show case flow", expanded=False):
        flow_col, econ_col = st.columns([1.35, 1])
        with flow_col:
            st.markdown("#### Case flow")
            st.dataframe(workflow_table(modeled), use_container_width=True, hide_index=True)
        with econ_col:
            st.markdown("#### Economics")
            st.dataframe(workflow_economics_table(modeled), use_container_width=True, hide_index=True)
        st.caption("Workflow visualization")
        st.graphviz_chart(model_workflow_graph(modeled), use_container_width=True)

    st.markdown("#### Model economics")
    st.markdown(model_economics_html(model_economics_table(modeled, base_m)), unsafe_allow_html=True)
