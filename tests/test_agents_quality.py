"""The AGENTS.md review is advisory, check-only and gated by changes to AGENTS.md."""
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "rules/reviews/agents-quality"


class AgentsQualityTests(unittest.TestCase):
    def test_review_is_advisory_and_triggered_only_by_agents_md(self):
        rule = tomllib.loads((RULE / "rule.toml").read_text())
        self.assertFalse(rule["blocking"])
        self.assertNotIn("run_at", rule)  # Only the rule set assigns an execution point.
        self.assertEqual(rule["review"]["trigger"], {"changed_files": ["AGENTS.md"]})
        self.assertFalse(rule["review"]["include_diff"])
        self.assertEqual(rule["review"]["context"], [{"path": "AGENTS.md"}])

    def test_rule_set_assigns_the_review_to_check_only(self):
        config = tomllib.loads((ROOT / "rulesets/multi-point/repository-conventions/config.toml").read_text())
        entries = [rule for rule in config["rules"]
                   if isinstance(rule, dict) and rule["id"] == "rules/reviews/agents-quality"]
        self.assertEqual([entry["run_at"] for entry in entries], [["check"]])

    def test_prompt_embeds_the_rubric(self):
        prompt = (RULE / "prompt.md").read_text()
        self.assertIn("Contradictions, conflicting requirements", prompt)


if __name__ == "__main__":
    unittest.main()
