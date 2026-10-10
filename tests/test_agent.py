import unittest

import tests  # noqa: F401  (sets sys.path)
from breathebuddy.agent import SimpleAgent, ask, build_strands_agent, get_agent
from breathebuddy.service import bootstrap


class TestAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bootstrap()

    def test_strands_sdk_builds_real_agent(self):
        try:
            from strands import Agent  # noqa: F401
        except Exception:
            self.skipTest("strands-agents not installed")
        agent = build_strands_agent()
        self.assertIsNotNone(agent, "Strands Agent should build when SDK present")
        self.assertEqual(type(agent).__name__, "Agent")
        self.assertIsNot(SimpleAgent, type(agent))
        # tools are registered through the SDK tool registry
        self.assertGreaterEqual(len(agent.tool_registry.registry), 5)

    def test_get_agent_prefers_strands(self):
        try:
            import strands  # noqa: F401
        except Exception:
            self.skipTest("strands-agents not installed")
        agent = get_agent(prefer_strands=True)
        self.assertNotIsInstance(agent, SimpleAgent)

    def test_ask_falls_back_without_credentials(self):
        # No Bedrock credentials in CI/local -> must still return a usable answer.
        res = ask("Should Mater Dei School hold outdoor assembly tomorrow?",
                  prefer_strands=True)
        self.assertIn("answer", res)
        self.assertTrue(res["answer"])
        self.assertIn(res["engine"], ("strands", "simple"))

    def test_simple_engine_always_offline(self):
        res = ask("Should Mater Dei School hold outdoor assembly tomorrow?", prefer_strands=False)
        self.assertEqual(res["engine"], "simple")
        self.assertTrue(res["answer"])


if __name__ == "__main__":
    unittest.main()
