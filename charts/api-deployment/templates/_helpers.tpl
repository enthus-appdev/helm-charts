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

{{/*
Render a Kubernetes probe, retaining the historical HTTP default when no handler
is specified. Keep enabled chart-only; all remaining fields are native probe fields.
*/}}
{{- define "api-deployment.probe" -}}
{{- $probe := omit .probe "enabled" -}}
{{- if .probe.enabled -}}
{{- $handlers := 0 -}}
{{- range $handler := list "httpGet" "grpc" "tcpSocket" "exec" -}}
{{- if hasKey $probe $handler -}}
{{- $handlers = add1 $handlers -}}
{{- end -}}
{{- end -}}
{{- if gt (int $handlers) 1 -}}
{{- fail (printf "%s must specify exactly one probe handler" .name) -}}
{{- end -}}
{{- if eq (int $handlers) 0 -}}
{{- $_ := set $probe "httpGet" (dict "path" "/" "port" "http") -}}
{{- end -}}
{{- if hasKey $probe "grpc" -}}
{{- $port := $probe.grpc.port -}}
{{- if not (or (kindIs "float64" $port) (kindIs "int64" $port) (kindIs "int" $port)) -}}
{{- fail (printf "%s.grpc.port must be an integer between 1 and 65535" .name) -}}
{{- end -}}
{{- if or (lt (float64 $port) 1.0) (gt (float64 $port) 65535.0) (ne (float64 $port) (float64 (int $port))) -}}
{{- fail (printf "%s.grpc.port must be an integer between 1 and 65535" .name) -}}
{{- end -}}
{{- end -}}
{{ .name }}:
{{- toYaml $probe | nindent 2 }}
{{- end -}}
{{- end -}}
