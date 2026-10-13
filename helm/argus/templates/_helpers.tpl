{{/* Release-scoped base name, e.g. "argus". */}}
{{- define "argus.fullname" -}}
{{- if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "argus.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: argus
{{- end -}}

{{/* Selector labels for one component: pass (dict "ctx" $ "component" "backend"). */}}
{{- define "argus.selectorLabels" -}}
app.kubernetes.io/name: {{ .ctx.Chart.Name }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Image for one component. A component may pin its own tag (simulator.image.tag);
     otherwise every component shares image.tag, falling back to the chart's appVersion. */}}
{{- define "argus.image" -}}
{{- $own := "" -}}
{{- with (index .ctx.Values .component) -}}{{- with .image -}}{{- $own = .tag -}}{{- end -}}{{- end -}}
{{- printf "%s/argus-%s:%s" .ctx.Values.image.registry .component ($own | default .ctx.Values.image.tag | default .ctx.Chart.AppVersion) -}}
{{- end -}}

{{- define "argus.backendName" -}}{{ include "argus.fullname" . }}-backend{{- end -}}
{{- define "argus.frontendName" -}}{{ include "argus.fullname" . }}-frontend{{- end -}}
{{- define "argus.postgresName" -}}{{ include "argus.fullname" . }}-postgres{{- end -}}

{{- define "argus.dbSecretName" -}}
{{- .Values.postgres.existingSecret | default (printf "%s-db" (include "argus.fullname" .)) -}}
{{- end -}}

{{/* Database env for the backend and its migration init container. Kubernetes expands
     $(POSTGRES_PASSWORD) inside DATABASE_URL because it is defined first. */}}
{{- define "argus.databaseEnv" -}}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "argus.dbSecretName" . }}
      key: password
- name: DATABASE_URL
  value: {{ printf "postgresql+psycopg://%s:$(POSTGRES_PASSWORD)@%s:5432/%s" .Values.postgres.username (include "argus.postgresName" .) .Values.postgres.database | quote }}
{{- end -}}

{{/* Hardened container defaults shared by every workload. */}}
{{- define "argus.containerSecurity" -}}
allowPrivilegeEscalation: false
capabilities:
  drop: ["ALL"]
{{- end -}}
