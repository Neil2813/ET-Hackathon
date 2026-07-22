import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from services.governance_checkpoint import evaluate_checkpoint_triggers, HIGH_RISK_EXPOSURE_USD

def test_evaluate_checkpoint_no_triggers():
    incident = {
        "severity": "LOW",
        "total_exposure_usd": 10000,
        "gnn_confidence": 0.95,
        "affected_nodes": [
            {"single_source": False}
        ]
    }
    triggers = evaluate_checkpoint_triggers(incident)
    assert len(triggers) == 0

def test_evaluate_checkpoint_severity_trigger():
    incident = {
        "severity": "CRITICAL",
        "total_exposure_usd": 10000,
        "gnn_confidence": 0.95,
        "affected_nodes": []
    }
    triggers = evaluate_checkpoint_triggers(incident)
    assert len(triggers) == 1
    assert "Severity=CRITICAL" in triggers[0]

def test_evaluate_checkpoint_exposure_trigger():
    incident = {
        "severity": "MODERATE",
        "total_exposure_usd": HIGH_RISK_EXPOSURE_USD + 100,
        "gnn_confidence": 0.95,
        "affected_nodes": []
    }
    triggers = evaluate_checkpoint_triggers(incident)
    assert len(triggers) == 1
    assert "exceeds" in triggers[0]
    assert "threshold" in triggers[0]

def test_evaluate_checkpoint_confidence_trigger():
    incident = {
        "severity": "MODERATE",
        "total_exposure_usd": 10000,
        "gnn_confidence": 0.50, # below 0.70
        "affected_nodes": []
    }
    triggers = evaluate_checkpoint_triggers(incident)
    assert len(triggers) == 1
    assert "GNN confidence" in triggers[0]

def test_evaluate_checkpoint_sole_source_trigger():
    incident = {
        "severity": "MODERATE",
        "total_exposure_usd": 10000,
        "gnn_confidence": 0.95,
        "affected_nodes": [
            {"single_source": True}
        ]
    }
    triggers = evaluate_checkpoint_triggers(incident)
    assert len(triggers) == 1
    assert "Sole-source supplier affected" in triggers[0]

def test_evaluate_checkpoint_multiple_triggers():
    incident = {
        "severity": "CRITICAL",
        "total_exposure_usd": HIGH_RISK_EXPOSURE_USD + 1000,
        "gnn_confidence": 0.40,
        "affected_nodes": [
            {"single_source": True}
        ]
    }
    triggers = evaluate_checkpoint_triggers(incident)
    assert len(triggers) == 4
