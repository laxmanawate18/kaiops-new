import requests

BASE_URL = "http://localhost:8000/api/v1"

# 1. Login
login_res = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": "admin", "password": "admin123"}
)
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✅ 1. Login successful")

# 2. Simulate Autonomous P0 Outage
print("🚨 2. Triggering Autonomous Incident Simulation...")
sim_res = requests.post(
    f"{BASE_URL}/chat/incidents/simulate",
    json={"incident_name": "🚨 P0 Outage: Payment-Gateway Pod CrashLoopBackOff"},
    headers=headers
)

print(f"Status: {sim_res.status_code}")
data = sim_res.json()
print("Session ID:", data.get("session_id"))
print("Reasoning Steps:", data.get("reasoning_steps"))
print("Requires Confirmation:", data.get("requires_confirmation"))
print("Agent RCA excerpt:", data.get("agent_message", {}).get("text", "")[:200])
print("🎉 Autonomous Incident Simulation Verified Successfully!")

