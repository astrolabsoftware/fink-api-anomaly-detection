apiVersion: v1
kind: Service
metadata:
  name: log-anomaly-detection-api-${SERVICE}
  namespace: ${NAMESPACE}
spec:
  type: ClusterIP
  selector:
    app: log-anomaly-detection-api-${SERVICE}
  ports:
    - name: http
      port: 8000
      targetPort: http
      protocol: TCP
