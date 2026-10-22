# Administrator RBAC hand-over

**Minimum hand-over chart version: 0.8.0.** Earlier versions do not support
`rbac.keep`. Defaults remain `rbac.create: true`, `rbac.keep: false`.

The administrator must first upgrade the existing release with `rbac.create=true`
and `rbac.keep=true`, preserving its release name, namespace, overrides and runtime
service account. Verify `helm.sh/resource-policy: keep` on both the ClusterRole
and ClusterRoleBinding in the **stored release manifest**, not only live metadata.
Review the binding subject: it now follows the workload's service-account helper;
custom/external service-account values previously still bound the fullname.

Only after validating retention with the exact Helm client may the administrator
upgrade with `rbac.create=false`. Keep must already exist in the previous manifest;
setting keep and disabling creation in one upgrade does not stage retention.
Verify both objects remain with unchanged UIDs, rules, subjects and runtime access.

The administrator then imports the retained objects into **infrastructure-config
Tofu**, using its Kubernetes-provider resources in the same root family as
`rbac.tf`. Keep names and immutable roleRefs; import/adoption is not achieved by
this chart switch or annotation. Review an import plan showing **zero remote
changes** before any separately authorized infrastructure operation. Application
CI never owns this bootstrap or receives cluster-resource permissions.

These are ordinary templates, not hooks: no hook-delete-policy applies. Exercise
omission and uninstall retention with the actual Helm version before production
hand-over; render tests are not that proof. An old application rollback can reclaim
cluster resources, so administrator rollback/history policy must exclude such
revisions. Do not delete/recreate, force-adopt, or prune these resources to transfer
ownership. Deployment identity and infrastructure operation documentation belongs
in the infrastructure root.

Kubernetes service accounts remain application-owned. A retained binding can grant
permissions again if its subject name is reused. Before permanently retiring the
application or reassigning that KSA name, the administrator must revoke/retire the
bootstrap binding through infrastructure review. Do not grant application CI
cluster deletion rights or silently retain application KSAs as bootstrap objects.
