apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: strip-${SERVICE}-prefix
  namespace: ${NAMESPACE}
spec:
  stripPrefix:
    prefixes:
      - /${SERVICE}
