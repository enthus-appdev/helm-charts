"""Offline render contracts; requires Helm 3 and PyYAML. No cluster access."""
import pathlib
import subprocess
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLUSTER_KINDS = {"ClusterRole", "ClusterRoleBinding", "CustomResourceDefinition"}


def render(chart, *settings, string_settings=()):
    command = ["helm", "template", "ownership-test", str(ROOT / "charts" / chart),
               "--namespace", "runtime-test"]
    for setting in settings:
        command.extend(["--set", setting])
    for setting in string_settings:
        command.extend(["--set-string", setting])
    result = subprocess.run(command, text=True, capture_output=True, check=True, timeout=60)
    return [obj for obj in yaml.safe_load_all(result.stdout) if obj]


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

    def test_keep_cannot_stage_without_rendering_rbac(self):
        for chart in ["api-manager-deployment", "negsoft-operator"]:
            with self.subTest(chart=chart):
                objects = render(chart, "rbac.create=false", "rbac.keep=true")
                self.assertFalse(any(obj["kind"] in {"ClusterRole", "ClusterRoleBinding"} for obj in objects))

    def test_crd_retention_is_independent_of_rbac(self):
        objects = render("negsoft-operator", "rbac.create=false", "crds.install=true")
        cluster = [obj for obj in objects if obj["kind"] in CLUSTER_KINDS]
        self.assertEqual(len(cluster), 1)
        self.assertEqual(cluster[0]["kind"], "CustomResourceDefinition")
        self.assertEqual(cluster[0]["metadata"]["annotations"]["helm.sh/resource-policy"], "keep")

    def test_rejects_invalid_runtime_identity(self):
        for chart in ["api-manager-deployment", "negsoft-operator"]:
            for name in ["bad:name", "bad/name", "Uppercase", "bad\nsubjects:", "x" * 254,
                         "false", "0", "123"]:
                with self.subTest(chart=chart, name=name):
                    with self.assertRaises(subprocess.CalledProcessError) as error:
                        render(chart, f"serviceAccount.name={name}")
                    self.assertIn("serviceAccount.name must be a Kubernetes DNS subdomain string", error.exception.stderr)

    def test_valid_dotted_and_boundary_runtime_identity(self):
        for chart in ["api-manager-deployment", "negsoft-operator"]:
            for name in ["runtime.sa.example", ("a" * 63 + ".") * 3 + "b" * 61, "a" * 64, "123"]:
                with self.subTest(chart=chart, name=name):
                    objects = render(chart, string_settings=[f"serviceAccount.name={name}"])
                    bindings = [obj for obj in objects if obj["kind"] == "ClusterRoleBinding"]
                    self.assertEqual(len(bindings), 1 if chart == "api-manager-deployment" else 2)
                    for binding in bindings:
                        self.assertEqual(binding["subjects"][0]["name"], name)
                    account = next(obj for obj in objects if obj["kind"] == "ServiceAccount")
                    deployment = next(obj for obj in objects if obj["kind"] == "Deployment")
                    self.assertEqual(account["metadata"]["name"], name)
                    self.assertEqual(deployment["spec"]["template"]["spec"]["serviceAccountName"], name)
                    external = render(chart, "serviceAccount.create=false",
                                      string_settings=[f"serviceAccount.name={name}"])
                    self.assertFalse(any(obj["kind"] == "ServiceAccount" for obj in external))
                    workload = next(obj for obj in external if obj["kind"] == "Deployment")
                    self.assertEqual(workload["spec"]["template"]["spec"]["serviceAccountName"], name)

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
