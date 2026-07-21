import json
import unittest
from pathlib import Path

from case_memory import init_case_memory
from explainable_report import ExplainableReportBuilder, render_markdown
from orchestrator import Orchestrator


ROOT = Path(__file__).resolve().parent.parent
CASE = ROOT / "output" / "patient_041_S_4060_analysis.json"


class RWEAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = json.loads(CASE.read_text(encoding="utf-8"))
        cls.memory = Orchestrator(use_llm=False).run(init_case_memory(raw))

    def test_seven_agents_run(self):
        self.assertEqual(len(self.memory["agent_outputs"]), 7)
        self.assertIn("生物标志物Agent", self.memory["agent_outputs"])
        self.assertIn("影像Agent", self.memory["agent_outputs"])

    def test_quality_flags_known_source_problems(self):
        codes = {
            issue["code"]
            for issue in self.memory["agent_outputs"]["数据质控Agent"]["quality_issues"]
        }
        self.assertIn("MISSING_MOCA_TOTAL", codes)
        self.assertIn("FAQ_TOTAL_ITEM_CONFLICT", codes)

    def test_longitudinal_scores(self):
        trajectories = self.memory["agent_outputs"]["纵向统计Agent"]["trajectories"]
        self.assertEqual(trajectories["mmse"]["absolute_change"], -3.0)
        self.assertEqual(trajectories["adas13"]["absolute_change"], 10.0)
        self.assertEqual(trajectories["mmse"]["pattern"], "non_monotonic")

    def test_synthesis_does_not_claim_ad_etiology(self):
        report = self.memory["final_report"]
        self.assertEqual(report["etiology"]["label"], "undetermined")
        self.assertEqual(report["clinical_stage"]["label"], "MCI-compatible")

    def test_biomarkers_and_imaging_are_explicitly_bounded(self):
        biomarker = self.memory["agent_outputs"]["生物标志物Agent"]
        imaging = self.memory["agent_outputs"]["影像Agent"]
        self.assertEqual(biomarker["apoe"]["results"][0]["genotype"], "ε2/ε3")
        self.assertEqual(biomarker["atn_assessment"]["amyloid"], "indeterminate")
        self.assertEqual(imaging["status"], "awaiting_manual_paths")

    def test_explainable_report_is_traceable_offline(self):
        report = ExplainableReportBuilder(use_llm=False).build(self.memory)
        self.assertEqual(report["clinical_interpretation"]["etiology"]["label"], "undetermined")
        self.assertTrue(all(item["evidence_id"].startswith("E") for item in report["evidence"]))
        self.assertIn("record_id=137", render_markdown(report))
        self.assertEqual(report["explainability"]["llm_status"], "disabled")


if __name__ == "__main__":
    unittest.main()
