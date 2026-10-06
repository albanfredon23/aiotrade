"""Audit : les coûts réels (spread bid/ask, slippage, commissions, impact) entrent
dans l'arbre d'admissibilité du SCG. Sans eux, le backtest serait invalide."""
import numpy as np
import pytest

from aiotrade.copilot import Action, Copilot, CopilotConfig, MarketQuote
from aiotrade.execution import ExecutionConfig, ExecutionModel
from aiotrade.scg import SphericalConstraintGraph
from aiotrade.sizing import SizingConfig
from aiotrade.tap import TrajectoryBundle

from .test_copilot import NOMINAL, env, reading  # noqa: F401  (fixture partagée)

PRICE, SPREAD = 1.0850, 0.0004  # EURUSD, 4 pips de spread
SIGMA, ADV, NOTIONAL = 0.001, 5e8, 100_000.0


def bundle_limite() -> TrajectoryBundle:
    """11 trajectoires gagnantes, 5 perdantes à −0,98 % : juste sous la perte maximale de 1 %."""
    paths = [[0.002]] * 11 + [[-0.0098]] * 5
    return TrajectoryBundle(np.array(paths), "audit")


def test_cout_aller_retour_contient_spread_et_slippage():
    model = ExecutionModel(ExecutionConfig(slippage_bps=0.5))
    leg = model.cost(NOTIONAL, PRICE, SPREAD, SIGMA, ADV)
    assert leg.spread == pytest.approx(0.5 * SPREAD / PRICE)  # demi-spread payé à chaque exécution
    assert leg.slippage == pytest.approx(0.5e-4)
    rt = model.round_trip(NOTIONAL, PRICE, SPREAD, SIGMA, ADV)
    assert rt == pytest.approx(2 * (leg.spread + leg.slippage + leg.impact + leg.commission))
    # Plus de spread ou plus de slippage : coût strictement plus élevé.
    assert model.round_trip(NOTIONAL, PRICE, 2 * SPREAD, SIGMA, ADV) > rt
    assert ExecutionModel(ExecutionConfig(slippage_bps=2.0)).round_trip(NOTIONAL, PRICE, SPREAD, SIGMA, ADV) > rt


def test_admissible_sans_frictions_rejete_avec_frictions():
    scg = SphericalConstraintGraph()
    cost = ExecutionModel().round_trip(NOTIONAL, PRICE, SPREAD, SIGMA, ADV)
    assert cost > 0.0002  # le spread seul coûte déjà ~3,7 points de base aller-retour

    sans = scg.evaluate(bundle_limite(), 1.0, 1.0, 1.0, stop_distance=0.5, cost_per_unit=0.0)
    avec = scg.evaluate(bundle_limite(), 1.0, 1.0, 1.0, stop_distance=0.5, cost_per_unit=cost)

    assert sans.admitted and sans.admissibility_ratio == 1.0
    assert not avec.admitted
    assert avec.rejections["loss_violation"] == 5  # les frictions font franchir la perte maximale
    assert avec.admissibility_ratio == pytest.approx(11 / 16)
    assert avec.expected_net == pytest.approx(sans.expected_net - cost)


def test_slippage_seul_suffit_a_faire_basculer():
    scg = SphericalConstraintGraph()
    cout_sans_spread = ExecutionModel(ExecutionConfig(slippage_bps=1.5)).round_trip(NOTIONAL, PRICE, 0.0, SIGMA, ADV)
    report = scg.evaluate(bundle_limite(), 1.0, 1.0, 1.0, stop_distance=0.5, cost_per_unit=cout_sans_spread)
    assert not report.admitted and report.rejections["loss_violation"] == 5


def test_frictions_deduites_a_l_entree_et_a_la_sortie():
    scg = SphericalConstraintGraph()
    curves = scg.equity_paths(TrajectoryBundle(np.zeros((1, 3)), "plat"), 1.0, 0.5, cost_per_unit=0.0004)
    assert curves[0, 0] == pytest.approx(1.0 - 0.0002)  # demi-coût dès l'entrée
    assert curves[0, -1] == pytest.approx(1.0 - 0.0004)  # coût complet à la sortie


def test_copilote_transmet_le_spread_cote_au_garde_fou(env):  # noqa: F811
    m, s, f = env
    t = 2_900
    cp = Copilot(f, CopilotConfig(sizing=SizingConfig(confidence_z=0.0)), m.symbol)
    ctx = s.context(t)

    def decide(spread: float):
        quote = MarketQuote(float(m.close[t]), spread, float(s.avg_volume[t]))
        return cp.decide(ctx, quote, reading(), NOMINAL, 100_000.0, 100_000.0, np.random.default_rng(1))

    normal = decide(float(m.spread[t]))
    large = decide(float(m.spread[t]) * 400)
    assert normal.action != Action.CASH
    assert large.action == Action.CASH  # même faisceau, même signal : seules les frictions changent
    assert large.record["round_trip_cost_bps"] > normal.record["round_trip_cost_bps"]
