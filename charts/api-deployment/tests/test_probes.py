"""Render regression tests. Run: python3 -m unittest discover -s charts/api-deployment/tests

Requires helm and PyYAML.
"""
import json
from pathlib import Path
import subprocess
import unittest

import yaml

CHART = Path(__file__).resolve().parents[1]


class ProbeTests(unittest.TestCase):
    def render(self, values=None):
        return subprocess.run(
            ["helm", "template", "test", str(CHART), "-f", "-"],
            input=json.dumps(values or {}), text=True, capture_output=True,
        )

    def container(self, values=None):
        result = self.render(values)
        self.assertEqual(result.returncode, 0, result.stderr)
        deployment = next(doc for doc in yaml.safe_load_all(result.stdout)
                          if doc and doc.get("kind") == "Deployment")
        return deployment["spec"]["template"]["spec"]["containers"][0]

    def test_defaults(self):
        container = self.container()
        for name in ("livenessProbe", "readinessProbe"):
            self.assertEqual(container[name], {"httpGet": {"path": "/", "port": "http"}})

    def test_independent_handlers_and_timing(self):
        container = self.container({
            "livenessProbe": {"grpc": {"port": 8080, "service": "liveness"}, "periodSeconds": 7},
            "readinessProbe": {"httpGet": {"path": "/ready", "port": "http"}},
        })
        self.assertEqual(container["livenessProbe"], {
            "grpc": {"port": 8080, "service": "liveness"}, "periodSeconds": 7,
        })
        self.assertEqual(container["readinessProbe"]["httpGet"]["path"], "/ready")

    def test_disabled_probe(self):
        container = self.container({"livenessProbe": {"enabled": False},
                                    "readinessProbe": {"grpc": {"port": 8081}}})
        self.assertNotIn("livenessProbe", container)
        self.assertEqual(container["readinessProbe"], {"grpc": {"port": 8081}})

    def test_invalid_grpc_ports(self):
        for port in (None, "http", "8081", 0, 65536, 8081.9):
            with self.subTest(port=port):
                result = self.render({"livenessProbe": {"grpc": {"port": port}}})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("livenessProbe.grpc.port must be an integer", result.stderr)

    def test_multiple_handlers(self):
        for handler in ("httpGet", "tcpSocket", "exec"):
            with self.subTest(handler=handler):
                result = self.render({"readinessProbe": {
                    "grpc": {"port": 8080}, handler: {"port": 8080},
                }})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("exactly one probe handler", result.stderr)

    def test_legacy_configuration_fails_explicitly(self):
        result = self.render({"grpcProbes": {"enabled": True}})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("grpcProbes has been removed", result.stderr)


if __name__ == "__main__":
    unittest.main()
