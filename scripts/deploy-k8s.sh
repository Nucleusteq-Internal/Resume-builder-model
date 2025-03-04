#!/bin/sh
cd $K8S_YAML_DIR || exit
curl -s -o kustomize --location https://github.com/kubernetes-sigs/kustomize/releases/download/v3.1.0/kustomize_3.1.0_linux_amd64
chmod u+x ./kustomize
./kustomize edit set image image_name=$IMAGE_NAME && ./kustomize build .
kubectl apply -k ./
# Verify deployment
kubectl rollout status deployment/resume-builder-model-api
# List Public IP of cluster
kubectl get services -o wide -n plasma-namespace
kubectl get ingress -n plasma-namespace
kubectl get deployment -n plasma-namespace