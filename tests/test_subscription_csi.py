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
        result = subprocess.run(["helm", "template", "test-subscription", str(ROOT / "charts/api-subscription"),
                                 "--namespace", "runtime-ns", "-f", file.name],
                                text=True, capture_output=True, check=True, timeout=60)
        output = result.stdout
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

    def test_default_provider_and_mixed_spc_ownership(self):
        source = {"resourceName": "projects/test/secrets/sql/versions/latest", "path": "password"}
        owned = dict(MOUNT, name="owned", secretProviderClass="owned-provider", secrets=[source])
        external = dict(MOUNT, name="external", secretProviderClass="shared-provider", create=False)
        objects = render({"csiSecrets": [owned, external]})
        subscription = next(obj for obj in objects if obj["kind"] == "NegSoftSubscription")
        self.assertEqual([item["name"] for item in subscription["spec"]["csiSecrets"]], ["owned", "external"])
        spcs = [obj for obj in objects if obj["kind"] == "SecretProviderClass"]
        self.assertEqual(len(spcs), 1)
        self.assertEqual(spcs[0]["metadata"]["name"], "owned-provider")
        self.assertEqual(spcs[0]["spec"]["provider"], "gke")
        self.assertEqual(yaml.safe_load(spcs[0]["spec"]["parameters"]["secrets"]), [source])

    def test_missing_mount_fields_fail_before_invalid_cr_output(self):
        for entry, field in [({"secretProviderClass": "spc"}, "name"),
                             ({"name": "volume", "secretProviderClass": "spc"}, "mountPath"),
                             ({"name": "volume", "mountPath": "/runtime"}, "secretProviderClass")]:
            entry["create"] = False
            with self.subTest(field=field):
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    render({"csiSecrets": [entry]})
                self.assertIn(f"csiSecrets.{field} is required", error.exception.stderr)

    def test_credential_retention_flag_requires_boolean(self):
        with self.assertRaises(subprocess.CalledProcessError) as error:
            render({"credentialsKeep": "false", "credentials": {"synthetic": "fixture-only"}})
        self.assertIn("credentialsKeep must be a boolean", error.exception.stderr)

    def test_create_string_false_rejected(self):
        with self.assertRaises(subprocess.CalledProcessError) as error:
            render({"csiSecrets": [dict(MOUNT, create="false")]})
        self.assertIn("csiSecrets.create must be a boolean", error.exception.stderr)

    def test_legacy_secret_retention_requires_staging_before_omission(self):
        credentials = {"synthetic-file": "fixture-only"}
        default = next(obj for obj in render({"credentials": credentials}) if obj["kind"] == "Secret")
        retained = next(obj for obj in render({"credentials": credentials, "credentialsKeep": True})
                        if obj["kind"] == "Secret")
        self.assertNotIn("helm.sh/resource-policy", default["metadata"].get("annotations", {}))
        self.assertEqual(retained["metadata"]["annotations"]["helm.sh/resource-policy"], "keep")
        del retained["metadata"]["annotations"]
        self.assertEqual(default, retained)
        omitted = render({"credentialsKeep": True, "csiSecrets": [dict(MOUNT, create=False)]})
        self.assertFalse(any(obj["kind"] == "Secret" for obj in omitted))

    def test_missing_new_retention_flag_preserves_default(self):
        objects = render({"credentialsKeep": None, "credentials": {"synthetic": "fixture-only"}})
        secret = next(obj for obj in objects if obj["kind"] == "Secret")
        self.assertNotIn("helm.sh/resource-policy", secret["metadata"].get("annotations", {}))

    def test_owned_spc_requires_nonempty_complete_sources(self):
        for sources in [None, [], "not-a-list"]:
            with self.subTest(sources=sources):
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    render({"csiSecrets": [dict(MOUNT, secrets=sources)]})
                self.assertIn("csiSecrets.secrets must be a non-empty list", error.exception.stderr)
        for source in [{"path": "password"}, {"resourceName": "projects/test/secrets/sql/versions/latest"},
                       {"resourceName": "", "path": "password"}, "not-an-object"]:
            with self.subTest(source=source):
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    render({"csiSecrets": [dict(MOUNT, secrets=[source])]})
                self.assertIn("resourceName and path strings", error.exception.stderr)

    def test_owned_spc_names_are_unique_but_external_sharing_allowed(self):
        owned = dict(MOUNT, secrets=[{"resourceName": "projects/test/secrets/sql/versions/latest", "path": "password"}])
        second = dict(owned, name="second-volume")
        with self.assertRaises(subprocess.CalledProcessError) as error:
            render({"csiSecrets": [owned, second]})
        self.assertIn("chart-owned secretProviderClass must be unique", error.exception.stderr)
        second["create"] = False
        objects = render({"csiSecrets": [owned, second]})
        self.assertEqual(len([obj for obj in objects if obj["kind"] == "SecretProviderClass"]), 1)

    def test_owned_provider_driver_pairing_is_gke_only(self):
        owned = dict(MOUNT, driver="secrets-store-gke.csi.k8s.io", provider="gke",
                     secrets=[{"resourceName": "projects/test/secrets/sql/versions/latest", "path": "password"}])
        objects = render({"csiSecrets": [owned]})
        subscription = next(obj for obj in objects if obj["kind"] == "NegSoftSubscription")
        self.assertEqual(subscription["spec"]["csiSecrets"][0]["driver"], owned["driver"])
        self.assertEqual(next(obj for obj in objects if obj["kind"] == "SecretProviderClass")["spec"]["provider"], "gke")
        for field, value, message in [("driver", "secrets-store.csi.k8s.io", "requires the GKE driver"),
                                      ("provider", "gke\nsecretObjects:", "requires provider:gke")]:
            with self.subTest(field=field):
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    render({"csiSecrets": [dict(owned, **{field: value})]})
                self.assertIn(message, error.exception.stderr)

    def test_external_driver_must_match_crd_enum(self):
        for driver in ["typo-driver", False, ""]:
            with self.subTest(driver=driver):
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    render({"csiSecrets": [dict(MOUNT, create=False, driver=driver)]})
                self.assertIn("csiSecrets.driver must be a supported CSI driver", error.exception.stderr)

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
