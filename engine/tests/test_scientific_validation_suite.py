"""
engine/tests/test_scientific_validation_suite.py
Tests unitarios para la Suite de Validación Científica Anti-Overfitting (SOP-146).
"""

from engine.backtest.scientific_validation_suite import (
    compute_daily_clustered_statistics,
    compute_sample_statistics,
    evaluate_ablation_study,
    evaluate_parameter_sensitivity_grid,
    evaluate_survivorship_bias_benchmark,
    evaluate_temporal_out_of_sample,
    run_scientific_validation_suite,
)


def _build_synthetic_trades() -> list[dict]:
    base_pattern = [
        {"outcome_r": 1.35, "close_reason": "PROTECTED_EXIT", "streak_mult": 1.0, "sizing_mult": 1.15},
        {"outcome_r": -0.65, "close_reason": "SOP25_EARLY_INVALIDATION", "streak_mult": 1.0, "sizing_mult": 1.0},
        {"outcome_r": 2.10, "close_reason": "TP2_HIT", "streak_mult": 1.0, "sizing_mult": 1.25},
        {"outcome_r": -1.00, "close_reason": "SL_HIT", "streak_mult": 0.85, "sizing_mult": 0.85},
        {"outcome_r": 1.20, "close_reason": "TP1_HIT", "streak_mult": 0.65, "sizing_mult": 1.0},
    ]
    trades = []
    for idx in range(30):
        item = dict(base_pattern[idx % len(base_pattern)])
        item["symbol"] = "BTCUSDT"
        item["entry_time"] = f"2026-03-{(idx // 2) + 1:02d} {(idx % 2) * 4 + 10:02d}:00:00"
        trades.append(item)
    return trades


def test_compute_sample_statistics_confidence_intervals():
    returns = [1.5, -0.65, 2.0, -1.0, 1.2, 0.0, 1.8, -0.65, 2.4, -1.0]
    stats = compute_sample_statistics(returns)
    assert stats["trades_count"] == 10
    assert stats["profit_factor"] > 1.5
    assert stats["standard_error_r"] > 0.0
    assert stats["ci95_low_r"] < stats["expectancy_r"] < stats["ci95_high_r"]
    assert stats["max_drawdown_r"] >= 0.65


def test_evaluate_temporal_out_of_sample_split_and_folds():
    trades = _build_synthetic_trades()
    oos = evaluate_temporal_out_of_sample(trades, train_ratio=0.60)
    assert oos["in_sample_60pct"]["flat_1r"]["trades_count"] == 18
    assert oos["out_of_sample_40pct"]["flat_1r"]["trades_count"] == 12
    assert len(oos["rolling_3_folds"]) == 3
    assert oos["out_of_sample_40pct"]["flat_1r"]["profit_factor"] > 1.0
    assert oos["daily_clustered_flat_1r"]["active_days_count"] == 15
    assert oos["daily_clustered_friction_sop119_1r"]["daily_se_r"] > 0.0


def test_evaluate_parameter_sensitivity_and_ablation():
    trades = _build_synthetic_trades()
    sens = evaluate_parameter_sensitivity_grid(trades)
    assert len(sens["grid"]) == 5
    assert 0.0 <= sens["parameter_stability_score"] <= 1.0
    assert sens["min_profit_factor_across_grid"] > 1.0

    ablation = evaluate_ablation_study(trades, train_ratio=0.60)
    assert len(ablation) == 4
    assert ablation[0]["in_sample_60pct"]["trades_count"] == 18
    assert ablation[0]["out_of_sample_40pct"]["trades_count"] == 12


def test_survivorship_bias_and_full_suite_execution(tmp_path):
    trades = _build_synthetic_trades()
    surv = evaluate_survivorship_bias_benchmark(trades, rejected_pair_gate_count=90)
    assert surv["unpruned_15_assets_flat_1r"]["trades_count"] > len(trades)
    assert "methodology_note" in surv

    out_file = tmp_path / "sci_report.json"
    report = run_scientific_validation_suite(output_path=str(out_file))
    assert out_file.exists()
    assert report["sample_size_trades"] > 100
    assert report["temporal_out_of_sample_audit"]["out_of_sample_40pct"]["flat_1r"]["profit_factor"] > 1.2
