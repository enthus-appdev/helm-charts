"""Render signature mounts with Helm. Run: python3 -m unittest discover -s tests."""

from pathlib import Path
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def render(chart, values):
    result = subprocess.run(
        ["helm", "template", "test", str(ROOT / "charts" / chart), "-f", "-"],
        input=yaml.safe_dump(values), text=True, capture_output=True, check=True,
    )
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def pod_spec(doc):
    if doc["kind"] == "CronJob":
        return doc["spec"]["jobTemplate"]["spec"]["template"]
    return doc["spec"]["template"]


class SignatureMounts(unittest.TestCase):
    def assert_mount(self, pod):
        volume = next(v for v in pod["spec"]["volumes"] if v["name"] == "signatures")
        self.assertEqual(volume["csi"]["driver"], "gcsfuse.csi.storage.gke.io")
        self.assertIs(volume["csi"]["readOnly"], True)
        self.assertEqual(volume["csi"]["volumeAttributes"]["bucketName"], "test-signatures")
        mount = next(v for v in pod["spec"]["containers"][0]["volumeMounts"] if v["name"] == "signatures")
        self.assertIs(mount["readOnly"], True)
        self.assertEqual(mount["mountPath"], "/mnt/signatures")
        self.assertEqual(pod["metadata"]["annotations"]["gke-gcsfuse/volumes"], "true")
        self.assertEqual(pod["metadata"]["annotations"]["gke-gcsfuse/cpu-limit"], "0")
        self.assertEqual(pod["metadata"]["annotations"]["gke-gcsfuse/memory-limit"], "256Mi")

    def assert_no_mount(self, pod):
        self.assertNotIn("signatures", [v["name"] for v in pod["spec"]["volumes"]])
        self.assertNotIn("gke-gcsfuse/volumes", pod.get("metadata", {}).get("annotations", {}))

    def test_deployment_default_off(self):
        deployment = next(d for d in render("api-deployment", {}) if d["kind"] == "Deployment")
        self.assert_no_mount(pod_spec(deployment))

    def test_deployment_read_only(self):
        values = {"signatureVolume": {"enabled": True, "bucketName": "test-signatures", "cpuRequest": "25m", "memoryRequest": "64Mi"}}
        deployment = next(d for d in render("api-deployment", values) if d["kind"] == "Deployment")
        pod = pod_spec(deployment)
        self.assert_mount(pod)
        self.assertEqual(pod["metadata"]["annotations"]["gke-gcsfuse/memory-request"], "64Mi")

    def test_deployment_requires_bucket(self):
        with self.assertRaises(subprocess.CalledProcessError):
            render("api-deployment", {"signatureVolume": {"enabled": True}})

    def test_cron_mount_is_uniform(self):
        values = {
            "signatureVolume": {"enabled": True, "bucketName": "test-signatures"},
            "podAnnotations": {"example.com/existing": "kept"},
            "cronjobs": [
                {"name": "SyncSignatures", "schedule": "0 0 * * *"},
                {"name": "OtherJob", "schedule": "0 0 * * *"},
            ],
        }
        jobs = [d for d in render("api-job-cronjob", values) if d["kind"] == "CronJob"]
        self.assertEqual(len(jobs), 2)
        for job in jobs:
            self.assert_mount(pod_spec(job))
            self.assertEqual(pod_spec(job)["metadata"]["annotations"]["example.com/existing"], "kept")

    def test_cron_default_off(self):
        values = {"cronjobs": [{"name": "OtherJob", "schedule": "0 0 * * *"}]}
        job = next(d for d in render("api-job-cronjob", values) if d["kind"] == "CronJob")
        self.assert_no_mount(pod_spec(job))

    def test_cron_requires_bucket(self):
        values = {"signatureVolume": {"enabled": True}, "cronjobs": [{"name": "SyncSignatures", "schedule": "0 0 * * *"}]}
        with self.assertRaises(subprocess.CalledProcessError):
            render("api-job-cronjob", values)


if __name__ == "__main__":
    unittest.main()
