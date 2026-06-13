{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "healthcheck.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "healthcheck.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "healthcheck.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "healthcheck.selectorLabels" -}}
app.kubernetes.io/name: {{ include "healthcheck.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "healthcheck.labels" -}}
helm.sh/chart: {{ include "healthcheck.chart" . }}
{{ include "healthcheck.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "healthcheck.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "healthcheck.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end -}}

{{/*
Pod template spec shared by the CronJob and the on-demand Job, so an ad-hoc
`kubectl create job --from=cronjob/...` and the scheduled run are identical.
The probe image is self-contained (browser + probe baked in); the pod only
supplies config via env and a writable /tmp for the read-only root filesystem.
*/}}
{{- define "healthcheck.podSpec" -}}
serviceAccountName: {{ include "healthcheck.serviceAccountName" . }}
automountServiceAccountToken: false
restartPolicy: Never
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  seccompProfile:
    type: RuntimeDefault
containers:
  - name: probe
    image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
    imagePullPolicy: {{ .Values.image.pullPolicy }}
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
    env:
      # readOnlyRootFilesystem: keep all writes (browser profile, cache) in /tmp.
      - name: HOME
        value: /tmp
      - name: ENV_LABEL
        value: {{ .Values.envLabel | quote }}
      - name: REPORT_ON
        value: {{ .Values.reportOn | quote }}
      - name: SOURCE_IP
        value: {{ .Values.sourceIp | quote }}
      - name: COOKIE_NAME
        value: {{ .Values.cookieName | quote }}
      - name: EXPECTED_SHA
        value: {{ .Values.expectedSha | quote }}
      {{- $targets := .Values.targets | default dict }}
      - name: API_BASE
        value: {{ $targets.apiBase | default "" | quote }}
      - name: GUI_BASE
        value: {{ $targets.guiBase | default "" | quote }}
      - name: LEGACY_BASE
        value: {{ $targets.legacyBase | default "" | quote }}
      - name: REPLICA_BASES
        value: {{ join "," ($targets.replicas | default (list)) | quote }}
      - name: SHOT
        value: /tmp/render.png
      {{- $discord := .Values.discord | default dict }}
      {{- if $discord.webhookSecretName }}
      - name: DISCORD_WEBHOOK_URL
        valueFrom:
          secretKeyRef:
            name: {{ $discord.webhookSecretName | quote }}
            key: {{ $discord.webhookSecretKey | default "webhook-url" | quote }}
            optional: false
      {{- end }}
      {{- $portal := .Values.portal | default dict }}
      - name: PORTAL_API_BASE
        value: {{ $portal.apiBase | default "" | quote }}
      {{- if $portal.credentialsSecretName }}
      - name: PORTAL_EMAIL
        valueFrom:
          secretKeyRef:
            name: {{ $portal.credentialsSecretName | quote }}
            key: {{ $portal.credentialsEmailKey | default "email" | quote }}
            optional: false
      - name: PORTAL_PASSWORD
        valueFrom:
          secretKeyRef:
            name: {{ $portal.credentialsSecretName | quote }}
            key: {{ $portal.credentialsPasswordKey | default "password" | quote }}
            optional: false
      {{- end }}
    resources:
      {{- toYaml .Values.resources | nindent 6 }}
    volumeMounts:
      - name: tmp
        mountPath: /tmp
volumes:
  - name: tmp
    emptyDir: {}
{{- end -}}
