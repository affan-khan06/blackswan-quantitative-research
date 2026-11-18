from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_and_universe_endpoints():
    with TestClient(app) as client:
        r_health = client.get("/api/health")
        assert r_health.status_code == 200
        assert r_health.json()["status"] == "ok"

        r_univ = client.get("/api/market-data/universe")
        assert r_univ.status_code == 200
        symbols = [a["symbol"] for a in r_univ.json()["assets"]]
        assert "NIFTY50" in symbols
        assert "RELIANCE" in symbols


def test_portfolio_validation_rejects_bad_weights_and_vix():
    with TestClient(app) as client:
        # Weights do not sum to 1.0
        bad_weights = {
            "allocations": [
                {"symbol": "NIFTY50", "weight": 0.5},
                {"symbol": "RELIANCE", "weight": 0.3},
            ],
            "start_date": "2022-01-01",
        }
        r1 = client.post("/api/portfolio/analyze", json=bad_weights)
        assert r1.status_code == 422

        # INDIAVIX cannot hold portfolio weight
        bad_vix = {
            "allocations": [
                {"symbol": "INDIAVIX", "weight": 1.0},
            ],
            "start_date": "2022-01-01",
        }
        r2 = client.post("/api/portfolio/analyze", json=bad_vix)
        assert r2.status_code == 422


def test_end_to_end_real_nse_simulation_and_pdf_report():
    payload = {
        "name": "Integration Test NSE Balanced Portfolio",
        "allocations": [
            {"symbol": "NIFTY50", "weight": 0.40},
            {"symbol": "RELIANCE", "weight": 0.25},
            {"symbol": "HDFCBANK", "weight": 0.20},
            {"symbol": "INFY", "weight": 0.15},
        ],
        "start_date": "2020-01-01",
        "initial_capital": 1000000.0,
        "simulation_method": "regime_switching_mc",
        "n_paths": 500,
        "horizon_days": 21,
        "confidence_level": 0.95,
        "random_seed": 42,
        "run_method_comparison": True,
    }
    with TestClient(app) as client:
        r_sim = client.post("/api/simulations/run-sync", json=payload)
        assert r_sim.status_code == 200, r_sim.text
        data = r_sim.json()
        exp_id = data["id"]
        assert data["status"] == "COMPLETED"
        assert data["results"]["risk_metrics"]["euler_risk_attribution"]["reconciled"] is True
        assert len(data["results"]["method_comparison"]) == 4

        # Verify PDF report generation returns genuine PDF bytes
        r_pdf = client.get(f"/api/reports/{exp_id}/pdf")
        assert r_pdf.status_code == 200
        assert r_pdf.headers["content-type"] == "application/pdf"
        assert r_pdf.content.startswith(b"%PDF")

        # Cleanup test experiment so DB stays clean on initial launch
        r_del = client.delete(f"/api/experiments/{exp_id}")
        assert r_del.status_code == 200
