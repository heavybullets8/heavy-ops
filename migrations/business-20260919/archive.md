# Migration staging archive

All 227 staged migration files were encrypted and verified by SHA-256 against the original bytes before their plaintext copies were removed. The user's accounting-work backup was preserved separately.

Encrypted archive: `/home/heavy/.local/share/bighorn-byte/migrations/2026-09-19/migration-staging-20260919.tar.age`.

The adjacent `archive-verification.json` records its checksum and per-file verification. The decryption identity is in the talos 1Password vault item `bighorn-byte-migration-archive-key-20260919`; no plaintext identity remains in the migration staging directory.

This retained migration archive supplements the cluster's normal offsite base backups and WAL recovery. It is not the recurring production backup mechanism.
