# Capacity note for the application refactor

Snapshot: September 19, 2026, 18:24 UTC. This is current usage, not a peak-load study.

The node has 63.95 allocatable CPU cores and 181.6 GiB ordinary RAM. It used 1.532 cores and 30.4 GiB RAM. Scheduled requests reserved 10.315 cores and 64.8 GiB RAM. There were 123 running pods against a 150-pod limit; memory, disk, and PID pressure were false.

The active business apps used about 1.6 GiB RAM and had no restarts or OOM terminations. The continuous outreach deployment has one replica and processes one job at a time. Start the refactor's throughput work by measuring queue latency and adding two, then four workers, paired with a bounded browser-context semaphore. Keep AI budgets, mail pacing, and idempotency independent of that concurrency.

Review per-pod memory, browser CPU, temporary storage budgets, and Dragonfly reservations against load measurements. Shared TTL caching may help if repeated DNS or page processing becomes significant. The server has enough headroom for these experiments; simply raising idle pod limits does not increase serial-worker throughput.

Tracked in [BIG-141](https://linear.app/bighorn-byte/issue/BIG-141/simplify-bighorn-byte-around-its-self-hosted-runtime).
