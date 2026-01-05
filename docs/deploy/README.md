# Deployment

This guide explains how to deploy the `virt-joiner` component using Kustomize on an OpenShift or Kubernetes cluster.

## Prerequisites

- Access to the target cluster with `oc` or `kubectl`
- Kustomize installed (or use `oc kustomize` on OpenShift)
- The base and overlay directories from this repository cloned locally

## Update Secrets

Edit the secrets file for your specific cluster to provide the required FreeIPA credentials and domain information.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: virt-joiner-config
  namespace: openshift-cnv
type: Opaque
stringData:
  IPA_HOST: "ipa.example.com"
  IPA_USER: "admin"
  IPA_PASS: "Secret123!"
  DOMAIN: "example.com"
```

## Apply the Kustomization

Navigate to your cluster-specific overlay and apply the resources.
For OpenShift clusters:

```bash
cd overlays/cluster1
oc apply -k .
```

This will create or update the necessary resources in the openshift-cnv namespace.

## Verification

And check that the associated pods are running:
```
oc get pods -n openshift-cnv
```