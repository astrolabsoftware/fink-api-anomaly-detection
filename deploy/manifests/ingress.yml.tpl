apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: log-anomaly-detection-api-${SERVICE}
  namespace: ${NAMESPACE}
  annotations:
    traefik.ingress.kubernetes.io/router.middlewares: ${NAMESPACE}-strip-${SERVICE}-prefix@kubernetescrd
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - ${DOMAIN}
      secretName: fink-api-tls
  rules:
    - host: ${DOMAIN}
      http:
        paths:
          - path: /${SERVICE}
            pathType: Prefix
            backend:
              service:
                name: log-anomaly-detection-api-${SERVICE}
                port:
                  number: 8000
