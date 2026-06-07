# Triage MongoDB Kubernetes Runtime Failure

Use this skill when MongoDB symptoms correlate with Kubernetes runtime signals such as Pending Pods, failed scheduling, PVC binding errors, image pull failures, CrashLoopBackOff, readiness failures, or StatefulSet replica mismatch.

## Workflow

1. Identify the affected MongoDB component from Pod labels, StatefulSet name, and shard/configsvr/mongos naming.
2. Classify the Kubernetes runtime signal using Pod status, Pod conditions, Events, StatefulSet status, and Node state.
3. Map the signal to MongoDB impact: connection entrypoint, config server, shard member, or replica redundancy.
4. Generate supported and refuted hypotheses with evidence and evidence gaps.
5. Recommend only read-only verification actions unless the user explicitly asks for remediation.
