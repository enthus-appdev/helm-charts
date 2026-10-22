"""Offline CSI contracts; requires Helm 3 and PyYAML, never a cluster."""
import pathlib
import subprocess
import tempfile
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHARTS = ["api-deployment", "api-job-cronjob", "api-manager-deployment",
          "api-notification-deployment", "api-portal-deployment", "negsoft-operator"]
CSI = {"name": "runtime-files", "mountPath": "/var/run/runtime-secrets",
       "secretProviderClass": "bootstrap-runtime", "create": False}


def render(chart, values):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as file:
        yaml.safe_dump(values, file)
        file.flush()
        output = subprocess.check_output(["helm", "template", "runtime-test", str(ROOT / "charts" / chart),
                                          "--namespace", "test-ns", "-f", file.name], text=True)
    return [obj for obj in yaml.safe_load_all(output) if obj]


def podspecs(objects):
    for obj in objects:
        if obj["kind"] == "Deployment":
            yield obj["spec"]["template"]["spec"]
        elif obj["kind"] == "CronJob":
            yield obj["spec"]["jobTemplate"]["spec"]["template"]["spec"]
        elif obj["kind"] == "ConfigMap" and "template_job.yaml" in obj.get("data", {}):
            yield yaml.safe_load(obj["data"]["template_job.yaml"])["spec"]["template"]["spec"]


class CSIInterfaces(unittest.TestCase):
    def test_external_spc_readonly_mounts(self):
        for chart in CHARTS:
            with self.subTest(chart=chart):
                values = {"csiSecrets": [CSI], "job": {"serviceAccountName": "job-runtime"},
                          "serviceAccount": {"name": "controller-runtime"},
                          "cronjobs": [{"name": "test", "schedule": "0 * * * *"}],
                          "env": [{"name": "MSSQL_CONFIG_FILE", "value": "/var/run/runtime-secrets/mssql.json"}]}
                objects = render(chart, values)
                self.assertFalse(any(obj["kind"] == "SecretProviderClass" for obj in objects))
                specs = list(podspecs(objects))
                self.assertTrue(specs)
                for spec in specs:
                    volume = next(volume for volume in spec["volumes"] if volume["name"] == CSI["name"])
                    self.assertEqual(volume["csi"], {"driver": "secrets-store-gke.csi.k8s.io", "readOnly": True,
                                                    "volumeAttributes": {"secretProviderClass": CSI["secretProviderClass"]}})
                    container = spec["containers"][0]
                    mount = next(mount for mount in container["volumeMounts"] if mount["name"] == CSI["name"])
                    self.assertEqual(mount, {"name": CSI["name"], "mountPath": CSI["mountPath"], "readOnly": True})
                    self.assertIn(values["env"][0], container["env"])
                    self.assertIn(spec["serviceAccountName"], ["controller-runtime", "job-runtime"])

    def test_managed_spc_default_and_explicit_create(self):
        for chart in CHARTS:
            for create in [None, True]:
                with self.subTest(chart=chart, create=create):
                    entry = dict(CSI, secrets=[{"resourceName": "projects/test/secrets/test/versions/latest", "path": "config"}])
                    if create is None:
                        del entry["create"]
                    else:
                        entry["create"] = create
                    objects = render(chart, {"csiSecrets": [entry], "job": {"serviceAccountName": "runtime"}})
                    spcs = [obj for obj in objects if obj["kind"] == "SecretProviderClass"]
                    self.assertEqual(len(spcs), 1)
                    self.assertEqual(spcs[0]["spec"]["provider"], "gke")
                    self.assertNotIn("secretObjects", spcs[0]["spec"])
                    self.assertEqual(yaml.safe_load(spcs[0]["spec"]["parameters"]["secrets"]), entry["secrets"])

    def test_operator_no_credential_secret_or_implicit_refs(self):
        objects = render("negsoft-operator", {"secret": {"create": False}, "csiSecrets": [CSI],
                                             "env": [{"name": "MSSQL_PASSWORD_FILE", "value": "/var/run/runtime-secrets/password"}]})
        self.assertFalse(any(obj["kind"] == "Secret" for obj in objects))
        controller = next(obj for obj in objects if obj["kind"] == "Deployment")
        env = controller["spec"]["template"]["spec"]["containers"][0]["env"]
        self.assertFalse(any("valueFrom" in item for item in env))
        self.assertEqual([item["name"] for item in env], ["CRONJOB_PREFIX", "MSSQL_PASSWORD_FILE"])
        config = next(obj for obj in objects if obj["kind"] == "ConfigMap")
        generated = yaml.safe_load(config["data"]["template_cronjob.yaml"])
        spec = generated["spec"]["jobTemplate"]["spec"]["template"]["spec"]
        self.assertFalse(any(volume["name"] == CSI["name"] for volume in spec["volumes"]))
        self.assertNotIn("env", spec["containers"][0])

    def test_operator_legacy_defaults_remain(self):
        objects = render("negsoft-operator", {})
        self.assertEqual(len([obj for obj in objects if obj["kind"] == "Secret"]), 1)
        controller = next(obj for obj in objects if obj["kind"] == "Deployment")
        env = controller["spec"]["template"]["spec"]["containers"][0]["env"]
        self.assertIn("MSSQL_PASSWORD", [item["name"] for item in env])
        self.assertIn("REDIS_PASSWORD", [item["name"] for item in env])


if __name__ == "__main__":
    unittest.main()
