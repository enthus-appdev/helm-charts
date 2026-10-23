"""Signature FUSE requests on direct pods and embedded job templates."""
import unittest

import yaml

from test_csi_interfaces import CSI, render

CHARTS = ["api-deployment", "api-job-cronjob", "api-manager-deployment", "negsoft-operator"]
REQUESTS = {"gke-gcsfuse/cpu-request": "10m", "gke-gcsfuse/memory-request": "128Mi"}


def templates(objects):
    for obj in objects:
        if obj["kind"] in {"Deployment", "Job"}:
            yield obj["spec"]["template"]
        elif obj["kind"] == "CronJob":
            yield obj["spec"]["jobTemplate"]["spec"]["template"]
        elif obj["kind"] == "ConfigMap":
            for key in ["template_job.yaml", "template_cronjob.yaml"]:
                if key in obj.get("data", {}):
                    yield from templates([yaml.safe_load(obj["data"][key])])


def values(enabled):
    return {"signatureVolume": {"enabled": enabled, "bucketName": "test-signatures"},
            "cronjobs": [{"name": "test", "schedule": "0 * * * *"}],
            "job": {"serviceAccountName": "job-runtime"}, "jobServiceAccountName": "subscription-runtime",
            "csiSecrets": [CSI], "serviceAccount": {"name": "controller-runtime"}}


class SignatureResources(unittest.TestCase):
    def test_enabled_requests_without_limits(self):
        for chart in CHARTS:
            with self.subTest(chart=chart):
                pods = list(templates(render(chart, values(True))))
                mounted = [pod for pod in pods if any(volume["name"] == "signatures"
                           for volume in pod["spec"].get("volumes", []))]
                self.assertEqual(len(mounted), 2 if chart == "api-manager-deployment" else 1)
                for pod in mounted:
                    annotations = pod["metadata"]["annotations"]
                    fuse = {key: value for key, value in annotations.items() if key.startswith("gke-gcsfuse/")}
                    self.assertEqual(fuse, {"gke-gcsfuse/volumes": "true", **REQUESTS})
                    volume = next(item for item in pod["spec"]["volumes"] if item["name"] == "signatures")
                    self.assertTrue(volume["csi"]["readOnly"])
                    self.assertEqual(volume["csi"]["volumeAttributes"]["bucketName"], "test-signatures")
                    self.assertNotEqual(pod["spec"]["serviceAccountName"], "default")

    def test_disabled_has_no_fuse_annotations(self):
        for chart in CHARTS:
            with self.subTest(chart=chart):
                for pod in templates(render(chart, values(False))):
                    self.assertFalse(any(key.startswith("gke-gcsfuse/")
                                         for key in pod["metadata"].get("annotations", {})))
                    self.assertFalse(any(volume["name"] == "signatures"
                                         for volume in pod["spec"].get("volumes", [])))

    def test_explicit_overrides_are_preserved(self):
        overrides = {"gke-gcsfuse/cpu-request": "20m", "gke-gcsfuse/memory-request": "192Mi",
                     "gke-gcsfuse/cpu-limit": "0", "gke-gcsfuse/memory-limit": "0"}
        for chart in CHARTS:
            with self.subTest(chart=chart):
                config = values(True)
                config["signatureVolume"]["sidecarAnnotations"] = overrides
                config["podAnnotations"] = {"test.example/annotation": "preserved"}
                for pod in templates(render(chart, config)):
                    annotations = pod["metadata"].get("annotations", {})
                    if "gke-gcsfuse/volumes" in annotations:
                        for key, value in overrides.items():
                            self.assertEqual(annotations[key], value)
                        self.assertEqual(annotations["test.example/annotation"], "preserved")


if __name__ == "__main__":
    unittest.main()
