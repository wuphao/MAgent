from __future__ import annotations

from multi_agent.domain.reports import ReportSnapshot


class PublicationGate:
    def validate(self, snapshot: ReportSnapshot, artifacts: dict[str, dict]) -> dict[str, list[str]]:
        blocking: list[str] = []
        warnings: list[str] = []
        artifact_ids = set(artifacts)
        for finding in snapshot.findings:
            missing = [artifact_id for artifact_id in finding.artifact_refs if artifact_id not in artifact_ids]
            if missing:
                blocking.append(f"finding {finding.finding_id} references missing artifacts: {', '.join(missing)}")
            if finding.status == "withdrawn":
                blocking.append(f"finding {finding.finding_id} is withdrawn and cannot be published")
            if not finding.support_refs and not finding.artifact_refs:
                warnings.append(f"finding {finding.finding_id} has no direct support refs")
        if snapshot.challenges and snapshot.status == "completed":
            warnings.append("snapshot has challenges but status is completed")
        return {"blocking_errors": blocking, "warnings": warnings}
