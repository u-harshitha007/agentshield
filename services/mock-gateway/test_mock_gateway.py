"""Quick test script for mock gateway endpoints."""
import requests
import time

BASE_URL = "http://localhost:8001"


def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    resp = requests.get(f"{BASE_URL}/health")
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.json()}")
    assert resp.status_code == 200
    print("✅ Health check passed\n")


def test_lease():
    """Test lease issuance."""
    print("Testing lease issuance...")
    payload = {
        "task_id": "task-test-123",
        "requested_by": "test-user",
        "policy_id": "pol-test-001",
    }
    resp = requests.post(f"{BASE_URL}/v1/tasks", json=payload)
    print(f"  Status: {resp.status_code}")
    data = resp.json()
    print(f"  Lease ID: {data['lease_id']}")
    print(f"  Signature: {data['signature']}")
    assert resp.status_code == 200
    assert "lease_id" in data
    print("✅ Lease issuance passed\n")
    return data["lease_id"]


def test_tool_call_allow():
    """Test tool call with ALLOW decision."""
    print("Testing tool call (ALLOW)...")
    payload = {
        "call_id": "call-123",
        "task_id": "task-123",
        "lease_id": "lease-123",
        "tool_name": "read_file",
        "tool_args": {"path": "/etc/config"},
        "context": {},
    }
    resp = requests.post(f"{BASE_URL}/v1/tool-calls", json=payload)
    print(f"  Status: {resp.status_code}")
    data = resp.json()
    print(f"  Decision: {data['decision']}")
    print(f"  Message: {data['message']}")
    assert resp.status_code == 200
    assert data["decision"] == "ALLOW"
    print("✅ ALLOW decision passed\n")


def test_tool_call_hold():
    """Test tool call with HOLD decision (high amount)."""
    print("Testing tool call (HOLD)...")
    payload = {
        "call_id": "call-456",
        "task_id": "task-456",
        "lease_id": "lease-456",
        "tool_name": "transfer_funds",  # Not in HIGH_RISK_TOOLS
        "tool_args": {"amount": 500000, "beneficiary": "ABC Corp"},
        "context": {},
    }
    resp = requests.post(f"{BASE_URL}/v1/tool-calls", json=payload)
    print(f"  Status: {resp.status_code}")
    data = resp.json()
    print(f"  Decision: {data['decision']}")
    print(f"  Message: {data['message']}")
    print(f"  Approval ID: {data['approval_id']}")
    assert resp.status_code == 200
    assert data["decision"] == "HOLD"
    assert data["approval_id"] is not None
    print("✅ HOLD decision passed\n")
    return data["approval_id"]


def test_approval_polling(approval_id: str):
    """Test approval status polling."""
    print(f"Testing approval polling for {approval_id}...")
    
    # First poll: should be pending
    resp = requests.get(f"{BASE_URL}/v1/approvals/{approval_id}")
    print(f"  Status: {resp.status_code}")
    data = resp.json()
    print(f"  Approval Status: {data['status']}")
    assert resp.status_code == 200
    assert data["status"] == "pending"
    
    # Wait for auto-approval (10 seconds)
    print("  Waiting 11 seconds for auto-approval...")
    time.sleep(11)
    
    # Second poll: should be approved
    resp = requests.get(f"{BASE_URL}/v1/approvals/{approval_id}")
    data = resp.json()
    print(f"  Approval Status: {data['status']}")
    print(f"  Decision: {data['decision']}")
    assert data["status"] == "approved"
    assert data["decision"] == "ALLOW"
    print("✅ Approval polling passed\n")


def test_event():
    """Test event reception."""
    print("Testing event reception...")
    payload = {
        "event_type": "task.created",
        "payload": {"task_id": "task-789", "goal": "Test goal"},
    }
    resp = requests.post(f"{BASE_URL}/v1/events", json=payload)
    print(f"  Status: {resp.status_code}")
    data = resp.json()
    print(f"  Response: {data}")
    assert resp.status_code == 200
    print("✅ Event reception passed\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Mock Gateway Test Suite")
    print("=" * 60 + "\n")
    
    try:
        test_health()
        test_lease()
        test_tool_call_allow()
        approval_id = test_tool_call_hold()
        test_approval_polling(approval_id)
        test_event()
        
        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to mock gateway.")
        print("   Make sure it's running: python app/main.py")
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
