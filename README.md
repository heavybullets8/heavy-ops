# My Home Operations Repository

_... managed with Flux, SOPS, and GitHub Actions_ 🤖

---

## 📖 Overview

This repository contains the configuration for my home infrastructure and
Kubernetes cluster. I follow Infrastructure as Code (IaC) and GitOps practices
using tools like [Talos Linux](https://www.talos.dev/),
[Kubernetes](https://kubernetes.io/), [Flux](https://github.com/fluxcd/flux2),
[SOPS](https://github.com/mozilla/sops), and
[GitHub Actions](https://github.com/features/actions).

---

## ⛵ Kubernetes

My Kubernetes cluster is deployed with [Talos Linux](https://www.talos.dev/) on
a single powerful node. For persistent storage, I use
[OpenEBS HostPath](https://github.com/openebs/dynamic-localpv-provisioner) and
[OpenEBS ZFS](https://github.com/openebs/zfs-localpv).

### Core Components

- [cert-manager](https://github.com/cert-manager/cert-manager): Automates the
  creation and management of TLS certificates.
- [cilium](https://github.com/cilium/cilium): Provides networking, security, and
  observability for the cluster.
- [external-secrets](https://github.com/external-secrets/external-secrets):
  Syncs secrets from external APIs into Kubernetes.
- [ingress-nginx](https://github.com/kubernetes/ingress-nginx): Acts as a
  reverse proxy and load balancer for Kubernetes services.
- [sops](https://github.com/mozilla/sops): Encrypts and manages secrets within
  Git.
- [kopiur](https://github.com/home-operations/kopiur): Backs up application PVCs
  to TrueNAS and R2.

### GitOps and Automation

[Flux](https://github.com/fluxcd/flux2) monitors the `kubernetes` directory in
this repository and ensures the cluster state matches the configuration. Changes
pushed to the main branch are automatically applied to the cluster.

I use [GitHub Actions](https://github.com/features/actions) for continuous
integration and deployment workflows, leveraging self-hosted GitHub runners
within the cluster for execution.

---

## ☁️ Cloud Dependencies

While the core infrastructure is self-hosted, I utilize a few cloud services for
critical functionalities:

| Service                                   | Purpose                                           | Cost        |
| ----------------------------------------- | ------------------------------------------------- | ----------- |
| [Migadu](https://migadu.com/)             | Email hosting (also use this for business things) | ~$90/year   |
| [Cloudflare](https://www.cloudflare.com/) | DNS, domain management and R2 bucket              | ~$8/month   |
| [GitHub](https://github.com/)             | Repository hosting and CI/CD pipelines            | Free        |
| [Pushover](https://pushover.net/)         | Application and system notifications              | $5 one-time |

---

## 🌐 DNS and Networking

My network is managed using a
[UniFi Dream Machine Pro Max](https://store.ui.com/us/en/category/cloud-gateways-large-scale/products/udm-pro-max),
which serves as the router, firewall, and DNS server for my home network.

---

## 🔧 Hardware

### Kubernetes Node

- **Case**: Fractal Design Torrent
- **Motherboard**: ASUS Pro WS TRX50-SAGE
- **CPU**: AMD Ryzen™ Threadripper™ 7970X (32 cores, 64 threads)
- **RAM**: 192 GB (G.SKILL Zeta R5 NEO Series DDR5, 4× 48 GB)
- **Boot Drive**: Intel Optane 905p 960 GB (formatted with XFS)
- **Persistent Volumes**:
  - 4× Intel Optane 905p 1.5 TB (configured as 2 mirrored VDEVs using ZFS)
  - **Adapter**: GLOTRENDS PU41 Quad U.2 SSD to PCIe 4.0 X16
- **GPU**: NVIDIA RTX 4000 ADA
- **Cooling**: SilverStone Technology XE360-TR5 AIO cooler
- **Power Supply**: FSP Twins Pro 900 W
- **Network**:
  - Mellanox X5 ADAT 25 Gb

### NAS Server

- **CPU**: AMD Ryzen Threadripper 3960X (24 cores, 48 threads)
- **RAM**: 256 GB
- **Storage**:
  - **HDDs**: 12× 18 TB WD Red Pro (configured as 2 VDEVs in RAIDZ2)
- **GPU**: NVIDIA Quadro P2200
- **Power Supply**: FSP Twins Pro 900 W
- **Network**:
  - Mellanox X5 ADAT 25 Gb

---

## 🤝 Acknowledgments

I would like to express my gratitude to the following resources and communities
that have significantly contributed to my home operations setup:

- **[kubesearch.dev](https://kubesearch.dev/)**: Provided configuration examples
  during my setup process.
- **[onedr0p's cluster template](https://github.com/onedr0p/cluster-template)**:
  Served as a bootstrap for my server configuration.
- **[Home Operations Discord Community](https://discord.gg/home-operations)**: A
  supportive community where I received valuable advice and shared experiences.

## Bighorn Byte environments

The production web app, outreach workers and crawler use one pinned Bighorn
Byte web image. The web release runs database migrations before the dependent
workers roll out.

The caller demonstration at `development.bighornbyte.com` uses the same image
with separate demo/admin databases and the `bighorn-byte-development` 1Password
item. It contains fictional dealers, has no provider credentials or workers,
and limits outbound network access to DNS and PostgreSQL. Its login is stored
in that item. Keep development values out of the production runtime items.
