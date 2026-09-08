import pytest

from prior_auth.engine import BaseInputs, ModelInputs, simulate_current_workflow, simulate_model_workflow


def approx(x: float) -> float:
    return pytest.approx(x)


def test_workbook_baseline_reproduces_core_numbers_and_derived_rates():
    result = simulate_current_workflow(BaseInputs())
    assert result["initial_cases"] == approx(1000)
    assert result["portal_approved"] == approx(700)
    assert result["portal_queue"] == approx(300)
    assert result["rn_approved"] == approx(180)
    assert result["md_reviewed"] == approx(120)
    assert result["md_approved"] == approx(60)
    assert result["final_denials"] == approx(60)
    assert result["rn_review_cost"] == approx(6000)
    assert result["md_review_cost"] == approx(12000)
    assert result["review_cost"] == approx(18000)
    assert result["gross_savings"] == approx(60000)
    assert result["net_savings"] == approx(42000)
    assert result["initial_inappropriate"] == approx(60)
    assert result["initial_appropriate"] == approx(940)
    assert result["portal_specificity"] == approx(700 / 940)
    assert result["human_rn_sensitivity"] == approx(1)
    assert result["human_rn_specificity"] == approx(180 / 240)
    assert result["human_md_sensitivity"] == approx(1)
    assert result["human_md_specificity"] == approx(1)
    assert "missed_denials" not in result


def test_both_models_no_op_reproduces_baseline():
    result = simulate_model_workflow(
        BaseInputs(),
        ModelInputs(
            nurse_model_sensitivity=1.0,
            nurse_model_specificity=0.0,
            md_model_sensitivity=1.0,
            md_model_specificity=0.0,
        ),
    )
    assert result["nurse_model_autoapproved"] == approx(0)
    assert result["rn_reviewed"] == approx(300)
    assert result["rn_approved"] == approx(180)
    assert result["md_queue"] == approx(120)
    assert result["md_model_autoapproved"] == approx(0)
    assert result["human_md_reviewed"] == approx(120)
    assert result["human_md_approved"] == approx(60)
    assert result["final_denials"] == approx(60)
    assert result["missed_denials"] == approx(0)


def test_perfect_rn_model_no_op_md_model_conditions_human_rn_queue():
    base = BaseInputs()
    result = simulate_model_workflow(
        base,
        ModelInputs(
            nurse_model_sensitivity=1.0,
            nurse_model_specificity=1.0,
            md_model_sensitivity=1.0,
            md_model_specificity=0.0,
        ),
    )
    assert result["nurse_model_autoapproved_appropriate"] == approx(240)
    assert result["nurse_model_falseapproved_inappropriate"] == approx(0)
    assert result["nurse_model_autoapproved"] == approx(240)
    assert result["rn_reviewed_appropriate"] == approx(0)
    assert result["rn_reviewed_inappropriate"] == approx(60)
    assert result["rn_reviewed"] == approx(60)
    assert result["rn_approved"] == approx(0)
    assert result["md_queue"] == approx(60)
    assert result["md_model_autoapproved"] == approx(0)
    assert result["human_md_reviewed"] == approx(60)
    assert result["human_md_approved"] == approx(0)
    assert result["final_denials"] == approx(60)
    assert result["missed_denials"] == approx(0)
    assert result["nurse_model_labor_saved"] == approx(10800)
    assert result["nurse_model_denial_value_lost"] == approx(0)
    assert result["nurse_model_incremental_value"] == approx(10800)


def test_rn_model_false_approval_avoids_rn_and_md_review_but_loses_denial_value():
    base = BaseInputs()
    result = simulate_model_workflow(
        base,
        ModelInputs(
            nurse_model_sensitivity=1 - 1 / 60,
            nurse_model_specificity=0.0,
            md_model_sensitivity=1.0,
            md_model_specificity=0.0,
        ),
    )
    assert result["nurse_model_falseapproved_inappropriate"] == approx(1)
    assert result["nurse_model_autoapproved"] == approx(1)
    assert result["nurse_model_labor_saved"] == approx(120)
    assert result["nurse_model_denial_value_lost"] == approx(1000)
    assert result["nurse_model_incremental_value"] == approx(-880)


def test_no_op_rn_model_perfect_md_model_conditions_human_md_queue():
    base = BaseInputs()
    result = simulate_model_workflow(
        base,
        ModelInputs(
            nurse_model_sensitivity=1.0,
            nurse_model_specificity=0.0,
            md_model_sensitivity=1.0,
            md_model_specificity=1.0,
        ),
    )
    assert result["md_queue_appropriate"] == approx(60)
    assert result["md_queue_inappropriate"] == approx(60)
    assert result["md_model_autoapproved_appropriate"] == approx(60)
    assert result["md_model_falseapproved_inappropriate"] == approx(0)
    assert result["human_md_reviewed_appropriate"] == approx(0)
    assert result["human_md_reviewed_inappropriate"] == approx(60)
    assert result["human_md_reviewed"] == approx(60)
    assert result["human_md_approved"] == approx(0)
    assert result["final_denials"] == approx(60)
    assert result["missed_denials"] == approx(0)
    assert result["md_model_autoapproved"] == approx(60)
    assert result["md_model_labor_saved"] == approx(6000)
    assert result["md_model_denial_value_lost"] == approx(0)
    assert result["md_model_incremental_value"] == approx(6000)


def test_catastrophically_insensitive_md_model_loses_denial_value():
    result = simulate_model_workflow(
        BaseInputs(),
        ModelInputs(
            nurse_model_sensitivity=1.0,
            nurse_model_specificity=0.0,
            md_model_sensitivity=0.0,
            md_model_specificity=1.0,
        ),
    )
    assert result["md_queue_appropriate"] == approx(60)
    assert result["md_queue_inappropriate"] == approx(60)
    assert result["md_model_autoapproved"] == approx(120)
    assert result["human_md_reviewed"] == approx(0)
    assert result["final_denials"] == approx(0)
    assert result["missed_md_model"] == approx(60)
    assert result["md_model_labor_saved"] == approx(12000)
    assert result["md_model_denial_value_lost"] == approx(60000)
    assert result["md_model_incremental_value"] == approx(-48000)


def test_intermediate_models_condition_each_downstream_queue():
    base = BaseInputs()
    result = simulate_model_workflow(
        base,
        ModelInputs(
            nurse_model_sensitivity=0.8,
            nurse_model_specificity=0.9,
            md_model_sensitivity=0.9,
            md_model_specificity=0.8,
        ),
    )
    assert result["portal_queue_appropriate"] == approx(240)
    assert result["portal_queue_inappropriate"] == approx(60)
    assert result["nurse_model_autoapproved_appropriate"] == approx(216)
    assert result["nurse_model_falseapproved_inappropriate"] == approx(12)
    assert result["rn_reviewed_appropriate"] == approx(24)
    assert result["rn_reviewed_inappropriate"] == approx(48)
    assert result["rn_reviewed"] == approx(72)
    assert result["rn_approved"] == approx(18)
    assert result["md_queue_appropriate"] == approx(6)
    assert result["md_queue_inappropriate"] == approx(48)
    assert result["md_queue"] == approx(54)
    assert result["md_model_autoapproved_appropriate"] == approx(4.8)
    assert result["md_model_falseapproved_inappropriate"] == approx(4.8)
    assert result["human_md_reviewed_appropriate"] == approx(1.2)
    assert result["human_md_reviewed_inappropriate"] == approx(43.2)
    assert result["human_md_approved"] == approx(1.2)
    assert result["final_denials"] == approx(43.2)
    assert result["missed_nurse_model"] == approx(12)
    assert result["missed_md_model"] == approx(4.8)
    assert result["missed_denials"] == approx(16.8)
    assert result["nurse_model_autoapproved"] == approx(228)
    assert result["nurse_model_labor_saved"] == approx(11160)
    assert result["nurse_model_denial_value_lost"] == approx(12000)
    assert result["nurse_model_incremental_value"] == approx(-840)
    assert result["md_model_autoapproved"] == approx(9.6)
    assert result["md_model_labor_saved"] == approx(960)
    assert result["md_model_denial_value_lost"] == approx(4800)
    assert result["md_model_incremental_value"] == approx(-3840)


def test_model_specificity_zero_never_automates_appropriate_cases():
    result = simulate_model_workflow(
        BaseInputs(),
        ModelInputs(
            nurse_model_sensitivity=1.0,
            nurse_model_specificity=0.0,
            md_model_sensitivity=1.0,
            md_model_specificity=0.0,
        ),
    )
    assert result["nurse_model_autoapproved_appropriate"] == approx(0)
    assert result["nurse_model_falseapproved_inappropriate"] == approx(0)
    assert result["md_model_autoapproved_appropriate"] == approx(0)
    assert result["md_model_falseapproved_inappropriate"] == approx(0)
    assert result["nurse_model_autoapproved"] == approx(0)
    assert result["md_model_autoapproved"] == approx(0)


def test_model_sensitivity_one_never_misses_inappropriate_cases():
    result = simulate_model_workflow(
        BaseInputs(),
        ModelInputs(
            nurse_model_sensitivity=1.0,
            nurse_model_specificity=0.5,
            md_model_sensitivity=1.0,
            md_model_specificity=0.5,
        ),
    )
    assert result["nurse_model_falseapproved_inappropriate"] == approx(0)
    assert result["md_model_falseapproved_inappropriate"] == approx(0)
    assert result["missed_denials"] == approx(0)


def test_perfect_md_model_after_perfect_rn_model_has_no_avoidable_md_reviews():
    result = simulate_model_workflow(
        BaseInputs(),
        ModelInputs(
            nurse_model_sensitivity=1.0,
            nurse_model_specificity=1.0,
            md_model_sensitivity=1.0,
            md_model_specificity=1.0,
        ),
    )
    assert result["md_queue_appropriate"] == approx(0)
    assert result["md_queue_inappropriate"] == approx(60)
    assert result["md_model_autoapproved"] == approx(0)
    assert result["md_model_labor_saved"] == approx(0)
    assert result["md_model_denial_value_lost"] == approx(0)
    assert result["md_model_incremental_value"] == approx(0)


def test_model_review_cost_savings_match_baseline_review_cost_reduction():
    base = BaseInputs()
    baseline = simulate_current_workflow(base)
    result = simulate_model_workflow(
        base,
        ModelInputs(
            nurse_model_sensitivity=0.8,
            nurse_model_specificity=0.9,
            md_model_sensitivity=0.9,
            md_model_specificity=0.8,
        ),
    )
    total_model_review_cost_saved = result["nurse_model_labor_saved"] + result["md_model_labor_saved"]
    assert baseline["review_cost"] - result["review_cost"] == approx(total_model_review_cost_saved)


def test_cases_are_conserved_at_every_branch():
    result = simulate_model_workflow(
        BaseInputs(),
        ModelInputs(
            nurse_model_sensitivity=0.8,
            nurse_model_specificity=0.9,
            md_model_sensitivity=0.9,
            md_model_specificity=0.8,
        ),
    )
    assert result["initial_cases"] == approx(result["initial_appropriate"] + result["initial_inappropriate"])
    assert result["initial_cases"] == approx(result["portal_approved"] + result["portal_queue"])
    assert result["initial_appropriate"] == approx(result["portal_approved"] + result["portal_queue_appropriate"])
    assert result["initial_inappropriate"] == approx(result["portal_queue_inappropriate"])

    assert result["portal_queue"] == approx(result["nurse_model_autoapproved"] + result["rn_reviewed"])
    assert result["portal_queue_appropriate"] == approx(result["nurse_model_autoapproved_appropriate"] + result["rn_reviewed_appropriate"])
    assert result["portal_queue_inappropriate"] == approx(result["nurse_model_falseapproved_inappropriate"] + result["rn_reviewed_inappropriate"])

    assert result["rn_reviewed"] == approx(result["rn_approved"] + result["md_queue"])
    assert result["rn_reviewed_appropriate"] == approx(result["rn_approved_appropriate"] + result["rn_to_md_appropriate"])
    assert result["rn_reviewed_inappropriate"] == approx(result["rn_falseapproved_inappropriate"] + result["rn_to_md_inappropriate"])

    assert result["md_queue"] == approx(result["md_model_autoapproved"] + result["human_md_reviewed"])
    assert result["md_queue_appropriate"] == approx(result["md_model_autoapproved_appropriate"] + result["human_md_reviewed_appropriate"])
    assert result["md_queue_inappropriate"] == approx(result["md_model_falseapproved_inappropriate"] + result["human_md_reviewed_inappropriate"])

    assert result["human_md_reviewed"] == approx(result["human_md_approved"] + result["final_denials"])
    assert result["human_md_reviewed_appropriate"] == approx(result["human_md_approved"])
    assert result["human_md_reviewed_inappropriate"] == approx(result["final_denials"])

    final_exits = (
        result["portal_approved"]
        + result["nurse_model_autoapproved"]
        + result["rn_approved"]
        + result["md_model_autoapproved"]
        + result["human_md_approved"]
        + result["final_denials"]
    )
    assert final_exits == approx(result["initial_cases"])
