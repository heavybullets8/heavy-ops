# UpCloud Talos trial

An independent, single-node Chicago cluster for the customer-hosting experiment.
It follows the home cluster's Talos → Kubernetes → Helmfile → Flux workflow.
Its Flux root is `clusters/upcloud-trial/kubernetes`; the home cluster's existing
bootstrap, application root and credentials are separate.

| Component | Trial setting |
| --- | --- |
| Region | UpCloud `us-chi1` |
| Talos node | `STARTER-4xCPU-8GB`, 40-GiB Standard boot disk |
| SSH helper | `STARTER-1xCPU-1GB`, 10-GiB Standard boot disk |
| Talos / Kubernetes | `v1.14.1` / `v1.36.4` |
| Cilium / Flux Operator | `1.20.2` / `0.61.0` |
| Private network | `10.88.0.0/24`; node `.10`, helper `.2` |
| Pods / services | `10.80.0.0/16` / `10.81.0.0/16` |
| Management | SSH through the helper; local ports `15000` and `16443` |
| Time | KVM PTP device `/dev/ptp_kvm` |

There is one schedulable control-plane node. This proves a cloud bootstrap, not
high availability, cross-site replication, fencing, failover or backup recovery.
No business data or production application credentials belong in this cluster.
Persistent database storage and the recovery rehearsal are separate gates.

## Access and bootstrap

`UPCLOUD_TRIAL_STATE` selects a private directory containing `resources.json`,
`bastion.json`, `bastion`, `known_hosts`, `talos/controlplane.yaml`,
`talos/talosconfig` and `kubeconfig`. The observed run defaults to
`/tmp/upcloud-hosting-trial-20261002`. Keep the directory mode `0700`, private
files `0600`, and the credentials out of Git. Preserve a private recovery copy
before clearing `/tmp`.

From the repository root:

```sh
python3 clusters/upcloud-trial/manage.py connect
python3 clusters/upcloud-trial/manage.py version
python3 clusters/upcloud-trial/manage.py status
```

For a newly installed node only, after Talos reports time synchronized:

```sh
python3 clusters/upcloud-trial/manage.py bootstrap
python3 clusters/upcloud-trial/manage.py kubeconfig
python3 clusters/upcloud-trial/manage.py install
```

`install` checks the isolated API endpoint and passes the trial context to
Helmfile. Helmfile and Flux read the same `helm-values.yaml` files. The trial
Git source currently follows `feat/upcloud-talos-trial-20261002`. Keep that branch
while it is in use; when merging, change `instance.sync.ref` to `refs/heads/main`
and reconcile the Flux instance before deleting the branch.

The generated Kubernetes context is `admin@upcloud-trial`. For direct commands,
always pass both its kubeconfig and context. Management connections use mutual
TLS through loopback-only SSH forwards; certificate verification stays enabled.
End the tunnel with `python3 clusters/upcloud-trial/manage.py disconnect`.

## Provider image preparation

The [Talos UpCloud guide](https://docs.siderolabs.com/talos/v1.14/platform-specific-installations/cloud-platforms/upcloud)
uses the UpCloud factory image, Packer, a reusable template and metadata user
data. We tested that sequence through the image write. The account API rejected
template creation with `TRIAL_TEMPLATES_DISABLED`, so this trial uses the same
factory image written to an offline disk instead. A mounted-root write produced
a corrupted kernel; the offline rewrite passed a full byte-range checksum and
booted successfully.

Image schematic: `376567988ad370138ad8b2698212367b8edcb69b5fd68c80be1f2ec7d603b4ba`.

```text
version: v1.14.1
file: upcloud-amd64.raw.xz
compressed SHA-256: 1b2849830f3f6c89a184d0d64e95bdd89c5b01486f6c75f20b1b8c8ac2199621
raw bytes: 11736711168
raw SHA-256: 164761f5be706eecc83635448d5504516935b4359a4e97fd11d950a3a9c1d682
```

The initial provisioning helper defaults to a dry run:

```sh
python3 clusters/upcloud-trial/provision/api.py inventory
python3 clusters/upcloud-trial/provision/api.py network
python3 clusters/upcloud-trial/provision/api.py bastion
python3 clusters/upcloud-trial/provision/api.py talos
```

Create a fresh SSH key and Talos PKI in the private state directory before
provisioning. Generate only `controlplane,talosconfig`, pin both versions above,
use endpoint `https://10.88.0.10:6443`, disk `/dev/vda`, and apply the patches in
this order: `talos-remove-defaults.yaml`, `talos-patch.yaml`,
`time-sync-trial.yaml`. Include API certificate SANs `127.0.0.1,10.88.0.10`.
Validate the generated control-plane configuration in `cloud` mode. Existing
credentials must be restored rather than regenerated for an existing cluster.

`--apply` creates and inventories the selected resource. The Talos target is
initially allocated from Debian; stop it before using its disk. Via the
[UpCloud storage API](https://developers.upcloud.com/1.3/9-storages/), detach the
target's recorded boot volume, attach it to the helper as `virtio:1`, and check
the guest serial against the first 20 hexadecimal UUID characters. Run
`provision/write-image-offline.sh SERIAL` on the helper. It refuses a mounted or
incorrectly identified disk, verifies the compressed source, writes only
`/dev/vdb`, and checks all raw-image bytes. Only after `OFFLINE_IMAGE_VERIFIED`,
detach it from the helper, reattach it to the target as its boot disk at
`virtio:0`, and start the target. Metadata delivers its private Talos config.

Do not reuse the running node's disk for another image preparation operation.
The provisioning helper is scoped to this dated trial and rejects duplicate
resources; it is not a general-purpose production infrastructure manager.

## Trial restrictions and cleanup

This account's observed quota is 6 cores / 12 GiB, larger than the default
published trial. The two retained VMs use 5 cores / 9 GiB. The account has free
credits expiring November 1, 2026 and no paid balance or debt enabled. Recheck
quota and credits before allocating resources. Both VMs and their disks remain
allocated for further testing; stopped VMs and detached disks can still incur
charges against the account's credits.

Public trial ports are restricted. Private Talos TCP 50000 and Kubernetes TCP
6443 through the helper were verified. NTS TCP 4460 timed out. Standard NTP
replies to ephemeral ports also timed out; a helper probe using source port 123
succeeded. The [Talos-supported KVM PTP clock](https://docs.siderolabs.com/talos/v1.14/reference/configuration/network/timesyncconfig)
resolved time synchronization without disabling the boot prerequisite.

For teardown, first save the test evidence and a private recovery copy. Use
`resources.json` plus live API inspection to verify every UUID, title and zone.
Stop and delete the two trial servers, then delete their recorded boot volumes
and the trial SDN network. Verify there are no trial templates, builder disks,
detached volumes or retained IPs. Disconnect the local SSH tunnel and remove
temporary access material when the experiment is finished. A stopped VM is not
a completed cleanup.
