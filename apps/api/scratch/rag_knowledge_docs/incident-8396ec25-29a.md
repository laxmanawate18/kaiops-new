# Past Incident: Session 2026-08-26


Session: 8396ec25-29a5-43eb-8540-4650cf26ad41

## Conversation

**AGENT:** 📚 I found the following diagnosis steps for an OOMKilled pod crash loop:

### 📋 **Issue Summary**
An **OOMKilled pod crash loop** typically presents as a pod entering `CrashLoopBackOff` with the reason `OOMKilled` (exit code 137), indicating that the container's memory usage exceeded its allocated limit, leading to its termination by the operating system.

### [SEARCH] **Diagnosis Steps for OOMKilled Pod Crash Loop**

1.  **Verify OOMKilled Status:**
    *   Use `kubectl describe pod <pod_name> -n <namespace>` and check the `Last State: Terminated` section for `Reason: OOMKilled` and `ExitCode

**USER:** Search the runbooks for OOMKilled pod crash loop and give me the diagnosis steps.
