"""Offline subscription CSI schema/render contracts; Helm, PyYAML, jsonschema."""
import hashlib
import pathlib
import subprocess
import tempfile
import unittest

import jsonschema
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CRD = ROOT / "charts/negsoft-operator/files/crd-negsoftsubscriptions.yaml"
MOUNT = {"name": "job-credentials", "mountPath": "/var/run/job-secrets",
         "secretProviderClass": "subscription-runtime"}


def render(values):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as file:
        yaml.safe_dump(values, file)
        file.flush()
        output = subprocess.check_output(["helm", "template", "test-subscription", str(ROOT / "charts/api-subscription"),
                                          "--namespace", "runtime-ns", "-f", file.name],
                                         text=True, stderr=subprocess.STDOUT)
    return [obj for obj in yaml.safe_load_all(output) if obj]


class SubscriptionCSI(unittest.TestCase):
    def test_default_has_no_csi_or_spc(self):
        objects = render({})
        subscription = next(obj for obj in objects if obj["kind"] == "NegSoftSubscription")
        self.assertNotIn("csiSecrets", subscription["spec"])
        self.assertFalse(any(obj["kind"] == "SecretProviderClass" for obj in objects))

    def test_owned_and_external_spc_with_schema(self):
        schema = yaml.safe_load(CRD.read_text())["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
        for create in [None, True, False]:
            with self.subTest(create=create):
                entry = dict(MOUNT, provider="gke", secrets=[{"resourceName": "projects/test/secrets/sql/versions/latest",
                                                            "path": "password"}])
                if create is not None:
                    entry["create"] = create
                objects = render({"csiSecrets": [entry]})
                subscription = next(obj for obj in objects if obj["kind"] == "NegSoftSubscription")
                self.assertEqual(subscription["spec"]["csiSecrets"], [MOUNT])
                jsonschema.validate(subscription, schema)
                spcs = [obj for obj in objects if obj["kind"] == "SecretProviderClass"]
                self.assertEqual(len(spcs), 0 if create is False else 1)
                if spcs:
                    self.assertEqual(spcs[0]["spec"]["provider"], "gke")
                    self.assertNotIn("secretObjects", spcs[0]["spec"])
                self.assertFalse(any(obj["kind"] in {"Deployment", "Job", "CronJob", "Pod", "Secret"} for obj in objects))

    def test_optional_driver_and_no_fake_identity_override(self):
        objects = render({"csiSecrets": [dict(MOUNT, create=False, driver="secrets-store.csi.k8s.io")],
                          "serviceAccount": {"name": "declared-worker", "create": True}})
        subscription = next(obj for obj in objects if obj["kind"] == "NegSoftSubscription")
        self.assertEqual(subscription["spec"]["csiSecrets"][0]["driver"], "secrets-store.csi.k8s.io")
        self.assertNotIn("serviceAccountName", subscription["spec"])
        self.assertEqual(next(obj for obj in objects if obj["kind"] == "ServiceAccount")["metadata"]["name"], "declared-worker")

    def test_create_string_false_rejected(self):
        with self.assertRaises(subprocess.CalledProcessError) as error:
            render({"csiSecrets": [dict(MOUNT, create="false")]})
        self.assertIn("csiSecrets.create must be a boolean", error.exception.output)

    def test_generated_source_provenance_and_chart_retention(self):
        content = CRD.read_bytes()
        parsed = yaml.safe_load(content)
        self.assertEqual(parsed["metadata"]["annotations"]["helm.sh/resource-policy"], "keep")
        upstream = content.replace(b"    helm.sh/resource-policy: keep\n", b"")
        blob = hashlib.sha1(b"blob " + str(len(upstream)).encode() + b"\0" + upstream).hexdigest()
        # Authoritative generated source from operator PR115, commit65d8563.
        self.assertEqual(blob, "351ca2100d2919c6ddda6a4679e870c55b94985f")
        self.assertNotIn("helm.sh/hook", parsed["metadata"]["annotations"])
        csi = parsed["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]["csiSecrets"]
        self.assertEqual(csi["maxItems"], 16)
        self.assertEqual(csi["x-kubernetes-list-map-keys"], ["name"])
        self.assertEqual(csi["items"]["properties"]["driver"]["default"], "secrets-store-gke.csi.k8s.io")


if __name__ == "__main__":
    unittest.main()
