"""Local model adapter for Florida Litigator Weekly Update (C32).

Provides a deterministic, rule-based analysis model.
No external API calls, no cloud fallback.
Produces documented analysis from verified source facts.

Config via config/analysis.json.
"""
from __future__ import annotations
from typing import Any
from pathlib import Path

class ModelError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")

class AnalysisProfile:
    """Analysis profile configuration."""
    def __init__(self, profile_id: str, model_name: str = "flwu-deterministic",
                 prompt_template: str | None = None):
        self.profile_id = profile_id
        self.model_name = model_name
        self.prompt_template = prompt_template

    def analyze(self, record: dict[str, Any]) -> dict[str, Any]:
        """Run deterministic analysis on a record.

        Produces:
        - summary: deterministic summary of the record
        - practice_actions: list of practice actions
        - risk_flags: any identified risks
        - confidence: confidence level (high/medium/low)
        """
        kind = record.get("kind", "")
        title = record.get("title", "Untitled")
        legal_status = record.get("legal_status", "unknown")

        analysis = {
            "analysis_type": kind,
            "summary": f"Analysis of {kind}: {title} (status: {legal_status})",
            "practice_actions": self._suggest_actions(kind, legal_status),
            "risk_flags": self._identify_risks(kind, legal_status, record),
            "confidence": self._determine_confidence(record),
            "source_ids": [record.get("source_id", "")],
        }
        return analysis

    def _suggest_actions(self, kind: str, status: str) -> list[str]:
        actions = []
        if kind in ("statute", "bill"):
            actions.append("Verify current citation format")
            actions.append("Check for recent amendments")
        elif kind == "case":
            actions.append("Review cited authority for subsequent history")
            actions.append("Verify jurisdictional scope")
        elif kind in ("court_rule", "agency_rule"):
            actions.append("Confirm effective date compliance")
            actions.append("Check for pending rulemaking")
        else:
            actions.append("Verify current applicability")
        if status == "operative":
            actions.append("Confirm no superseding authority")
        elif status in ("withdrawn", "superseded"):
            actions.append("Note historical status for research purposes")
        return actions

    def _identify_risks(self, kind: str, status: str, record: dict) -> list[str]:
        risks = []
        if status == "proposed":
            risks.append("Not yet operative - check for adoption")
        if record.get("legal_status") == "unknown":
            risks.append("Status uncertain - verify current status")
        if record.get("body_text") and "synthetic" in record.get("body_text", "").lower():
            risks.append("Synthetic/test content - not for production use")
        return risks

    def _determine_confidence(self, record: dict) -> str:
        body = record.get("body_text") or ""
        if len(body.strip()) < 10:
            return "low"
        if record.get("legal_status") == "unknown":
            return "medium"
        return "high"

def load_analysis_config(path: Path | None = None) -> list[AnalysisProfile]:
    """Load analysis profiles from config/analysis.json."""
    if path is None:
        path = Path("config/analysis.json")

    if path.is_file():
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        return [AnalysisProfile(p["profile_id"], p.get("model_name", "flwu-deterministic"))
                for p in data.get("profiles", [])]

    # Default profile
    return [AnalysisProfile("default")]

def run_analysis(record: dict[str, Any], profile: AnalysisProfile | None = None) -> dict[str, Any]:
    """Run analysis on a record using the default profile."""
    profiles = load_analysis_config()
    active_profile = profile or profiles[0]
    return active_profile.analyze(record)
