#!/usr/bin/env bash
set -euo pipefail

if [[ $(id -u) -eq 0 ]]; then
    echo "Run this script as the regular user that will administer k3s, not as root." >&2
    exit 1
fi

for command in dnf sudo curl; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "This script requires '$command'." >&2
        exit 1
    fi
done

sudo dnf install -y git curl firewalld
sudo systemctl enable --now firewalld

# K3s uses two internal networks (10.42.0.0/16 and 10.43.0.0/16) by default
for cidr in 10.42.0.0/16 10.43.0.0/16; do
    sudo firewall-cmd --permanent --zone=trusted --add-source="$cidr"
done
sudo firewall-cmd --permanent --zone=public --add-service=http
sudo firewall-cmd --permanent --zone=public --add-service=https
sudo firewall-cmd --reload

curl -sfL https://get.k3s.io | sudo sh -

# regular user for kubectl access
mkdir -p "$HOME/.kube"
sudo cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"
chmod 600 "$HOME/.kube/config"

shell_rc="$HOME/.bashrc"
touch "$shell_rc"
if ! grep -Fqx 'export KUBECONFIG="$HOME/.kube/config"' "$shell_rc" 2>/dev/null; then
    printf '\nexport KUBECONFIG="$HOME/.kube/config"\n' >> "$shell_rc"
fi

echo "k3s is installed. Run 'source ~/.bashrc' and then 'kubectl get nodes'."
