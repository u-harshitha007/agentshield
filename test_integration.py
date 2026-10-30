"""Integration test: Agent Runtime + Mock Gateway.

This script tests the actual communication between Agent and Mock Gateway.
"""
import requests
import time
import json
from datetime import datetime

AGENT_URL = "http://localhost:8003"
GATEWAY_URL = "http://localhost:8001"

def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def check_services():
    """Verify both services are running."""
    print_section("STEP 1: Verify Services")
    
    # Check Mock Gateway
    try:
        resp = requests.get(f"{GATEWAY_URL}/health", timeout=5)
        print(f"✅ Mock Gateway: {resp.json()}")
    except Exception as e:
        print(f"❌ Mock Gateway not running: {e}")
        return False
    
    # Check Agent Runtime
    try:
        resp = requests.get(f"{AGENT_URL}/v1/health", timeout=5)
        print(f"✅ Agent Runtime: {resp.json()}")
    except Exception as e:
        print(f"❌ Agent Runtime not running: {e}")
        return False
    
    return True


def create_task(goal: str, task_id: str = None):
    """Create a task via Agent API."""
    print_section(f"STEP 2: Create Task - {goal}")
    
    payload = {
        "goal": goal,
        "context": {
            "supplier_id": "SUP-12345",
            "user_id": "demo-user",
        },
        "policy_id": "pol-demo-001",
    }
    
    if task_id:
        payload["task_id"] = task_id
    
    print(f"📤 POST {AGENT_URL}/v1/tasks")
    print(f"   Goal: {goal}")
    
    resp = requests.post(f"{AGENT_URL}/v1/tasks", json=payload, timeout=10)
    
    print(f"\n📥 Response: {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, indent=2))
    
    return data.get("task_id")


def get_task_status(task_id: str):
    """Get task status."""
    resp = requests.get(f"{AGENT_URL}/v1/tasks/{task_id}", timeout=5)
    return resp.json()


def get_task_trace(task_id: str):
    """Get task execution trace."""
    resp = requests.get(f"{AGENT_URL}/v1/tasks/{task_id}/trace", timeout=5)
    return resp.json()


def poll_task(task_id: str, max_wait: int = 30):
    """Poll task until completion or timeout."""
    print_section("STEP 3: Monitor Task Execution")
    
    print(f"📊 Polling task {task_id}...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        data = get_task_status(task_id)
        status = data.get("status")
        
        print(f"   [{int(time.time() - start_time)}s] Status: {status}")
        
        if status in ["COMPLETED", "FAILED"]:
            print(f"\n✅ Task reached terminal state: {status}")
            print(json.dumps(data, indent=2))
            return data
        
        time.sleep(2)
    
    print(f"\n⚠️ Task did not complete within {max_wait}s")
    return get_task_status(task_id)


def verify_gateway_calls(task_id: str):
    """Verify gateway was actually called."""
    print_section("STEP 4: Verify Gateway Integration")
    
    trace = get_task_trace(task_id)
    
    print(f"📋 Task Trace for {task_id}:")
    print(json.dumps(trace, indent=2))
    
    # Check for tool calls in trace
    observations = trace.get("observations", [])
    tool_calls = [obs for obs in observations if obs.get("type") == "tool_call"]
    
    print(f"\n🔧 Tool Calls: {len(tool_calls)}")
    for idx, call in enumerate(tool_calls, 1):
        print(f"\n   Call {idx}:")
        print(f"      Tool: {call.get('tool_name')}")
        print(f"      Decision: {call.get('decision')}")
        print(f"      Reason: {call.get('reason_code')}")
        
        if call.get("decision") == "DENY":
            print(f"      ⚠️ DENIED - Safe alternatives: {call.get('safe_alternatives')}")
        elif call.get("decision") == "HOLD":
            print(f"      ⏸️ HOLD - Approval ID: {call.get('approval_id')}")
    
    if not tool_calls:
        print("   ⚠️ No tool calls found - Gateway may not have been invoked!")
    
    return tool_calls


def test_scenario_allow():
    """Test ALLOW scenario - simple read operation."""
    print("\n" + "🟢" * 35)
    print("TEST SCENARIO 1: ALLOW (Low-Risk Operation)")
    print("🟢" * 35)
    
    task_id = create_task("Read supplier details for SUP-12345", "task-allow-001")
    if not task_id:
        print("❌ Failed to create task")
        return False
    
    result = poll_task(task_id, max_wait=60)
    tool_calls = verify_gateway_calls(task_id)
    
    # Check if any tool was ALLOWED
    allowed = any(call.get("decision") == "ALLOW" for call in tool_calls)
    
    if allowed:
        print("\n✅ ALLOW scenario verified - tool call was permitted")
        return True
    else:
        print("\n⚠️ No ALLOW decisions found")
        return False


def test_scenario_deny():
    """Test DENY scenario - high-risk tool."""
    print("\n" + "🔴" * 35)
    print("TEST SCENARIO 2: DENY (High-Risk Tool)")
    print("🔴" * 35)
    
    # This goal should trigger execute_payment tool (in HIGH_RISK_TOOLS)
    task_id = create_task(
        "Execute payment of ₹5,00,000 to supplier SUP-12345",
        "task-deny-001"
    )
    if not task_id:
        print("❌ Failed to create task")
        return False
    
    result = poll_task(task_id, max_wait=60)
    tool_calls = verify_gateway_calls(task_id)
    
    # Check if any tool was DENIED
    denied_calls = [call for call in tool_calls if call.get("decision") == "DENY"]
    
    if denied_calls:
        print(f"\n✅ DENY scenario verified - {len(denied_calls)} tool(s) denied")
        
        # Verify replanning occurred (should try safe alternatives)
        print("\n🔄 Checking for replanning...")
        observations = get_task_trace(task_id).get("observations", [])
        replan_events = [obs for obs in observations if obs.get("type") == "replan"]
        
        if replan_events:
            print(f"   ✅ Agent replanned {len(replan_events)} time(s)")
        else:
            print("   ⚠️ No replanning detected")
        
        return True
    else:
        print("\n⚠️ No DENY decisions found")
        return False


def test_scenario_hold():
    """Test HOLD scenario - high amount requiring approval."""
    print("\n" + "🟡" * 35)
    print("TEST SCENARIO 3: HOLD (Amount Threshold)")
    print("🟡" * 35)
    
    # This should trigger HOLD due to amount > threshold
    task_id = create_task(
        "Transfer ₹3,00,000 to supplier SUP-12345",
        "task-hold-001"
    )
    if not task_id:
        print("❌ Failed to create task")
        return False
    
    result = poll_task(task_id, max_wait=60)
    tool_calls = verify_gateway_calls(task_id)
    
    # Check if any tool triggered HOLD
    hold_calls = [call for call in tool_calls if call.get("decision") == "HOLD"]
    
    if hold_calls:
        print(f"\n✅ HOLD scenario verified - {len(hold_calls)} tool(s) held")
        
        # Check for approval polling
        for call in hold_calls:
            approval_id = call.get("approval_id")
            if approval_id:
                print(f"\n   📝 Approval ID: {approval_id}")
                print("   ⏳ Note: Mock gateway auto-approves after 10 seconds")
        
        return True
    else:
        print("\n⚠️ No HOLD decisions found")
        return False


def main():
    """Run integration tests."""
    print("\n" + "🧪" * 35)
    print("INTEGRATION TEST: Agent Runtime + Mock Gateway")
    print("🧪" * 35)
    print(f"\nTimestamp: {datetime.now()}")
    print(f"Agent URL: {AGENT_URL}")
    print(f"Gateway URL: {GATEWAY_URL}")
    
    # Step 1: Check services
    if not check_services():
        print("\n❌ Services not ready. Exiting.")
        return
    
    # Wait a bit for services to stabilize
    print("\n⏳ Waiting 2 seconds for services to stabilize...")
    time.sleep(2)
    
    # Run test scenarios
    results = []
    
    try:
        results.append(("ALLOW", test_scenario_allow()))
    except Exception as e:
        print(f"\n❌ ALLOW test failed with error: {e}")
        results.append(("ALLOW", False))
    
    try:
        results.append(("DENY", test_scenario_deny()))
    except Exception as e:
        print(f"\n❌ DENY test failed with error: {e}")
        results.append(("DENY", False))
    
    try:
        results.append(("HOLD", test_scenario_hold()))
    except Exception as e:
        print(f"\n❌ HOLD test failed with error: {e}")
        results.append(("HOLD", False))
    
    # Summary
    print("\n" + "=" * 70)
    print("  INTEGRATION TEST RESULTS")
    print("=" * 70 + "\n")
    
    for scenario, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {scenario:15} {status}")
    
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    
    print(f"\n   Total: {passed_count}/{total} scenarios passed")
    
    if passed_count == total:
        print("\n🎉 All integration tests passed!")
    else:
        print(f"\n⚠️ {total - passed_count} scenario(s) failed")
    
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
