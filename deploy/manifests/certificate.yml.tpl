apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: fink-api-tls
  namespace: ${NAMESPACE}
spec:
  secretName: fink-api-tls
  issuerRef:
    name: letsencrypt-production
    kind: ClusterIssuer
  dnsNames:
    - ${DOMAIN}
