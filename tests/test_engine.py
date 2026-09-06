from prior_auth.engine import BaseInputs, ModelInputs, simulate_current_workflow, simulate_model_workflow


def test_workbook_baseline_reproduces_core_numbers():
    result = simulate_current_workflow(BaseInputs())
    assert round(result["initial_cases"], 8) == 1000
    assert round(result["portal_approved"], 8) == 700
    assert round(result["portal_queue"], 8) == 300
    assert round(result["rn_approved"], 8) == 180
    assert round(result["md_reviewed"], 8) == 120
    assert round(result["md_approved"], 8) == 60
    assert round(result["final_denials"], 8) == 60
    assert round(result["rn_review_cost"], 8) == 6000
    assert round(result["md_review_cost"], 8) == 12000
    assert round(result["review_cost"], 8) == 18000
    assert round(result["gross_savings"], 8) == 60000
    assert round(result["net_savings"], 8) == 42000
    assert "missed_denials" not in result


def test_perfect_models_do_not_miss_denials():
    base = BaseInputs()
    model = ModelInputs(
        nurse_model_sensitivity=1.0,
        nurse_model_specificity=1.0,
        md_model_sensitivity=1.0,
        md_model_specificity=1.0,
    )
    result = simulate_model_workflow(base, model)
    assert round(result["missed_denials"], 8) == 0
    assert round(result["final_denials"], 8) == 60


def test_md_false_negatives_lose_denial_value():
    base = BaseInputs()
    model = ModelInputs(
        nurse_model_sensitivity=1.0,
        nurse_model_specificity=1.0,
        md_model_sensitivity=0.9,
        md_model_specificity=1.0,
    )
    result = simulate_model_workflow(base, model)
    assert result["missed_md_model"] > 0
    assert result["md_model_denial_value_lost"] == result["missed_md_model"] * base.savings_per_denial
