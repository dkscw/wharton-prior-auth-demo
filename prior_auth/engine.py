from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class BaseInputs:
    initial_cases: float = 1000.0
    inappropriate_rate: float = 0.06
    portal_approval_rate: float = 0.70
    rn_approval_rate: float = 0.60
    md_approval_rate: float = 0.50
    rn_sensitivity: float = 1.00
    rn_specificity: float = 0.75
    rn_cost: float = 20.0
    md_cost: float = 100.0
    savings_per_denial: float = 1000.0
    outsourced_price_per_case: float = 25.0


@dataclass(frozen=True)
class ModelInputs:
    nurse_model_sensitivity: float = 0.95
    nurse_model_specificity: float = 0.95
    md_model_sensitivity: float = 0.95
    md_model_specificity: float = 0.95


def _validate_probability(name: str, value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")


def _validate_base(x: BaseInputs) -> None:
    if x.initial_cases < 0:
        raise ValueError("initial_cases must be non-negative")
    for name in (
        "inappropriate_rate",
        "portal_approval_rate",
        "rn_approval_rate",
        "md_approval_rate",
        "rn_sensitivity",
        "rn_specificity",
    ):
        _validate_probability(name, getattr(x, name))
    for name in ("rn_cost", "md_cost", "savings_per_denial", "outsourced_price_per_case"):
        if getattr(x, name) < 0:
            raise ValueError(f"{name} must be non-negative")


def _validate_model(x: ModelInputs) -> None:
    for name in (
        "nurse_model_sensitivity",
        "nurse_model_specificity",
        "md_model_sensitivity",
        "md_model_specificity",
    ):
        _validate_probability(name, getattr(x, name))


def _portal_split(base: BaseInputs) -> Dict[str, float]:
    """Safe-rules portal: approvals are assumed to come only from appropriate cases.

    This assumption reproduces the workbook baseline: 6% inappropriate overall,
    70% safely approved by portal, leaving 300 cases containing all 60 inappropriate cases.
    """
    inappropriate = base.initial_cases * base.inappropriate_rate
    appropriate = base.initial_cases - inappropriate
    requested_portal_approvals = base.initial_cases * base.portal_approval_rate
    portal_approved = min(requested_portal_approvals, appropriate)
    return {
        "initial_inappropriate": inappropriate,
        "initial_appropriate": appropriate,
        "portal_approved_appropriate": portal_approved,
        "portal_queue_appropriate": appropriate - portal_approved,
        "portal_queue_inappropriate": inappropriate,
    }


def simulate_current_workflow(base: BaseInputs) -> Dict[str, object]:
    """Simulate the current portal -> RN -> human MD workflow.

    This is a deterministic observed-rate funnel. The final denial rate is
    the remainder after portal, RN, and MD approvals.
    """
    _validate_base(base)

    portal_approved = base.initial_cases * base.portal_approval_rate
    rn_total = base.initial_cases - portal_approved
    rn_approved_total = rn_total * base.rn_approval_rate
    md_total = rn_total - rn_approved_total
    md_approved_total = md_total * base.md_approval_rate
    final_denials = md_total - md_approved_total

    rn_review_cost = rn_total * base.rn_cost
    md_review_cost = md_total * base.md_cost
    review_cost = rn_review_cost + md_review_cost
    gross_savings = final_denials * base.savings_per_denial
    net_savings = gross_savings - review_cost
    roi = gross_savings / review_cost if review_cost else float("inf")
    client_cost = base.initial_cases * base.outsourced_price_per_case
    client_roi = gross_savings / client_cost if client_cost else float("inf")
    vendor_profit = client_cost - review_cost
    vendor_margin = vendor_profit / client_cost if client_cost else float("nan")
    client_cost = base.initial_cases * base.outsourced_price_per_case
    client_roi = gross_savings / client_cost if client_cost else float("inf")
    vendor_profit = client_cost - review_cost
    vendor_margin = vendor_profit / client_cost if client_cost else float("nan")

    stages: List[Dict[str, float | str]] = [
        {"stage": "Initial cases", "cases": base.initial_cases},
        {"stage": "Portal approvals", "cases": portal_approved},
        {"stage": "RN reviews", "cases": rn_total},
        {"stage": "RN approvals", "cases": rn_approved_total},
        {"stage": "MD reviews", "cases": md_total},
        {"stage": "MD approvals", "cases": md_approved_total},
        {"stage": "Detected inappropriate / denied", "cases": final_denials},
    ]

    return {
        "stages": stages,
        "initial_cases": base.initial_cases,
        "portal_approved": portal_approved,
        "portal_queue": rn_total,
        "rn_approved": rn_approved_total,
        "md_reviewed": md_total,
        "md_approved": md_approved_total,
        "final_denials": final_denials,
        "review_cost": review_cost,
        "rn_review_cost": rn_review_cost,
        "md_review_cost": md_review_cost,
        "gross_savings": gross_savings,
        "net_savings": net_savings,
        "roi": roi,
        "client_cost": client_cost,
        "client_roi": client_roi,
        "vendor_profit": vendor_profit,
        "vendor_margin": vendor_margin,
    }


def simulate_model_workflow(base: BaseInputs, model: ModelInputs) -> Dict[str, object]:
    """Simulate portal -> RN model -> RN -> MD model -> human MD."""
    _validate_base(base)
    _validate_model(model)

    baseline = simulate_current_workflow(base)
    initial_inapp = baseline["final_denials"]
    initial_app = base.initial_cases - initial_inapp
    portal_approved = min(baseline["portal_approved"], initial_app)
    q_app = initial_app - portal_approved
    q_inapp = initial_inapp

    nm_autoapprove_app = q_app * model.nurse_model_specificity
    nm_falseapprove_inapp = q_inapp * (1 - model.nurse_model_sensitivity)
    rn_app = q_app - nm_autoapprove_app
    rn_inapp = q_inapp - nm_falseapprove_inapp
    rn_total = rn_app + rn_inapp

    rn_requested_approvals = rn_total * base.rn_approval_rate
    rn_approve_app = min(rn_requested_approvals, rn_app)
    rn_falseapprove_inapp = 0.0
    rn_to_md_app = rn_app - rn_approve_app
    rn_to_md_inapp = rn_inapp

    mdq_app = rn_to_md_app
    mdq_inapp = rn_to_md_inapp
    mdq_total = mdq_app + mdq_inapp

    mm_autoapprove_app = mdq_app * model.md_model_specificity
    mm_falseapprove_inapp = mdq_inapp * (1 - model.md_model_sensitivity)
    mm_to_human_app = mdq_app - mm_autoapprove_app
    mm_to_human_inapp = mdq_inapp - mm_falseapprove_inapp

    human_md_total = mm_to_human_app + mm_to_human_inapp
    md_requested_approvals = human_md_total * base.md_approval_rate
    human_md_approved = min(md_requested_approvals, mm_to_human_app)
    final_denials = human_md_total - human_md_approved
    missed_nurse_model = nm_falseapprove_inapp
    missed_rn = rn_falseapprove_inapp
    missed_md_model = mm_falseapprove_inapp
    missed_total = missed_nurse_model + missed_rn + missed_md_model

    rn_review_cost = rn_total * base.rn_cost
    md_review_cost = human_md_total * base.md_cost
    review_cost = rn_review_cost + md_review_cost
    gross_savings = final_denials * base.savings_per_denial
    net_savings = gross_savings - review_cost
    roi = gross_savings / review_cost if review_cost else float("inf")
    client_cost = base.initial_cases * base.outsourced_price_per_case
    client_roi = gross_savings / client_cost if client_cost else float("inf")
    vendor_profit = client_cost - review_cost
    vendor_margin = vendor_profit / client_cost if client_cost else float("nan")

    stages: List[Dict[str, float | str]] = [
        {"stage": "Initial cases", "cases": base.initial_cases, "appropriate": initial_app, "inappropriate": initial_inapp},
        {"stage": "Portal approves", "cases": portal_approved, "appropriate": portal_approved, "inappropriate": 0.0},
        {"stage": "RN model reviews", "cases": q_app + q_inapp, "appropriate": q_app, "inappropriate": q_inapp},
        {"stage": "Nurse model auto-approves", "cases": nm_autoapprove_app + nm_falseapprove_inapp, "appropriate": nm_autoapprove_app, "inappropriate": nm_falseapprove_inapp},
        {"stage": "RN reviews", "cases": rn_total, "appropriate": rn_app, "inappropriate": rn_inapp},
        {"stage": "RN approves", "cases": rn_approve_app, "appropriate": rn_approve_app, "inappropriate": 0.0},
        {"stage": "MD model reviews", "cases": mdq_total, "appropriate": mdq_app, "inappropriate": mdq_inapp},
        {"stage": "MD model auto-approves", "cases": mm_autoapprove_app + mm_falseapprove_inapp, "appropriate": mm_autoapprove_app, "inappropriate": mm_falseapprove_inapp},
        {"stage": "Human MD reviews", "cases": human_md_total, "appropriate": mm_to_human_app, "inappropriate": mm_to_human_inapp},
        {"stage": "MD approves", "cases": human_md_approved, "appropriate": human_md_approved, "inappropriate": 0.0},
        {"stage": "Final denials", "cases": final_denials, "appropriate": mm_to_human_app - human_md_approved, "inappropriate": mm_to_human_inapp},
    ]

    # Value decomposition for the MD model specifically, relative to sending its covered cases to human MD.
    md_model_human_reviews_avoided = mm_autoapprove_app + mm_falseapprove_inapp
    md_model_labor_saved = md_model_human_reviews_avoided * base.md_cost
    md_model_denial_value_lost = mm_falseapprove_inapp * base.savings_per_denial
    md_model_incremental_value = md_model_labor_saved - md_model_denial_value_lost

    denom = mdq_inapp * max(base.savings_per_denial - base.md_cost, 0)
    if denom <= 0:
        breakeven_sensitivity = 0.0
    else:
        allowable_fn = (base.md_cost * model.md_model_specificity * mdq_app) / denom
        breakeven_sensitivity = max(0.0, min(1.0, 1.0 - allowable_fn))

    return {
        "stages": stages,
        "initial_cases": base.initial_cases,
        "portal_approved": portal_approved,
        "portal_queue": q_app + q_inapp,
        "nurse_model_autoapproved": nm_autoapprove_app + nm_falseapprove_inapp,
        "nurse_model_direct_md": 0.0,
        "rn_reviewed": rn_total,
        "rn_approved": rn_approve_app,
        "md_queue": mdq_total,
        "md_model_autoapproved": mm_autoapprove_app + mm_falseapprove_inapp,
        "human_md_reviewed": human_md_total,
        "human_md_approved": human_md_approved,
        "final_denials": final_denials,
        "missed_nurse_model": missed_nurse_model,
        "missed_rn": missed_rn,
        "missed_md_model": missed_md_model,
        "missed_denials": missed_total,
        "review_cost": review_cost,
        "rn_review_cost": rn_review_cost,
        "md_review_cost": md_review_cost,
        "gross_savings": gross_savings,
        "net_savings": net_savings,
        "roi": roi,
        "client_cost": client_cost,
        "client_roi": client_roi,
        "vendor_profit": vendor_profit,
        "vendor_margin": vendor_margin,
        "initial_inappropriate": initial_inapp,
        "md_model_human_reviews_avoided": md_model_human_reviews_avoided,
        "md_model_labor_saved": md_model_labor_saved,
        "md_model_denial_value_lost": md_model_denial_value_lost,
        "md_model_incremental_value": md_model_incremental_value,
        "md_model_breakeven_sensitivity": breakeven_sensitivity,
    }
