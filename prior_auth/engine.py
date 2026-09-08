from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class BaseInputs:
    initial_cases: float = 1000.0
    portal_approval_rate: float = 0.70
    rn_approval_rate: float = 0.60
    md_approval_rate: float = 0.50
    rn_cost: float = 20.0
    md_cost: float = 100.0
    savings_per_denial: float = 1000.0
    outsourced_price_per_case: float = 25.0


@dataclass(frozen=True)
class ModelInputs:
    nurse_model_sensitivity: float = 0.90
    nurse_model_specificity: float = 0.70
    md_model_sensitivity: float = 0.90
    md_model_specificity: float = 0.70


def _validate_probability(name: str, value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")


def _validate_base(x: BaseInputs) -> None:
    if x.initial_cases < 0:
        raise ValueError("initial_cases must be non-negative")
    for name in (
        "portal_approval_rate",
        "rn_approval_rate",
        "md_approval_rate",
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


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        if numerator == 0:
            return 0.0
        raise ValueError("cannot derive rate with zero denominator")
    return numerator / denominator


def _validate_derived_rate(name: str, value: float) -> float:
    tolerance = 1e-9
    if value < -tolerance or value > 1 + tolerance:
        raise ValueError(f"{name} implied by workflow assumptions must be between 0 and 1")
    return max(0.0, min(1.0, value))


def _baseline_observed(base: BaseInputs) -> Dict[str, float]:
    portal_approved = base.initial_cases * base.portal_approval_rate
    portal_remaining = base.initial_cases - portal_approved
    rn_approved = portal_remaining * base.rn_approval_rate
    md_queue = portal_remaining - rn_approved
    md_approved = md_queue * base.md_approval_rate
    final_denials = md_queue - md_approved
    initial_inappropriate = final_denials
    initial_appropriate = base.initial_cases - initial_inappropriate

    portal_specificity = _validate_derived_rate(
        "portal_specificity",
        _safe_div(portal_approved, initial_appropriate),
    )
    rn_queue_appropriate = initial_appropriate - portal_approved
    rn_queue_inappropriate = initial_inappropriate
    rn_specificity = _validate_derived_rate(
        "rn_specificity",
        _safe_div(rn_approved, rn_queue_appropriate),
    )

    return {
        "portal_approved": portal_approved,
        "portal_remaining": portal_remaining,
        "rn_approved": rn_approved,
        "md_queue": md_queue,
        "md_approved": md_approved,
        "final_denials": final_denials,
        "initial_inappropriate": initial_inappropriate,
        "initial_appropriate": initial_appropriate,
        "portal_sensitivity": 1.0,
        "portal_specificity": portal_specificity,
        "rn_queue_appropriate": rn_queue_appropriate,
        "rn_queue_inappropriate": rn_queue_inappropriate,
        "human_rn_sensitivity": 1.0,
        "human_rn_specificity": rn_specificity,
        "human_md_sensitivity": 1.0,
        "human_md_specificity": 1.0,
    }


def simulate_current_workflow(base: BaseInputs) -> Dict[str, object]:
    """Simulate the current portal -> RN -> human MD workflow.

    This is a deterministic observed-rate funnel. The final denial rate is
    the remainder after portal, RN, and MD approvals.
    """
    _validate_base(base)
    observed = _baseline_observed(base)

    portal_approved = observed["portal_approved"]
    rn_total = observed["portal_remaining"]
    rn_approved_total = observed["rn_approved"]
    md_total = observed["md_queue"]
    md_approved_total = observed["md_approved"]
    final_denials = observed["final_denials"]

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

    stages: List[Dict[str, float | str]] = [
        {"stage": "Initial cases", "cases": base.initial_cases},
        {"stage": "Portal approvals", "cases": portal_approved},
        {"stage": "RN reviews", "cases": rn_total},
        {"stage": "RN approvals", "cases": rn_approved_total},
        {"stage": "MD reviews", "cases": md_total},
        {"stage": "MD approvals", "cases": md_approved_total},
        {"stage": "Deemed inappropriate", "cases": final_denials},
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
        "initial_inappropriate": observed["initial_inappropriate"],
        "initial_appropriate": observed["initial_appropriate"],
        "portal_sensitivity": observed["portal_sensitivity"],
        "portal_specificity": observed["portal_specificity"],
        "human_rn_sensitivity": observed["human_rn_sensitivity"],
        "human_rn_specificity": observed["human_rn_specificity"],
        "human_md_sensitivity": observed["human_md_sensitivity"],
        "human_md_specificity": observed["human_md_specificity"],
    }


def simulate_model_workflow(base: BaseInputs, model: ModelInputs) -> Dict[str, object]:
    """Simulate portal -> RN model -> RN -> MD model -> human MD."""
    _validate_base(base)
    _validate_model(model)
    observed = _baseline_observed(base)

    initial_app = observed["initial_appropriate"]
    initial_inapp = observed["initial_inappropriate"]
    portal_approved = initial_app * observed["portal_specificity"]
    q_app = initial_app - portal_approved
    q_inapp = initial_inapp * observed["portal_sensitivity"]

    nm_autoapprove_app = q_app * model.nurse_model_specificity
    nm_falseapprove_inapp = q_inapp * (1 - model.nurse_model_sensitivity)
    rn_app = q_app - nm_autoapprove_app
    rn_inapp = q_inapp - nm_falseapprove_inapp
    rn_total = rn_app + rn_inapp

    rn_approve_app = rn_app * observed["human_rn_specificity"]
    rn_falseapprove_inapp = rn_inapp * (1 - observed["human_rn_sensitivity"])
    rn_to_md_app = rn_app - rn_approve_app
    rn_to_md_inapp = rn_inapp - rn_falseapprove_inapp

    mdq_app = rn_to_md_app
    mdq_inapp = rn_to_md_inapp
    mdq_total = mdq_app + mdq_inapp

    mm_autoapprove_app = mdq_app * model.md_model_specificity
    mm_falseapprove_inapp = mdq_inapp * (1 - model.md_model_sensitivity)
    mm_to_human_app = mdq_app - mm_autoapprove_app
    mm_to_human_inapp = mdq_inapp - mm_falseapprove_inapp

    human_md_total = mm_to_human_app + mm_to_human_inapp
    human_md_approved = mm_to_human_app * observed["human_md_specificity"]
    final_denials = mm_to_human_inapp * observed["human_md_sensitivity"]
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
        {"stage": "Deemed inappropriate", "cases": final_denials, "appropriate": 0.0, "inappropriate": final_denials},
    ]

    nurse_model_labor_saved = (
        nm_autoapprove_app * (base.rn_cost + (1 - observed["human_rn_specificity"]) * base.md_cost)
        + nm_falseapprove_inapp * (base.rn_cost + base.md_cost)
    )
    nurse_model_denial_value_lost = nm_falseapprove_inapp * base.savings_per_denial
    nurse_model_incremental_value = nurse_model_labor_saved - nurse_model_denial_value_lost

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
        "portal_queue_appropriate": q_app,
        "portal_queue_inappropriate": q_inapp,
        "nurse_model_autoapproved": nm_autoapprove_app + nm_falseapprove_inapp,
        "nurse_model_autoapproved_appropriate": nm_autoapprove_app,
        "nurse_model_falseapproved_inappropriate": nm_falseapprove_inapp,
        "nurse_model_labor_saved": nurse_model_labor_saved,
        "nurse_model_denial_value_lost": nurse_model_denial_value_lost,
        "nurse_model_incremental_value": nurse_model_incremental_value,
        "nurse_model_direct_md": 0.0,
        "rn_reviewed": rn_total,
        "rn_reviewed_appropriate": rn_app,
        "rn_reviewed_inappropriate": rn_inapp,
        "rn_approved": rn_approve_app,
        "rn_approved_appropriate": rn_approve_app,
        "rn_falseapproved_inappropriate": rn_falseapprove_inapp,
        "rn_to_md_appropriate": rn_to_md_app,
        "rn_to_md_inappropriate": rn_to_md_inapp,
        "md_queue": mdq_total,
        "md_queue_appropriate": mdq_app,
        "md_queue_inappropriate": mdq_inapp,
        "md_model_autoapproved": mm_autoapprove_app + mm_falseapprove_inapp,
        "md_model_autoapproved_appropriate": mm_autoapprove_app,
        "md_model_falseapproved_inappropriate": mm_falseapprove_inapp,
        "human_md_reviewed": human_md_total,
        "human_md_reviewed_appropriate": mm_to_human_app,
        "human_md_reviewed_inappropriate": mm_to_human_inapp,
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
        "initial_appropriate": initial_app,
        "portal_sensitivity": observed["portal_sensitivity"],
        "portal_specificity": observed["portal_specificity"],
        "human_rn_sensitivity": observed["human_rn_sensitivity"],
        "human_rn_specificity": observed["human_rn_specificity"],
        "human_md_sensitivity": observed["human_md_sensitivity"],
        "human_md_specificity": observed["human_md_specificity"],
        "md_model_human_reviews_avoided": md_model_human_reviews_avoided,
        "md_model_labor_saved": md_model_labor_saved,
        "md_model_denial_value_lost": md_model_denial_value_lost,
        "md_model_incremental_value": md_model_incremental_value,
        "md_model_breakeven_sensitivity": breakeven_sensitivity,
    }
