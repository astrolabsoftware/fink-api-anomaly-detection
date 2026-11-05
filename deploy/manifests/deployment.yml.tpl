apiVersion: apps/v1
kind: Deployment
metadata:
  name: log-anomaly-detection-api-${SERVICE}
  namespace: ${NAMESPACE}
spec:
  replicas: ${REPLICAS}
  selector:
    matchLabels:
      app: log-anomaly-detection-api-${SERVICE}
  template:
    metadata:
      labels:
        app: log-anomaly-detection-api-${SERVICE}
    spec:
      imagePullSecrets:
        - name: gitlab-registry
      containers:
        - name: api
          image: ${IMAGE}
          imagePullPolicy: Always
          envFrom:
            - secretRef:
                name: fink-api-env-${SERVICE}
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          startupProbe:
            httpGet:
              path: /health
              port: http
            periodSeconds: 10
            failureThreshold: 60
          readinessProbe:
            httpGet:
              path: /health
              port: http
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: http
            periodSeconds: 20
