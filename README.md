# enthus Helm Charts

Helm charts maintained by enthus GmbH, published via GitHub Pages.

## Usage

Add the Helm repository:

```shell
helm repo add enthus https://enthus-appdev.github.io/helm-charts
helm repo update
```

Search available charts:

```shell
helm search repo enthus
```

Install a chart:

```shell
helm install my-release enthus/<chart-name>
```

## Available charts

| Chart | Description |
|---|---|
| [api-deployment](charts/api-deployment) | Deployment chart for the NegSoft API service |
| [api-subscription](charts/api-subscription) | Deployment chart for the NegSoft subscription API workload |
| [default](charts/default) | Default chart scaffold from `helm create` |
| [negsoft-operator](charts/negsoft-operator) | Kubernetes operator for managing NegSoft user subscriptions |
| [nexus](charts/nexus) | Internal admin UI for database operations, configuration, and cross-environment replication |
| [pim-cronjob](charts/pim-cronjob) | Reusable Kubernetes CronJob chart for Product Information Management (PIM) workloads — importers, exporters, and generators |

## Contributing

Charts are linted on every push and pull request. Release tarballs are published automatically via [chart-releaser-action](https://github.com/helm/chart-releaser-action) when version tags are pushed to `main`.
