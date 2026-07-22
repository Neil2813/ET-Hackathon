import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import patch, MagicMock

from services.idempotency import idempotency_guard, mark_completed, derive_key

@pytest.fixture
def mock_firestore():
    with patch("services.idempotency._client") as mock_client:
        mock_db = MagicMock()
        mock_client.return_value = mock_db
        yield mock_db

def test_derive_key():
    key1 = derive_key("approve", "inc_123", "user_abc")
    key2 = derive_key("approve", "inc_123", "user_abc")
    assert key1 == key2
    assert len(key1) == 32

def test_idempotency_guard_allow_new(mock_firestore):
    # Mocking snap.exists to be False
    mock_doc = MagicMock()
    mock_doc.get.return_value.exists = False
    mock_firestore.collection.return_value.document.return_value = mock_doc

    result = idempotency_guard("test_key_new")
    
    assert result.is_allowed is True
    assert result.is_duplicate is False
    assert result.is_in_flight is False
    # Verify set was called to mark as IN_FLIGHT
    assert mock_doc.set.call_count == 1

def test_idempotency_guard_duplicate_completed(mock_firestore):
    # Mocking snap.exists to be True with status COMPLETED
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {"status": "COMPLETED", "response": {"result": "success"}}
    
    mock_doc = MagicMock()
    mock_doc.get.return_value = mock_snap
    mock_firestore.collection.return_value.document.return_value = mock_doc

    result = idempotency_guard("test_key_existing")
    
    assert result.is_duplicate is True
    assert result.is_allowed is False
    assert result.cached_response == {"result": "success"}

def test_idempotency_guard_in_flight(mock_firestore):
    # Mocking snap.exists to be True with status IN_FLIGHT
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {"status": "IN_FLIGHT"}
    
    mock_doc = MagicMock()
    mock_doc.get.return_value = mock_snap
    mock_firestore.collection.return_value.document.return_value = mock_doc

    result = idempotency_guard("test_key_inflight")
    
    assert result.is_in_flight is True
    assert result.is_allowed is False
