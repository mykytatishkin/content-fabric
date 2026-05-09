# CFF auditd — security audit logging

End-to-end forensic logging for the CFF prod host: every change to identity, SSH config, firewall rules, cron, systemd units, and CFF code/secrets is recorded by Linux's audit subsystem and shipped to Loki for queryable retention.

## Layout

| Path | Purpose |
|------|---------|
| `cff-security.rules` | The CFF rule set. Deployed to `/etc/audit/rules.d/cff-security.rules` on the prod host. |
| `auditd.conf` | Daemon tuning (50MB × 10 logs = 500MB on-disk cap). Deployed to `/etc/audit/auditd.conf`. |

## Threat model the rules address

Three drivers from the May 2026 incident:

1. **Public Redis → cron-based RCE** — attacker wrote cron entries via Redis WRITE, ran a `b.9-9-8.com` cryptominer. Rules tag every change to `/etc/cron*` and `/var/spool/cron/` as `cff-cron`.
2. **SSH brute-force at scale** — 286k failed attempts over the visible window, 44k IPs banned. Rules track every `/etc/ssh/sshd_config` change (`cff-ssh-config`) and `/root/.ssh/` write (`cff-ssh-keys`).
3. **Suspicious 04:00 root SSH from external VPS (185.209.20.126)** — auditd USER_ACCT events make the source IP queryable per login.

## Tag taxonomy (`-k` keys)

| Tag | What it captures |
|-----|------------------|
| `cff-identity` | `/etc/passwd /etc/shadow /etc/group /etc/security/` |
| `cff-sudoers` | `/etc/sudoers /etc/sudoers.d/` |
| `cff-pam` | `/etc/pam.d/` |
| `cff-ssh-config` | `sshd_config` and drop-ins |
| `cff-ssh-keys` | `/root/.ssh/` |
| `cff-priv-exec` | sudo, su, passwd, chsh, chfn, newgrp, gpasswd executions |
| `cff-priv-launch` | any non-root user transitioning to UID 0 via execve |
| `cff-cron` | system cron + per-user cron |
| `cff-systemd` | `/etc/systemd/system/`, `/lib/systemd/system/`, `/etc/init.d/` |
| `cff-firewall` | `/etc/iptables/` |
| `cff-network` | `/etc/network/`, `/etc/hosts`, `/etc/resolv.conf`, `/etc/nsswitch.conf` |
| `cff-nginx` | `/etc/nginx/` |
| `cff-secrets` | reads/writes of `/opt/content-fabric/.env` |
| `cff-code-critical` | `main.py`, `app/core/security.py`, `app/api/deps.py` |
| `cff-yii-legacy` | `aiyoutube.pbnbots.com/yii` and `protected/` (alarms if Yii re-enabled) |
| `cff-module` | kernel module load/unload (rootkit indicator) |
| `cff-time` | `adjtimex/settimeofday/clock_settime` (anti-tamper) |
| `cff-mount` | `mount` syscall |
| `cff-docker` | `/etc/docker/` |

## Operational queries

`ausearch` on the host (parses raw audit.log):

```bash
# all USER_ACCT events from last 24h
ausearch --start "24 hours ago" -m USER_ACCT

# any change to sudoers in the last week
ausearch -k cff-sudoers --start "1 week ago"

# every sudo invocation with full command
ausearch -k cff-priv-exec -i

# kernel module load/unload (should be ~0)
ausearch -k cff-module
```

**Loki / Grafana** (preferred — survives log rotation, queryable across time):

```logql
# Identity mutations in last 24h
{job="auditd", audit_key=~"cff-identity|cff-sudoers"}

# All SSH login successes by source IP
{job="auditd"} |~ "type=USER_ACCT.*res=success" | regexp `addr=(?P<src_ip>[0-9.]+)`

# CFF code changes
{job="auditd", audit_key="cff-code-critical"}

# Cron persistence attempts
{job="auditd", audit_key="cff-cron"}
```

The dashboard at `/d/cff-security` in Grafana (🛡 CFF — Security Audit) renders all of these as panels.

## Pipeline

```
auditd → /var/log/audit/audit.log
         │
         └─ promtail (job_name: auditd) regex-extracts:
               - audit_type (SYSCALL, USER_ACCT, …)
               - audit_key  (cff-* tag)
               - comm       (the calling binary)
               - src_ip     (addr=… for SSH events)
         │
         └─ Loki (30d retention) → Grafana dashboard cff-security
```

`promtail-config.yml` `auditd` job has the regex stages.

## Re-deployment

```bash
# 1. Edit cff-security.rules in this directory.
# 2. Push to host:
scp cff-security.rules root@46.21.250.43:/etc/audit/rules.d/cff-security.rules
# 3. Reload (no daemon restart needed for rules-only changes):
ssh root@46.21.250.43 'auditctl -D && augenrules --load && auditctl -l | wc -l'
```

If `auditd.conf` changes:

```bash
scp auditd.conf root@46.21.250.43:/etc/audit/auditd.conf
ssh root@46.21.250.43 'service auditd restart'
```

## Gotchas

- **augenrules silently truncates rules at the first non-ASCII character** in comments. Keep all comments plain ASCII.
- **Watching `data/streams/` floods the log** — every ffmpeg tick triggers thousands of events. The Yii archive watch is narrowed to `/yii/` and `/protected/` only.
- **`-p w` rules trigger on inode mutation** (touch updates atime/mtime). Use `-p wa` (write+attr) to also catch chmod/chown.
- **Disk usage**: `auditd.conf` caps `/var/log/audit/` at 500MB (50MB × 10 files). `space_left=200` triggers SYSLOG warning at 200MB free; `admin_space_left=100` SUSPENDs auditd. Tune for your filesystem.

## Who has visibility

Anyone with Grafana access (`/d/cff-security`) can query. The raw audit.log is `root:adm 0640` so the `adm` group is enough; promtail runs as root inside its container and bind-mounts `/var/log` read-only.
