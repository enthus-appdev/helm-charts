{{/*
Expand the name of the chart.
*/}}
{{- define "api-deployment.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "api-deployment.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "api-deployment.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "api-deployment.labels" -}}
helm.sh/chart: {{ include "api-deployment.chart" . }}
{{ include "api-deployment.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "api-deployment.selectorLabels" -}}
app.kubernetes.io/name: {{ include "api-deployment.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "api-deployment.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "api-deployment.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
The tag Traefik injects and the HSO matches, so the shared interceptor can still route a
strip-prefixed service after its path prefix is gone. Single-sourced so the two can't drift.
*/}}
{{- define "api-deployment.scaleToZero.routingHeaderName" -}}X-Keda-Target{{- end -}}

{{- define "api-deployment.scaleToZero.validate" -}}
{{- if .Values.scaleToZero.enabled -}}
{{- $stz := .Values.scaleToZero -}}
{{- if not $stz.hosts }}{{ fail "scaleToZero.enabled requires scaleToZero.hosts" }}{{- end -}}
{{- if not $stz.interceptor }}{{ fail "scaleToZero.enabled requires scaleToZero.interceptor (name + namespace)" }}{{- end -}}
{{- if not $stz.interceptor.name }}{{ fail "scaleToZero.interceptor.name is required" }}{{- end -}}
{{- if not $stz.interceptor.namespace }}{{ fail "scaleToZero.interceptor.namespace is required" }}{{- end -}}
{{- if and $stz.stripPrefix (not $stz.pathPrefixes) }}{{ fail "scaleToZero.stripPrefix requires pathPrefixes (the prefixes to strip)" }}{{- end -}}
{{- if .Values.ingress.enabled }}{{ fail "scaleToZero and ingress are mutually exclusive — disable ingress" }}{{- end -}}
{{- if .Values.autoscaling.enabled }}{{ fail "scaleToZero scales replicas via KEDA — disable autoscaling (HPA)" }}{{- end -}}
{{- end -}}
{{- end -}}
