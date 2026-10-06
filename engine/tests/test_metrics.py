import json

from fastapi.testclient import TestClient

from aiotrade.api import app
from aiotrade.broker import BinanceSpot, PaperBroker
from aiotrade.live import LiveRunner
from aiotrade.metrics import MetricsPublisher, write_json_atomic

from .mock_binance import MockBinance


def test_ecriture_atomique(tmp_path):
    path = tmp_path / "m" / "engine.json"
    write_json_atomic(path, {"status": "ok"})
    write_json_atomic(path, {"status": "ok", "n": 2})
    assert json.loads(path.read_text()) == {"status": "ok", "n": 2}
    assert [p.name for p in path.parent.iterdir()] == ["engine.json"]  # aucun fichier temporaire restant


def test_publication_desactivee_sans_dossier(monkeypatch):
    monkeypatch.delenv("AIOTRADE_METRICS_DIR", raising=False)
    pub = MetricsPublisher("engine")
    assert not pub.enabled
    pub.update(status="ok")  # sans effet, sans erreur


def test_moteur_publie_ses_metriques(tmp_path, monkeypatch):
    monkeypatch.setenv("AIOTRADE_METRICS_DIR", str(tmp_path))
    with TestClient(app) as client:
        state = json.loads((tmp_path / "engine.json").read_text())
        assert state["status"] == "ok" and state["simulations_served"] == 0
        assert (tmp_path / "benchmark.json").exists()
        assert client.post("/api/simulate", json={"seed": 7, "shock": "flash_crash"}).status_code == 200
        state = json.loads((tmp_path / "engine.json").read_text())
        assert state["simulations_served"] == 1
        assert state["last_simulation"]["ledger_verified"] is True
    assert json.loads((tmp_path / "engine.json").read_text())["status"] == "stopped"


def test_executant_publie_sa_derniere_decision(tmp_path):
    data = BinanceSpot(base_url="http://127.0.0.1:9", transport=MockBinance(), environment="public")
    paper = PaperBroker(data, state_path=tmp_path / "state.json")
    pub = MetricsPublisher("trader", directory=tmp_path / "metrics")
    runner = LiveRunner(paper, history_bars=1_600, ledger_path=tmp_path / "d.jsonl", log=lambda m: None, metrics=pub)
    runner.run_forever(max_steps=1)
    state = json.loads((tmp_path / "metrics" / "trader.json").read_text())
    assert state["status"] == "ok" and state["broker_mode"] == "paper"
    assert state["decision"] in ("LONG", "CASH") and state["ledger_records"] == 1
    assert "api_key" not in json.dumps(state).lower()
