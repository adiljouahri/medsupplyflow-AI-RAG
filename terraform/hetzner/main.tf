terraform {
  required_version = ">= 1.5.0"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.48.0"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

variable "hcloud_token" {
  type        = string
  sensitive   = true
  description = "Hetzner Cloud API Token"
}

variable "server_type" {
  type        = string
  default     = "cpx31" # 4 vCPU, 8 GB RAM (excellent for AI microservices + Chroma)
  description = "Hetzner Cloud Server Type"
}

variable "server_location" {
  type        = string
  default     = "fsn1" # Falkenstein, Germany (GDPR-compliant)
  description = "Datacenter location (fsn1, nbg1, hel1)"
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key to access the deployment VM"
}

resource "hcloud_ssh_key" "deployer" {
  name       = "medsupplyflow-deployer"
  public_key = var.ssh_public_key
}

resource "hcloud_firewall" "medsupply_fw" {
  name = "medsupplyflow-firewall"

  rule {
    direction = "in"
    protocol  = "tcp"
    port      = "22"
    source_ips = [
      "0.0.0.0/0",
      "::/0"
    ]
  }

  rule {
    direction = "in"
    protocol  = "tcp"
    port      = "80"
    source_ips = [
      "0.0.0.0/0",
      "::/0"
    ]
  }

  rule {
    direction = "in"
    protocol  = "tcp"
    port      = "443"
    source_ips = [
      "0.0.0.0/0",
      "::/0"
    ]
  }
}

resource "hcloud_server" "medsupply_node" {
  name        = "medsupplyflow-production-node"
  image       = "ubuntu-24.04"
  server_type = var.server_type
  location    = var.server_location
  ssh_keys    = [hcloud_ssh_key.deployer.id]
  firewall_ids = [hcloud_firewall.medsupply_fw.id]

  user_data = <<-EOF
              #!/bin/bash
              apt-get update -y
              apt-get install -y ca-certificates curl gnupg
              install -m 0755 -d /etc/apt/keyrings
              curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
              chmod a+r /etc/apt/keyrings/docker.asc
              echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
              apt-get update -y
              apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
              systemctl enable docker
              systemctl start docker
              mkdir -p /opt/medsupplyflow
              EOF

  labels = {
    environment = "production"
    project     = "medsupplyflow-ai"
  }
}

output "server_ipv4" {
  value       = hcloud_server.medsupply_node.ipv4_address
  description = "Public IPv4 address of the Hetzner node"
}
