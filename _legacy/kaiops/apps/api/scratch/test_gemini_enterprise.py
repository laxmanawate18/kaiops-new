import sys
import os
import requests
import time
import base64
import json

BASE_URL = "http://localhost:8000/api/v1"

print("="*50)
print("1. Testing Authentication")
login_res = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": "admin", "password": "admin123"}
)
if login_res.status_code != 200:
    print(f"Failed to login: {login_res.text}")
    sys.exit(1)
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✅ Login successful")

print("="*50)
print("2. Testing Vertex AI Custom Sessions (Firestore Bypass)")
sess_res = requests.post(f"{BASE_URL}/chat/sessions", json={"name": "E2E Test Session"}, headers=headers)
if sess_res.status_code != 201:
    print(f"Failed to create session: {sess_res.text}")
    sys.exit(1)
session_id = sess_res.json()["session"]["id"]
print(f"✅ Session created: {session_id}")

msg_res = requests.post(
    f"{BASE_URL}/chat/messages",
    json={"session_id": session_id, "message": "Hello SRE agent, this is a test.", "metadata": {}},
    headers=headers
)
if msg_res.status_code != 200:
    print(f"Failed basic message: {msg_res.text}")
else:
    print(f"✅ Basic message response received! Length: {len(msg_res.json().get('agent_message', {}).get('text', ''))}")

print("="*50)
print("3. Testing Vertex AI Search & Grounding (RAG)")
rag_res = requests.post(
    f"{BASE_URL}/chat/messages",
    json={
        "session_id": session_id,
        "message": "What does the runbook say about the Payment Gateway?",
        "metadata": {}
    },
    headers=headers
)
print("✅ RAG response received.")
rag_data = rag_res.json()
print("Response text excerpt:", rag_data.get('agent_message', {}).get('text', '')[:100].replace('\n', ' '), "...")

print("="*50)
print("4. Testing Multi-Modal Vision Analysis")
dummy_img_b64 = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
vis_res = requests.post(
    f"{BASE_URL}/chat/messages",
    json={
        "session_id": session_id,
        "message": "Can you analyze this CloudWatch graph screenshot for anomalies?",
        "metadata": {
            "images": [
                {"mime_type": "image/gif", "data": dummy_img_b64}
            ]
        }
    },
    headers=headers
)
print("✅ Vision message sent.")
vis_text = vis_res.json().get('agent_message', {}).get('text', '')
print("Response text excerpt:", vis_text[:100].replace('\n', ' '), "...")

print("="*50)
print("5. Testing HITL Remediation (Destructive Action)")
hitl_res = requests.post(
    f"{BASE_URL}/chat/messages",
    json={
        "session_id": session_id,
        "message": "Restart the payment-gateway pod immediately.",
        "metadata": {}
    },
    headers=headers
)
hitl_data = hitl_res.json()
agent_response = hitl_data.get("agent_message", {}).get("text", "")
metadata = hitl_data.get("agent_message", {}).get("metadata", {})

print(f"Response text excerpt: {agent_response[:100].replace(chr(10), ' ')}...")
if metadata.get("requires_confirmation") is True:
    print(f"✅ HITL intercepted correctly! Pending Tool: {metadata.get('pending_tool')}")
else:
    print("❌ HITL interception did not flag requires_confirmation=True!")
    print(f"Metadata dump: {metadata}")

print("="*50)
print("6. Verifying Session Persistence in Firestore")
get_sess = requests.get(f"{BASE_URL}/chat/sessions/{session_id}/messages", headers=headers)
messages = get_sess.json().get("messages", [])
print(f"✅ Found {len(messages)} messages persisted in the session.")
if len(messages) >= 8:
    print("✅ All conversation turns successfully stored in the Custom Memory Bank!")
else:
    print(f"❌ Missing messages in history! Found {len(messages)}")

print("="*50)
print("🎉 ALL TESTS COMPLETED")
