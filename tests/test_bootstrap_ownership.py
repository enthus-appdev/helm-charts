"""Offline render contracts; requires Helm 3 and PyYAML. No cluster access."""
import pathlib
import subprocess
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLUSTER_KINDS = {"ClusterRole", "ClusterRoleBinding", "CustomResourceDefinition"}


def render(chart, *settings):
    command = ["helm", "template", "ownership-test", str(ROOT / "charts" / chart),
               "--namespace", "runtime-test"]
    for setting in settings:
        command.extend(["--set", setting])
    return [obj for obj in yaml.safe_load_all(subprocess.check_output(command, text=True)) if obj]


class BootstrapOwnership(unittest.TestCase):
    def test_defaults_and_retention(self):
        for chart, expected in [("api-manager-deployment", 2), ("negsoft-operator", 5)]:
            with self.subTest(chart=chart):
                defaults = render(chart)
                retained = render(chart, "rbac.keep=true")
                cluster = [obj for obj in defaults if obj["kind"] in CLUSTER_KINDS]
                self.assertEqual(len(cluster), expected)
                for obj in cluster:
                    if obj["kind"] != "CustomResourceDefinition":
                        self.assertNotIn("helm.sh/resource-policy", obj["metadata"].get("annotations", {}))
                for obj in retained:
                    if obj["kind"] in CLUSTER_KINDS:
                        self.assertEqual(obj["metadata"]["annotations"]["helm.sh/resource-policy"], "keep")
                # Retention changes no rules, names, subjects, or namespaced workloads.
                for obj in retained:
                    if obj["kind"] in {"ClusterRole", "ClusterRoleBinding"}:
                        del obj["metadata"]["annotations"]
                self.assertEqual(defaults, retained)

    def test_external_bootstrap_has_no_cluster_output(self):
        for chart in ["api-manager-deployment", "negsoft-operator"]:
            with self.subTest(chart=chart):
                objects = render(chart, "rbac.create=false", "crds.install=false")
                self.assertFalse([obj for obj in objects if obj["kind"] in CLUSTER_KINDS])
                self.assertTrue(any(obj["kind"] == "Deployment" for obj in objects))
                self.assertTrue(any(obj["kind"] == "ServiceAccount" for obj in objects))

    def test_operator_stage_crd_switch(self):
        objects = render("negsoft-operator", "crds.install=false", "rbac.keep=true")
        cluster = [obj for obj in objects if obj["kind"] in CLUSTER_KINDS]
        self.assertEqual(len(cluster), 4)
        for obj in cluster:
            self.assertEqual(obj["metadata"]["annotations"]["helm.sh/resource-policy"], "keep")

    def test_binding_uses_runtime_service_account(self):
        for chart in ["api-manager-deployment", "negsoft-operator"]:
            for create, name in [("true", ""), ("true", "custom-runtime"), ("false", "external-runtime"), ("false", "")]:
                with self.subTest(chart=chart, create=create, name=name):
                    objects = render(chart, f"serviceAccount.create={create}", f"serviceAccount.name={name}")
                    bindings = [obj for obj in objects if obj["kind"] == "ClusterRoleBinding"]
                    self.assertEqual(len(bindings), 1 if chart == "api-manager-deployment" else 2)
                    expected_name = name or (f"ownership-test-{chart}" if create == "true" else "default")
                    for binding in bindings:
                        self.assertEqual(binding["subjects"], [{"kind": "ServiceAccount", "name": expected_name,
                                                              "namespace": "runtime-test"}])


if __name__ == "__main__":
    unittest.main()
