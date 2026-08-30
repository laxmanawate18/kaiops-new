# Past Incident: Session 2026-08-28


Session: 49604bcf-9964-486c-aa6f-0cd3872960dc

## Conversation

**AGENT:** Here are all the applications registered in the system:

**Registered Applications** (6 total — 🟢 6 · 🔴 0 · 🟡 0)

| Application | Provider | Owner | Cluster | Status | ArgoCD | Repo |
|---|---|---|---|---|---|---|
| failing-app | AWS | admin | — | 🟢 active | failing-app | org/repo |
| demo-broken | AWS | admin | — | 🟢 active | demo-broken | org/repo |
| log-agent-eks | AWS | aws_e2e | — | 🟢 active | log-agent-eks | org/repo |
| azure-to-do | AZURE | laxman | — | 🟢 active | azure-to-do | [repo](https://github.com/laxmanawate18/azure-todo.git) |
| gcp-todo | GCP | laxman | gcp-demo-cluster | 🟢 a

**AGENT:** 📋 **Issue Summary**
- Problem: No issues detected. The application `demo-broken` appears to be healthy.
- Application: demo-broken
- Affected Component(s): demo-broken
- Severity: 🟢 Healthy
- Detection Time: N/A (no issues detected)

☁️ **AWS/EKS Context**
- Cluster: log-agent-eks
- Region: ap-southeast-2
- Namespace: kaiops-demo
- Log Group: /aws/containerinsights/log-agent-eks/application

[STATS] **Component Health**
| Component | Status | Logs | Errors | CPU | Memory |
|---|---|---|---|---|---|
| demo-broken | 🟢 Healthy | 0 | No | N/A | N/A |

📈 **Log Evidence**
- No error logs or unusual 

**USER:** can you troubleshoot demo-broken

**AGENT:** 👋 Hello! I'm the KaiOPS Root SRE Agent. I can help you with application metadata, deployment status, source code information, observability, and root cause analysis across Azure, AWS, and GCP.

What can I do for you today?

**USER:** can list down all the app?

**USER:** hi
