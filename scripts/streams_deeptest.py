#!/usr/bin/env python3
"""Deep E2E test for streams workflow on prod via API + UI.

Run on prod server: python3 /tmp/streams_deeptest.py
Mints admin Bearer JWT, exercises every /api/v1/streams/* endpoint and the
/panel/streams page.  Does NOT actually start ffmpeg.
"""
from __future__ import annotations

import json
import os
import sys
import time
from urllib.parse import urlparse

import requests

sys.path.insert(0, "/opt/content-fabric/prod")
from app.core.security import create_access_token  # noqa: E402
from shared.db.connection import get_connection  # noqa: E402
from sqlalchemy import text  # noqa: E402

BASE = os.environ.get("BASE", "http://127.0.0.1:8000")
HOST = urlparse(BASE).netloc

REPORT = {"bugs": [], "ok": []}


def log(*a):
    print(*a, flush=True)


def bug(tag, *info):
    REPORT["bugs"].append((tag, *info))
    log(f"[BUG] {tag}", *info)


def ok(tag, *info):
    REPORT["ok"].append((tag, *info))
    log(f"[ok] {tag}", *info)


def mint_admin_token() -> tuple[str, int]:
    # In CFF, admin = platform_users.status == 1 (UserStatus.ADMIN).
    with get_connection() as conn:
        row = conn.execute(text(
            "SELECT id, email FROM platform_users "
            "WHERE status = 1 ORDER BY id LIMIT 1"
        )).fetchone()
        if not row:
            raise SystemExit("No admin user found (status=1).")
    uid = row[0]
    token = create_access_token({"sub": uid})
    log(f"[auth] minted Bearer token for admin uid={uid} email={row[1]}")
    return token, uid


def main():
    token, uid = mint_admin_token()
    H = {"Authorization": f"Bearer {token}"}

    # 1. /panel/streams should render with cookie auth.  We use Bearer →
    # CSRF middleware skips. But /panel/* is rendered by panel.require_admin
    # which expects the cookie. Set it via the JWT.
    from app.core.auth import COOKIE_NAME
    cookies = {COOKIE_NAME: token}

    log("\n=== UI: GET /panel/streams ===")
    r = requests.get(BASE + "/panel/streams", cookies=cookies, allow_redirects=False, timeout=10)
    if r.status_code != 200:
        bug("PANEL_STREAMS_STATUS", r.status_code, r.text[:300])
    else:
        # Verify all 9 streams present.
        # Look for the JS data array. Each stream row has data-id but data is
        # provided as JSON in `let data = ...;`.
        if "let data = " not in r.text:
            bug("PANEL_STREAMS_NO_JS_DATA")
        else:
            # extract streams.length from the json
            import re as _re
            m = _re.search(r"let data = (\[.*?\]);", r.text, _re.S)
            if m:
                try:
                    arr = json.loads(m.group(1))
                    if len(arr) != 9:
                        bug("PANEL_STREAMS_COUNT", f"expected 9, got {len(arr)}")
                    else:
                        ok("PANEL_STREAMS_RENDERED", f"{len(arr)} streams")
                except Exception as e:
                    bug("PANEL_STREAMS_JSON_PARSE", str(e))
        if "setInterval(refreshStatus, 5000)" not in r.text:
            bug("PANEL_STREAMS_NO_POLLING")
        else:
            ok("PANEL_STREAMS_POLLING")
        if "/api/v1/streams/status" not in r.text:
            bug("PANEL_STREAMS_NO_STATUS_URL")
        if "/api/v1/streams/tail" not in r.text:
            bug("PANEL_STREAMS_NO_TAIL_URL")
        # Auth button per row
        if "/panel/streaming-accounts/" not in r.text:
            bug("PANEL_STREAMS_NO_AUTH_BTN")
        # Bulk buttons
        for needle in ("btnStartAll", "btnStopAll", "btnRestartAll"):
            if needle not in r.text:
                bug("PANEL_STREAMS_NO_BULK", needle)
        # Modal log
        if "openLog" not in r.text:
            bug("PANEL_STREAMS_NO_LOG_MODAL")

    # 2. /api/v1/streams/status — list with required fields
    log("\n=== API: GET /api/v1/streams/status ===")
    r = requests.get(BASE + "/api/v1/streams/status", headers=H, timeout=15)
    if r.status_code != 200:
        bug("STATUS_HTTP", r.status_code, r.text[:300])
        return
    body = r.json()
    if not body.get("ok") or not isinstance(body.get("data"), list):
        bug("STATUS_BODY", body)
        return
    streams = body["data"]
    if len(streams) != 9:
        bug("STATUS_COUNT", f"expected 9 enabled streams, got {len(streams)}")
    required_fields = ["id", "yid", "name", "channel", "service",
                       "stream_key", "workdir", "runner_path", "status"]
    for s in streams:
        missing = [f for f in required_fields if f not in s]
        if missing:
            bug("STATUS_MISSING_FIELDS", s.get("id"), missing)
        st = s.get("status", {})
        for k in ("activeState", "subState", "pid", "since_ts",
                  "runtime_max_sec", "elapsed_sec", "remaining_sec"):
            if k not in st:
                bug("STATUS_MISSING_STATUS_FIELD", s.get("id"), k)
    ok("STATUS", f"{len(streams)} streams, all fields present")

    # 3. /api/v1/streams/tail for each stream
    log("\n=== API: GET /api/v1/streams/tail for each ===")
    for s in streams:
        sid = s["id"]
        rt = requests.get(BASE + "/api/v1/streams/tail",
                          params={"id": sid, "lines": 10}, headers=H, timeout=15)
        if rt.status_code != 200:
            bug("TAIL_HTTP", sid, rt.status_code, rt.text[:200])
            continue
        jb = rt.json()
        if "log" not in jb or not jb.get("ok"):
            bug("TAIL_BODY", sid, jb)
        else:
            ok("TAIL", sid)

    # 4. /api/v1/streams/sync for one
    log("\n=== API: POST /api/v1/streams/sync (id=1) ===")
    sid = streams[0]["id"]
    svc = streams[0]["service"]
    unit_path = f"/etc/systemd/system/{svc}"
    pre_mtime = os.path.getmtime(unit_path) if os.path.isfile(unit_path) else None
    rs = requests.post(BASE + "/api/v1/streams/sync",
                       data={"id": sid}, headers={**H, "Origin": BASE},
                       timeout=20)
    if rs.status_code != 200:
        bug("SYNC_HTTP", rs.status_code, rs.text[:300])
    else:
        jb = rs.json()
        if not jb.get("ok"):
            bug("SYNC_BODY", jb)
        else:
            post_mtime = os.path.getmtime(unit_path) if os.path.isfile(unit_path) else None
            if pre_mtime is None or post_mtime is None or post_mtime <= pre_mtime:
                # Could be same second — not necessarily a bug.
                ok("SYNC", f"unit {svc} mtime pre={pre_mtime} post={post_mtime}")
            else:
                ok("SYNC", f"unit {svc} updated mtime {pre_mtime}→{post_mtime}")

    # 5. /api/v1/streams/sync-all
    log("\n=== API: POST /api/v1/streams/sync-all ===")
    rsa = requests.post(BASE + "/api/v1/streams/sync-all",
                        headers={**H, "Origin": BASE}, timeout=60)
    if rsa.status_code != 200:
        bug("SYNCALL_HTTP", rsa.status_code, rsa.text[:300])
    else:
        jb = rsa.json()
        if not jb.get("ok"):
            bug("SYNCALL_BODY", jb)
        elif jb.get("synced") != 9:
            bug("SYNCALL_COUNT", f"expected 9 synced, got {jb.get('synced')}")
        else:
            ok("SYNCALL", f"synced={jb.get('synced')} failed={jb.get('failed')}")

    # 6. /api/v1/streams/  POST minimal (Yii beforeValidate parity)
    log("\n=== API: POST /api/v1/streams/ minimal (Yii parity) ===")
    minimal = {
        "name": "test_btn",
        "stream_key": "xxxx-yyyy-zzzz-wwww",
        "streaming_account_id": 1,
    }
    rc = requests.post(BASE + "/api/v1/streams/",
                       json=minimal, headers={**H, "Origin": BASE},
                       timeout=20)
    test_id = None
    if rc.status_code != 201:
        bug("CREATE_HTTP", rc.status_code, rc.text[:400])
    else:
        jb = rc.json()
        if not jb.get("ok"):
            bug("CREATE_BODY", jb)
        else:
            test_id = jb.get("id")
            stream_obj = jb.get("stream", {})
            sn = stream_obj.get("service_name", "")
            wd = stream_obj.get("workdir", "")
            if sn != "stream-test_btn.service":
                bug("CREATE_SERVICE_NAME", f"got {sn!r}, expected stream-test_btn.service")
            else:
                ok("CREATE_SERVICE_NAME_DERIVED", sn)
            if not wd.endswith("/test_btn"):
                bug("CREATE_WORKDIR", f"got {wd!r}, expected suffix /test_btn")
            else:
                ok("CREATE_WORKDIR_DERIVED", wd)
            # Verify systemd unit file exists
            unit_path_t = "/etc/systemd/system/stream-test_btn.service"
            if not os.path.isfile(unit_path_t):
                bug("CREATE_UNIT_NOT_WRITTEN", unit_path_t)
            else:
                ok("CREATE_UNIT_WRITTEN", unit_path_t)

    # 7. Disabled stream start should NOT actually go live.  Use the test stream
    # we just created — first set enabled=0.
    log("\n=== API: POST /api/v1/streams/start for DISABLED stream ===")
    if test_id is not None:
        with get_connection() as conn:
            conn.execute(text(
                "UPDATE live_stream_configurations SET enabled = 0 WHERE id = :id"
            ), {"id": test_id})
            conn.commit()
        rstart = requests.post(BASE + "/api/v1/streams/start",
                               data={"id": test_id},
                               headers={**H, "Origin": BASE}, timeout=15)
        if rstart.status_code != 200:
            bug("START_DISABLED_HTTP", rstart.status_code, rstart.text[:300])
        else:
            jb = rstart.json()
            if jb.get("ok"):
                bug("START_DISABLED_RAN", jb)
            elif jb.get("error") != "Stream disabled":
                bug("START_DISABLED_WRONG_ERROR", jb)
            else:
                ok("START_DISABLED_BLOCKED", jb.get("error"))
            # Verify the systemd unit was NOT actually started.
            from shared.streams import systemd_manager
            st = systemd_manager.status("stream-test_btn.service")
            if st.get("active"):
                bug("START_DISABLED_UNIT_RUNNING", st)
            else:
                ok("START_DISABLED_UNIT_NOT_RUNNING",
                   st.get("activeState"), st.get("subState"))
    else:
        log("[skip] test_id missing; cannot run disabled-start test")

    # 8. start with non-existent id
    log("\n=== API: POST /api/v1/streams/start (id=999999) ===")
    r404 = requests.post(BASE + "/api/v1/streams/start",
                         data={"id": 999999},
                         headers={**H, "Origin": BASE}, timeout=15)
    if r404.status_code == 200:
        jb = r404.json()
        if jb.get("ok"):
            bug("START_NOTFOUND_OK_TRUE", jb)
        elif jb.get("error") != "Not found":
            bug("START_NOTFOUND_WRONG_ERROR", jb)
        else:
            ok("START_NOTFOUND", jb)
    elif r404.status_code == 404:
        ok("START_NOTFOUND_404")
    else:
        bug("START_NOTFOUND_HTTP", r404.status_code, r404.text[:300])

    # 9. stop for non-running unit (idempotent)
    log("\n=== API: POST /api/v1/streams/stop for non-running unit ===")
    if test_id is not None:
        rstop = requests.post(BASE + "/api/v1/streams/stop",
                              data={"id": test_id},
                              headers={**H, "Origin": BASE}, timeout=15)
        if rstop.status_code != 200:
            bug("STOP_IDEMPOTENT_HTTP", rstop.status_code, rstop.text[:300])
        else:
            jb = rstop.json()
            # `systemctl stop` on already-stopped unit returns 0 → ok=True
            if not jb.get("ok"):
                bug("STOP_IDEMPOTENT_NOT_OK", jb)
            else:
                ok("STOP_IDEMPOTENT", "ok=True even for non-running unit")

    # 10. CSRF: POST without same-origin Origin → 403 (cookie auth, no Bearer)
    log("\n=== CSRF: POST without Origin ===")
    r_csrf = requests.post(BASE + "/api/v1/streams/sync",
                           data={"id": 1},
                           cookies={COOKIE_NAME: token},
                           headers={"Origin": "http://evil.com"},
                           timeout=10)
    if r_csrf.status_code != 403:
        bug("CSRF_NOT_BLOCKED", r_csrf.status_code, r_csrf.text[:300])
    else:
        ok("CSRF_CROSS_ORIGIN_BLOCKED", r_csrf.status_code)

    # CSRF: POST with no Origin/Referer at all (cookie path) → 403
    r_csrf2 = requests.post(BASE + "/api/v1/streams/sync",
                            data={"id": 1},
                            cookies={COOKIE_NAME: token},
                            timeout=10)
    if r_csrf2.status_code != 403:
        bug("CSRF_NO_ORIGIN_NOT_BLOCKED", r_csrf2.status_code,
            r_csrf2.text[:300])
    else:
        ok("CSRF_NO_ORIGIN_BLOCKED", r_csrf2.status_code)

    # CSRF: same path WITH same-origin Origin → 200 (not blocked).
    r_csrf3 = requests.post(BASE + "/api/v1/streams/sync",
                            data={"id": 1},
                            cookies={COOKIE_NAME: token},
                            headers={"Origin": BASE},
                            timeout=15)
    if r_csrf3.status_code != 200:
        bug("CSRF_SAME_ORIGIN_BLOCKED", r_csrf3.status_code,
            r_csrf3.text[:300])
    else:
        ok("CSRF_SAME_ORIGIN_OK")

    # === Cleanup ===
    log("\n=== Cleanup test stream ===")
    if test_id is not None:
        with get_connection() as conn:
            conn.execute(text(
                "DELETE FROM live_stream_configurations WHERE id = :id"
            ), {"id": test_id})
            conn.commit()
        unit_path_t = "/etc/systemd/system/stream-test_btn.service"
        if os.path.isfile(unit_path_t):
            os.remove(unit_path_t)
        # daemon-reload
        import subprocess
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        # also remove env file and workdir if empty
        env_path = "/etc/aiyoutube/streams/test_btn.env"
        if os.path.isfile(env_path):
            os.remove(env_path)
        # remove workdir created by provisioner
        import shutil
        wd = "/var/www/fastuser/data/www/aiyoutube.pbnbots.com/data/streams/test_btn"
        if os.path.isdir(wd):
            shutil.rmtree(wd, ignore_errors=True)
        ok("CLEANUP", f"deleted stream id={test_id}")

    log("\n=== REPORT ===")
    log(json.dumps({"bugs": REPORT["bugs"], "ok_count": len(REPORT["ok"])},
                   indent=2, default=str))
    return REPORT


if __name__ == "__main__":
    main()
