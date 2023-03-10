# enthus Helm Charts

## Getting started

Add the Helm charts to your helm command:
```
helm repo add --username <username> --password <access_token> enthus-charts https://gitlab.com/api/v4/projects/42323755/packages/helm/stable
```

If you want to use the experimental/development versions use this one:
```
helm repo add --username <username> --password <access_token> enthus-experimental-charts https://gitlab.com/api/v4/projects/42323755/packages/helm/experimental
```


## Charts

- [api-deployment](charts/api-deployment): Deployment Chart for API
- [default](charts/default): Default Chart created by `helm create`
- [rtf2html](charts/rtf2html): Deployment Chart for RTF to HTML converter
- [sensa](charts/sensa): Deployment Chart for Sensa Bot
- [service-voucher](charts/service-voucher): Deployment Chart for service voucher app
