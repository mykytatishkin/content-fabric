# Baseline rootkit scan — 2026-05-09

Run as part of P4 hardening after the May 2026 Redis-RCE incident, to confirm no persistent foothold remained after `/etc/cron*` cleanup and Redis lockdown.

## rkhunter 1.4.6

```
$ rkhunter --check --skip-keypress --report-warnings-only --nocolors
```

Result: **4 warnings, all false-positives or known-config items.**

1. `/usr/bin/lwp-request has been replaced by a script` — legitimate; that binary IS a Perl script in this Debian package version. Property update would silence it.
2. Apache shared-memory segment 1.2 MB > rkhunter's 1.0 MB threshold — legitimate Apache scoreboard size.
3. `SSH PermitRootLogin: yes vs rkhunter expected no` — known unresolved hardening item (root-via-password preserved per team's request, see security report).
4. `/dev/shm` segments owned by postgres + Python multiprocessing semaphores (`sem.loky-*`, `sem.mp-*`, `PostgreSQL.*`) — legitimate; no executable content.

No actual rootkit indicators triggered (no hidden binaries, no preload hijack, no suspicious SUID, no port-knocking shellcode, no kernel module mismatches).

## chkrootkit (latest from apt)

```
$ chkrootkit -q
```

Result: **`INFECTED: Possible Malicious Linux.Xor.DDoS installed` — confirmed false-positive.**

The signature lists files under `/tmp/snap-private-tmp/snap.chromium/tmp/.../WasmTtsEngine/...` (Chromium snap's WebAssembly TTS engine). chkrootkit's Linux/Xor.DDoS heuristic flags directories containing many `.html`/`.js`/`.wasm`/`.pb` files written by a single PID — Chromium snap matches that pattern. Verified by:

1. None of the canonical Linux/Xor.DDoS payload paths exist (`/lib/libudev.so` is the legitimate one from libudev1, `/etc/cron.hourly/gcc.sh` does not exist, no `/usr/bin/.<random>` files).
2. The flagged files are normal Chromium runtime data, owned by `root:root` with timestamps matching snap install.
3. /etc/cron* directories are clean — `auditctl -k cff-cron` would catch any new persistence attempt.

## Conclusion

Server is clean of known rootkits as of 2026-05-09 19:57 MSK. Baseline established. Weekly automated re-scan scheduled at `/etc/cron.weekly/cff-rkhunter` writing to `/var/log/rkhunter/weekly-*.log`.
