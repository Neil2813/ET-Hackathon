import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pdf.certificate import generate_workflow_audit_report_pdf

def test_pdf_generation_successful_report():
    mock_report = {
        "workflow_id": "TEST-1234-PROOF",
        "summary": {
            "response_time_seconds": 2.5,
            "exposure_usd": 15000000,
            "action_taken": "REROUTED"
        },
        "detect": {
            "event": {
                "title": "Disruption",
                "region": "Global",
                "timestamp": "2026-07-21T10:00:00Z",
                "severity": "CRITICAL"
            }
        },
        "assess": {
            "confidence": 0.88,
            "analysis": "Severe risk detected."
        },
        "decide": {
            "recommended_mode": "SEA",
            "route_comparison": [
                {"mode": "SEA", "lane": "Cape", "transit_days": 28, "cost_usd": 2500000}
            ]
        },
        "act": {
            "decision": "EXECUTE",
            "executed_at": "2026-07-21T10:05:00Z",
            "details": "Rerouted"
        },
        "audit": {
            "status": "COMPLETE",
            "timeline": "Detect -> Assess",
            "response_time_seconds": 2.5
        }
    }
    
    pdf_bytes = generate_workflow_audit_report_pdf(mock_report, requested_by="Test")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000  # A valid PDF should have a decent size

def test_pdf_generation_empty_payload():
    mock_report = {}
    
    # Should not throw any exceptions
    pdf_bytes = generate_workflow_audit_report_pdf(mock_report, requested_by="Test")
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
