# Administrator cluster-resource hand-over

**Minimum hand-over chart version: 0.7.0.** Earlier versions do not support
`rbac.keep`. Defaults remain `rbac.create: true`, `rbac.keep: false` and
`crds.install: true`.

The administrator first upgrades the existing release with `rbac.create=true`
and `rbac.keep=true`, preserving its release identity, overrides, runtime service
account and **existing** `crds.install` setting. Verify keep on all four RBAC
objects in the **stored release manifest**, not merely live metadata.

The CRD has its own `helm.sh/resource-policy: keep`, independent of `rbac.keep`.
It is rendered from `templates/crd.yaml`, **not** Helm's special `crds/` directory,
so it participates in ordinary upgrade tracking. Before disabling installation,
verify keep on the previously stored CRD manifest and live CRD. Inventory its UID,
schema and existing custom-resource metadata/counts without reading credentials.
A release that never installed the CRD (currently Stage) must not try to create or
adopt another release's CRD.

After exercising the exact Helm client's retention behavior, the administrator
upgrades with `rbac.create=false` and `crds.install=false`. Keep must already be in
the previous tracked manifests; a single-step keep-and-omit cannot establish it.
Verify retained RBAC/CRD UIDs, rules, bindings, schema, custom resources and runtime
behavior remain unchanged, and the application release no longer tracks them.

Import the retained objects into **infrastructure-config Tofu** using its
Kubernetes-provider resources in the same root family as `rbac.tf`. The approved
owner is infrastructure bootstrap, not another application release. Review import
plans showing **zero remote changes**; chart flags/keep are not import or ownership
transfer. Application CI must not acquire cluster-resource writes.

RBAC and CRD are ordinary templates without hooks or hook-delete-policy; keep is
not a hook cleanup setting. Exercise omission and uninstall without losing CRD,
custom resources or runtime RBAC before production. Administrator rollback/history
policy must prevent old application revisions reclaiming these objects. Never
use deletion/recreation, force-adoption or pruning as a shortcut. Deployment
identity and infrastructure operation documentation belongs in the infrastructure
root; this chart change does not claim live adoption or runtime verification.

Kubernetes service accounts remain application-owned. A retained binding can grant
permissions again if its subject name is reused. Before permanently retiring the
application or reassigning that KSA name, the administrator must revoke/retire the
bootstrap binding through infrastructure review. Do not grant application CI
cluster deletion rights or silently retain application KSAs as bootstrap objects.
