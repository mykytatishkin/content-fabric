# SECURITY.md — Content Fabric

> Канонический security-reference после hardening pass 2026-05-09.
> Обновляется при каждом изменении perimeter / auth / audit. Цитаты вида
> `prod/main.py:30-58` означают, что строки реально живут там — если меняешь
> код, меняй и этот документ.

---

## 1. Threat model

После инцидента мая 2026 (Redis RCE → cron persistence → cryptominer)
угрозная модель сведена к четырём векторам, против которых выстроена
защита:

- **Public service exposure / RCE через сервис без auth.** Redis (6379) и
  Postgres (5432) ранее были видны из интернета через docker-proxy. Атакующий
  через `CONFIG SET dir /var/spool/cron/...` записал cron job. Теперь все
  служебные порты — `127.0.0.1` only, см. §2.
- **SSH brute force.** ~286k попыток / 44k IP за наблюдаемое окно. Митигация:
  fail2ban (sshd jail), auditd `cff-ssh-keys`/`cff-ssh-config`, Grafana
  dashboard `cff-security`.
- **Supply chain.** CVE в зависимостях Python (requests, python-multipart,
  psutil). Митигация: pinned upper bounds + регулярный `pip install -U`,
  см. §12.
- **Web-app угрозы.** Stored XSS в портале, CSRF на cookie-формах,
  unauthenticated `/metrics` и `/api/v1/{streams,dle-sources,logs}`.
  Закрыто в hardening pass 2026-05-09 (см. §15).

---

## 2. Network perimeter

Хост `46.21.250.43` (ZOMRO). Внешнему миру отдаются только web-порты;
служебные слушают `127.0.0.1` либо отрезаются на уровне Docker chain.

| Порт  | Протокол | Видимость           | Назначение                                 | Как ограничен                           |
| ----- | -------- | ------------------- | ------------------------------------------ | --------------------------------------- |
| 22    | TCP      | public              | SSH (root + key, password fallback — §13) | fail2ban (sshd jail), auditd            |
| 80    | TCP      | public              | nginx → 301 на HTTPS                      | `aiyoutube.pbnbots.com.conf:46-50`      |
| 443   | TCP      | public              | nginx TLS → uvicorn 127.0.0.1:8000        | TLS, HSTS, см. §3                       |
| 8000  | TCP      | 127.0.0.1           | uvicorn (FastAPI) upstream                 | bind в systemd unit                     |
| 3000  | TCP      | 127.0.0.1           | Grafana (Cloudflare tunnel наружу)         | docker bind                             |
| 3100  | TCP      | 127.0.0.1           | Loki                                       | docker bind                             |
| 9090  | TCP      | 127.0.0.1           | Prometheus                                 | docker bind                             |
| 9080  | TCP      | 127.0.0.1           | promtail HTTP                              | docker bind                             |
| 5432  | TCP      | docker bridge only  | Postgres (glitchtip)                       | DOCKER-USER chain (см. ниже)            |
| 6379  | TCP      | docker bridge only  | Redis (queue + glitchtip)                  | DOCKER-USER chain (см. ниже)            |
| 3306  | TCP      | 127.0.0.1           | MySQL (CFF main DB)                        | mysqld bind-address                     |

### Docker — почему `INPUT` недостаточно

`docker-proxy` слушает на `0.0.0.0:5432` и `0.0.0.0:6379` через NAT
(`PREROUTING` / `DNAT`), а трафик к контейнерам идёт по chain `FORWARD`
после трансляции, **минуя `INPUT`**. Поэтому правила
`iptables -A INPUT -p tcp --dport 5432 -j DROP` ничего не блокируют.

Корректное правило — в chain `DOCKER-USER` (выполняется до Docker NAT):

```bash
iptables -I DOCKER-USER -p tcp --dport 5432 ! -s 127.0.0.1 -j DROP
iptables -I DOCKER-USER -p tcp --dport 6379 ! -s 127.0.0.1 -j DROP
```

Сохраняется через `iptables-save > /etc/iptables/rules.v4` и поднимается
скриптом `/etc/network/if-pre-up.d/iptables` при загрузке.

### Внутренние эндпоинты, которые нельзя пускать наружу

- `GET /metrics` — Prometheus instrumentator. nginx ограничивает доступ
  только с loopback:
  ```nginx
  location = /metrics {
      allow 127.0.0.1;
      deny all;
  }
  ```
  См. `prod/deploy/nginx/aiyoutube.pbnbots.com.conf:19-22` и
  `prod/deploy/nginx/content-fabric.conf:49-52`.
- `GET /docs`, `/redoc`, `/openapi.json` — отключены в production (только
  при `ENV=development`), `prod/main.py:186-194`.

---

## 3. TLS / HTTPS

- Сертификат `aiyoutube.pbnbots.com` (FastPanel),
  `prod/deploy/nginx/aiyoutube.pbnbots.com.conf:5-6`.
- HTTP/2 включён (`http2 on`).
- HTTP → HTTPS 301 redirect (`:46-50` того же файла).
- `www.aiyoutube.pbnbots.com` редиректится на apex (`:53-67`).

### HSTS

Заголовок выставляется и nginx-ом, и приложением (defense-in-depth):

```
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
```

- `max-age=63072000` (2 года) — требование для preload list.
- `includeSubDomains` — все sub-доменные cookies/HTTP блокируются на 2 года.
- `preload` — заявка на включение в hstspreload.org. Пока **не подавалась**
  (нужно подтвердить, что все sub-домены умеют HTTPS).

Источники: `prod/main.py:57`, `prod/deploy/nginx/aiyoutube.pbnbots.com.conf:7`.

---

## 4. HTTP security headers

`SecurityHeadersMiddleware` (`prod/main.py:30-58`) выставляет на каждом
ответе:

| Header                       | Значение                                         | Зачем                                                                                              |
| ---------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `X-Content-Type-Options`     | `nosniff`                                        | Запрет MIME-sniff: браузер не догадается выдать `.txt` за HTML.                                    |
| `X-Frame-Options`            | `DENY`                                           | Запрет фрейминга (legacy header). Дублирует `frame-ancestors 'none'` для старых браузеров.         |
| `X-XSS-Protection`           | `1; mode=block`                                  | Legacy IE/старый Chrome. Современные браузеры игнорируют, но не вредит.                            |
| `Referrer-Policy`            | `strict-origin-when-cross-origin`                | Кросс-доменный реквест получает только origin, без path/query (минимум leak).                      |
| `Permissions-Policy`         | `camera=(), microphone=(), geolocation=()`       | Запрет API устройств. У нас нет таких фич — отключаем upfront.                                     |
| `Strict-Transport-Security`  | `max-age=63072000; includeSubDomains; preload`   | См. §3.                                                                                            |

### Content-Security-Policy

```
default-src 'self';
style-src   'self' 'unsafe-inline';
script-src  'self' 'unsafe-inline';
img-src     'self' data: blob:;
connect-src 'self';
object-src  'none';
base-uri    'self';
form-action 'self';
frame-ancestors 'none';
```

Построчно:

- `default-src 'self'` — fallback для любых нетребуемых директив.
- `style-src 'self' 'unsafe-inline'` — нужно из-за inline `<style>` в
  Jinja-шаблонах. `'unsafe-eval'` **убран** (`prod/main.py:37`) — eval в
  коде не используется.
- `script-src 'self' 'unsafe-inline'` — то же для inline `<script>`.
  Цель миграции: вынести inline → файлы и убрать `'unsafe-inline'`.
- `img-src 'self' data: blob:` — превью thumbnails (data URLs) и blob-генерация
  графиков.
- `connect-src 'self'` — fetch/XHR только к нашему origin.
- `object-src 'none'` — Flash/Java/legacy plugins запрещены.
- `base-uri 'self'` — защита от `<base href="evil.com">`-инъекций.
- `form-action 'self'` — submit формы только на свой origin (доп. CSRF-щит).
- `frame-ancestors 'none'` — современный аналог `X-Frame-Options: DENY`.

---

## 5. Authentication

### JWT

- Алгоритм: HS256 (`prod/app/core/security.py:19`).
- Секрет: `JWT_SECRET_KEY` из `/opt/content-fabric/.env`. Длина — 32 байта
  hex (`secrets.token_hex(32)`). Последняя ротация — **2026-05-09**
  (commit `049f140 fix(security): rotate JWT secret to 32 bytes`).
- Если переменная пуста — приложение падает на старте
  (`prod/app/core/security.py:13-18`), что предотвращает запуск с
  default-секретом.
- Lifetime: `JWT_EXPIRE_MINUTES` (default 1440 мин = 24h),
  `prod/app/core/security.py:20`.
- `sub` claim — обязательно строка (`prod/app/core/security.py:38-39`),
  иначе при сравнении `int` vs `str` PyJWT поведение нестабильно между
  версиями.

### Сессионная модель

Поддерживаются две формы предъявления токена (`prod/app/api/deps.py:26-57`):

1. **Bearer header** — для CLI / тестов / machine-to-machine. Не подвержен
   CSRF (атакующий не может прочитать `Authorization` с другого origin).
2. **Cookie `cff_token`** — выставляется на `/app/login`,
   `prod/app/views/app_portal.py:55-63`:
   - `httponly=True` — JS прочитать не может (защита от XSS-кражи токена).
   - `secure` — выставляется только если `HTTPS_ENABLED` (production).
   - `samesite=lax` — браузер не отправит cookie при cross-site POST,
     дополняет CSRF middleware (см. §7).
   - `path=/`, `max_age=86400` (24h).

Если присутствуют оба — приоритет у Bearer (`prod/app/api/deps.py:31-35`).

### Пароли

- bcrypt через `passlib.CryptContext(schemes=["bcrypt"])`,
  `prod/app/core/security.py:22`.
- Helpers: `hash_password()` / `verify_password()`,
  `prod/app/core/security.py:25-30`.

### 2FA / TOTP

- Библиотека: `pyotp>=2.9` (`prod/requirements.txt:18`).
- Шаблоны: `prod/app/templates/app_totp.html`,
  `prod/app/templates/app_settings.html`.
- Логика: `prod/app/api/endpoints/auth.py`,
  `prod/tests/test_api_auth_2fa.py`.
- 2FA доступно к включению в портале, но **не enforced** (см. §13).

---

## 6. Authorization

### `UserStatus` (IntEnum, `prod/shared/db/models.py:14-17`)

```python
class UserStatus(IntEnum):
    INACTIVE = 0   # деактивирован, login закрыт
    ADMIN    = 1   # полный доступ
    ACTIVE   = 10  # обычный пользователь
```

> ВАЖНО: в SQL-запросах всегда сравнивать через `.value` (см.
> `MEMORY.md`/architecture notes). FastAPI dependencies сами сравнивают
> через объект enum.

### Helpers (`prod/app/core/auth.py`)

| Функция                  | Где использовать         | Поведение при отсутствии прав            |
| ------------------------ | ------------------------ | ---------------------------------------- |
| `is_admin(user)`         | проверка bool            | возвращает False                         |
| `require_user(request)`  | view-handlers (HTML)     | redirect 302 → `/app/login`              |
| `require_admin(request)` | view-handlers (HTML)     | redirect 302 → `/app/`                   |
| `require_admin_api(user)`| API-helper (имеет user)  | `HTTPException(403)`                     |
| `get_current_user`       | FastAPI dep (cookie/Bearer) | `HTTPException(401)`                  |
| `get_current_admin`      | FastAPI dep              | `HTTPException(403)`                     |

### Admin-only endpoints (после 2026-05-09)

Все три модуля используют `Depends(get_current_admin)`:

- `/api/v1/streams/*` — `prod/app/api/endpoints/streams.py:24` (gates запуск
  systemd-юнитов и провижининг ffmpeg).
- `/api/v1/dle-sources/*` — `prod/app/api/endpoints/dle_sources.py:17`
  (триггер ingestion-job, доступ к 7 внешним БД).
- `/api/v1/logs/*` — `prod/app/api/endpoints/logs.py:36` (журналы
  journald, утечка trace_id, ошибки и т.п.).

Также `/panel/*` (HTML админка) защищён на уровне views через
`require_admin`.

См. commit `a45ea5c fix(security): require admin for streams/dle-sources/logs`.

---

## 7. CSRF protection

`CSRFMiddleware` (`prod/main.py:61-136`) — Origin/Referer-based проверка
для cookie-аутентифицированных state-changing запросов.

Алгоритм:

1. Метод `GET/HEAD/OPTIONS` → пропуск (safe by spec).
2. Есть `Authorization: Bearer …` → пропуск (CSRF-вектор отсутствует —
   браузер не отдаст этот header автоматически с другого origin).
3. Нет cookie `cff_token` → пропуск (login bootstrap, анонимные POST).
4. Иначе сравниваем `Origin` / `Referer` с `Host`:
   - Совпадает (с учётом `http://` и `https://`) → пропуск.
   - Не совпадает → `403 {"detail": "CSRF: cross-origin POST rejected"}`,
     warning в `cff.csrf` логгер.
   - Нет ни `Origin`, ни `Referer` → `403 {"detail": "CSRF: missing
     Origin/Referer header"}`. Браузеры всегда шлют хотя бы один на POST,
     отсутствие подозрительно.

`SameSite=lax` cookie (см. §5) — второй слой: даже если middleware
отключится, браузер сам не отправит cookie с другого origin при POST.

Источник: commit `049f140 fix(security): rotate JWT secret to 32 bytes,
add CSRF middleware, ports lockdown`.

---

## 8. Rate limiting

`slowapi` поверх `BaseHTTPMiddleware`, `prod/main.py:27`:

```python
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
```

- Default: **120 req/min на IP** для всех путей.
- Превышение → handler `prod/main.py:216-219` пишет warning и отдаёт
  `429 {"detail": "Too many requests"}`.
- Отдельные эндпоинты (например, `/auth/login`) можно дополнительно
  декорировать `@limiter.limit("…")`, если потребуется ужесточить.
- IP берётся из `request.client.host` (за nginx, поэтому фактически —
  X-Real-IP от nginx → uvicorn).

---

## 9. Audit logging (auditd)

Полная документация: `prod/deploy/auditd/README.md`. Правила:
`prod/deploy/auditd/cff-security.rules` (52 watch/syscall правила).

Что трекается (по тегам `-k`):

- **Identity**: `/etc/passwd`, `shadow`, `group`, `gshadow`, `security/`
  (`cff-identity`), sudoers (`cff-sudoers`), PAM (`cff-pam`).
- **SSH**: `sshd_config*` (`cff-ssh-config`), `/root/.ssh/`
  (`cff-ssh-keys`).
- **Privilege escalation**: execve `sudo/su/passwd/chsh/chfn/newgrp/gpasswd`
  (`cff-priv-exec`); любой переход не-root → UID 0 через execve
  (`cff-priv-launch`).
- **Persistence vectors**: `/etc/cron*`, `/var/spool/cron/` (`cff-cron`);
  `/etc/systemd/system/`, `/lib/systemd/system/`, `/etc/init.d/`
  (`cff-systemd`); kernel `init_module/delete_module/finit_module`
  (`cff-module`).
- **Network**: `/etc/iptables/` (`cff-firewall`), `/etc/network/`,
  `/etc/hosts`, `/etc/resolv.conf`, `/etc/nsswitch.conf` (`cff-network`),
  `/etc/nginx/` (`cff-nginx`).
- **CFF**: `/opt/content-fabric/.env` (`cff-secrets`, `-p rwa` —
  включая чтения!); `main.py`, `app/core/security.py`, `app/api/deps.py`
  (`cff-code-critical`).
- **Anti-tamper**: `adjtimex/settimeofday/clock_settime` + `/etc/localtime`
  (`cff-time`); `mount` syscall (`cff-mount`).
- **Yii legacy**: `/yii/`, `/protected/` (`cff-yii-legacy`) — алярм если
  кто-то снова включит Yii.

Pipeline: auditd → `/var/log/audit/audit.log` → promtail (job `auditd`,
извлекает `audit_type`, `audit_key`, `comm`, `src_ip`) → Loki (30d) →
Grafana dashboard `cff-security`.

Лимит на диск: 50MB × 10 файлов = 500MB
(`prod/deploy/auditd/auditd.conf`). `space_left=200` — SYSLOG warning,
`admin_space_left=100` — SUSPEND auditd.

Re-deploy:

```bash
scp cff-security.rules root@46.21.250.43:/etc/audit/rules.d/cff-security.rules
ssh root@46.21.250.43 'auditctl -D && augenrules --load && auditctl -l | wc -l'
```

> Gotcha: `augenrules` молча обрезает правила на первом не-ASCII символе в
> комментариях. Все комментарии в `.rules` — plain ASCII.

---

## 10. Observability of attacks

- **Grafana dashboard `cff-security`** (`/d/cff-security`): identity-mutations
  panel, SSH login successes by source IP, CFF code changes, cron
  persistence attempts — всё на основе LogQL по `{job="auditd"}`. Конфиг:
  `prod/deploy/observability/grafana/dashboards/security.json`.
- **fail2ban (sshd jail)** — стандартный jail.local, ban window/findtime
  по дефолту (10 min / 1h). 44k IP в bantable за наблюдаемое окно
  показывает, что jail работает; брутфорс 286k attempts отбит.
- **rkhunter weekly** — `/etc/cron.weekly/cff-rkhunter` пишет в
  `/var/log/rkhunter/weekly-*.log`. Baseline:
  `prod/deploy/auditd/baseline-scan-2026-05-09.md`.
- **Glitchtip** (Sentry-compatible) — application errors через
  `shared/error_tracking.py`.

---

## 11. Secrets management

- Файл: `/opt/content-fabric/.env` (на хосте, **не в git**).
- Permissions: `chmod 600 root:root`. Любое чтение/запись логируется в
  audit под тегом `cff-secrets` (см. §9).
- Загружается systemd-юнитами через `EnvironmentFile=/opt/content-fabric/.env`.
- Содержит: `JWT_SECRET_KEY`, `MYSQL_*`, `REDIS_URL`, OAuth-токены YouTube,
  Telegram-боты, Sentry/Glitchtip DSN. Конкретные значения — **see
  `/opt/content-fabric/.env`**, в этом документе их быть не должно.
- При ротации: бэкап в `/opt/content-fabric/.env.bak.<unix-ts>` (тоже под
  `chmod 600`, тоже под audit-watch).
- Шаблон с пустыми значениями: `prod/.env.example`.

> Получение `.env` — у `@mykytatishkin` в ЛС.

### 11a. SENTRY_DSN / GlitchTip configuration

CFF использует self-hosted GlitchTip (Sentry-compatible) для error tracking.
Контейнеры — `cff-glitchtip-{web,worker,redis,postgres}`, web-UI на
`http://127.0.0.1:8001` (наружу не выведен; ходить через SSH-tunnel).

SDK-обёртка: `prod/shared/error_tracking.py` (no-op если `SENTRY_DSN`
пустой). Инициализируется один раз на старте каждого процесса
(`prod/main.py`, `prod/workers/_job_bootstrap.py`) с `service` тегом и
автодобавлением `trace_id`/`task_id` из `logging_context` (через
`_before_send` hook).

Ключи в `/opt/content-fabric/.env` (значения **redacted** — реальный DSN
живёт только на хосте):

```
SENTRY_DSN=http://<32-char-public-key>@127.0.0.1:8001/<project_id>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.05
SENTRY_RELEASE=cff@<git-sha>
```

`SENTRY_TRACES_SAMPLE_RATE=0.05` — 5% транзакций сэмплятся для performance
tracing; для error capture сэмплинг не применяется (все исключения летят
в GlitchTip всегда).

#### Bootstrap (один раз на чистом GlitchTip)

```bash
# 1) superuser (на сервере)
docker exec -e DJANGO_SUPERUSER_PASSWORD='<pw>' cff-glitchtip-web \
    ./manage.py createsuperuser --noinput --email admin@cff.local

# 2) org "CFF" + project "cff-prod" + DSN — через Django shell
docker exec cff-glitchtip-web ./manage.py shell -c '
from django.contrib.auth import get_user_model
from apps.organizations_ext.models import Organization, OrganizationUserRole
from apps.projects.models import Project
from apps.teams.models import Team
admin = get_user_model().objects.get(email="admin@cff.local")
admin.is_active = True; admin.save()
org, _  = Organization.objects.get_or_create(name="CFF", slug="cff")
ou      = org.add_user(admin, role=OrganizationUserRole.OWNER)
team, _ = Team.objects.get_or_create(slug="cff", organization=org)
team.members.add(ou)
proj, _ = Project.objects.get_or_create(name="cff-prod", slug="cff-prod", organization=org)
team.projects.add(proj)
for k in proj.projectkey_set.all():
    print("DSN:", k.get_dsn())
'
```

DSN из вывода → пишем в `/opt/content-fabric/.env` под ключом `SENTRY_DSN`.
**Никогда не коммитить реальный DSN в git.**

#### Применение

После правки `.env` рестартим API + всех воркеров (юниты грузят файл
через `EnvironmentFile=`):

```bash
systemctl restart cff-api cff-{dle-ingestion,dle-processor,notification,\
publishing,shorts,sora,stats,stream-control,voice}-worker cff-scheduler
```

#### Smoke-test

```bash
cd /opt/content-fabric/prod && set -a && . /opt/content-fabric/.env && set +a
venv/bin/python -c '
import sys; sys.path.insert(0, ".")
from shared.error_tracking import init, capture_message
import sentry_sdk
init("smoke"); capture_message("smoke", level="warning"); sentry_sdk.flush(timeout=8)'
```

Событие должно появиться в GlitchTip (project `cff-prod`) в течение
~5–10 секунд. Проверка через Django shell (UI не выведен наружу):

```bash
docker exec cff-glitchtip-web ./manage.py shell -c '
from apps.issue_events.models import IssueEvent
from apps.projects.models import Project
print(IssueEvent.objects.filter(issue__project__slug="cff-prod").count())
'
```

#### Rotation / revoke

Удалить старый ключ и сгенерировать новый:

```bash
docker exec cff-glitchtip-web ./manage.py shell -c '
from apps.projects.models import Project, ProjectKey
p = Project.objects.get(slug="cff-prod")
ProjectKey.objects.filter(project=p).delete()
k = ProjectKey.objects.create(project=p)
print("DSN:", k.get_dsn())
'
```

Затем обновить `SENTRY_DSN` в `/opt/content-fabric/.env` и рестартнуть
юниты (см. выше). Старый DSN мгновенно перестаёт принимать события.

---

## 12. Dependency hygiene

`prod/requirements.txt` — pinned по нижней границе с известным CVE-фиксом
и закрытой верхней границей по major:

| Пакет             | Constraint            | Почему                                                            |
| ----------------- | --------------------- | ----------------------------------------------------------------- |
| `requests`        | `>=2.32.4,<3.0`       | CVE-2024-47081 (Netrc creds leak). Минимум 2.32.4.                |
| `python-multipart`| `>=0.0.18,<1.0`       | CVE-2024-53981 (DoS на boundary parsing). Минимум 0.0.18.         |
| `psutil`          | `>=5.9.8,<8.0`        | CVE-2024-...; security baseline.                                  |
| `pyotp`           | `>=2.9,<3.0`          | TOTP, без известных активных CVE; пиннуем major.                  |

Регламент:

- Раз в месяц: `pip list --outdated`, обновить minor/patch версии в
  `requirements.txt`, прогнать `prod/tests/` (202 теста), задеплоить.
- При CVE-алерте от GitHub Dependabot — out-of-band patch в течение 48h.

---

## 13. Что НЕ форсируется (и почему)

| Гайдлайн                  | Состояние   | Причина                                                                                                                                              |
| ------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| SSH без пароля root       | **отключено** | Команда использует root-via-password для backup-скриптов из внешнего VPS; ключи разнесены асинхронно. Митигация: fail2ban + auditd `cff-ssh-config`. |
| MFA enforcement для всех  | **отложено**  | По запросу пользователя. 2FA доступно в портале (см. §5), но не обязательно. План: enforce для admin после онбординга всех владельцев каналов.       |
| Принудительная ротация паролей | **нет**     | NIST SP 800-63B рекомендует **не** форсировать ротацию без признаков компрометации. Полагаемся на длину + bcrypt.                                    |
| Network egress firewall   | **нет**     | Воркерам нужен доступ к YouTube/TikTok/IG/Telegram API. Проще трекать аномалии через Grafana, чем поддерживать allow-list.                          |

---

## 14. Incident response runbook

Быстрые шаги для типичных сценариев. Все ссылки на источники — в Loki
(`/d/cff-security`) или на хосте через `ausearch`.

### a) Подозрительные cron entries

1. Проверить, что нового:
   ```bash
   ssh root@46.21.250.43 'ausearch -k cff-cron --start "24 hours ago" -i'
   ```
2. Сравнить с известным набором: `/etc/crontab`, `/etc/cron.d/`,
   `/etc/cron.{hourly,daily,weekly,monthly}/`, `crontab -l` для каждого
   пользователя.
3. В Grafana: panel "Cron persistence attempts" на `cff-security` показывает
   timeline.
4. Если найден чужой entry — удалить, ребутнуть auditd, искать инициатора:
   `ausearch -k cff-cron -i | grep <filename>`.

### b) Неизвестный SSH login

1. `ausearch -m USER_ACCT --start "24 hours ago"` — все login события.
2. В Grafana: "SSH login successes by source IP" группирует по
   `src_ip`. Любой IP не из allow-list (`@mykytatishkin`,
   `@SsmTuInvalid1`) — alert.
3. Если IP подозрительный:
   ```bash
   fail2ban-client set sshd banip <IP>
   ausearch -k cff-ssh-keys --start "1 week ago"   # вдруг ключ положили
   cat /root/.ssh/authorized_keys                   # ручная сверка
   ```
4. Сменить `JWT_SECRET_KEY` (логаут всех сессий) — см. §11.

### c) Подозрительные исходящие соединения от worker

1. Проверить логи воркера в Loki:
   `{job="cff-publishing-worker"} |~ "outbound|connect"` (либо через
   trace_id из Grafana).
2. Если worker лезет в незнакомый домен — посмотреть последние `git diff`
   на критичных файлах:
   ```bash
   ausearch -k cff-code-critical --start "1 week ago" -i
   ```
3. Cross-check: `lsof -i -p <pid>` на хосте.
4. Если подтверждается — остановить юнит:
   `systemctl stop cff-publishing-worker` и снять snapshot
   (`shared/error_tracking` в Glitchtip).

### d) Iptables rules сброшены

1. Проверить активный набор: `iptables -L DOCKER-USER -n -v` — должны
   быть DROP-правила для 5432/6379 (см. §2).
2. Если пусто — восстановить:
   ```bash
   iptables-restore < /etc/iptables/rules.v4
   ```
   либо ребут (`/etc/network/if-pre-up.d/iptables` поднимет автоматически).
3. Найти, кто сбросил: `ausearch -k cff-firewall --start "24 hours ago"`.

---

## 15. Audit history

- **2026-05-09 — Full hardening pass.** Один день, серия коммитов:
  - `87d6a1c fix(security): patch Stored XSS in 4 portal pages via Jinja
    tojson filter` — escape user-controlled JSON в шаблонах.
  - `a45ea5c fix(security): require admin for streams/dle-sources/logs API
    endpoints` — закрыты три ранее публичных API-роута.
  - `27fc60e fix(metrics): treat token_expires_at as UTC in
    sample_youtube_token_expiries` — исправлена tz-naive сравнения,
    устранена утечка через ошибочные метрики.
  - `e1dcde1 fix(dle): correct slug→host conversion for dle_post_url` —
    нормализация slug (защита от ssrf-подобных подстановок).
  - `2a610cb fix(dle): preserve parent trace_id in _create_cff_task` —
    непрерывная трассировка через worker-цепочки.
  - `b0d3b9f fix(panel): /panel/stats uses snapshot_date, not recorded_at`
    — корректные данные в админке (закрытие неконсистентности).
  - `27fc60e fix(security): block public access to /metrics in nginx`
    (см. §2).
  - `049f140 fix(security): rotate JWT secret to 32 bytes, add CSRF
    middleware, ports lockdown` — JWT, CSRF middleware, DOCKER-USER
    rules для 5432/6379.
  - `4a81951 fix(security+observability): tighten CSP+HSTS, push
    log_events_total from workers` — `'unsafe-eval'` убран из CSP, HSTS
    поднят до 2y+preload.
  - `e49ace1 feat(security): auditd rules + ingestion + Grafana security
    dashboard` — 52 audit правила, promtail pipeline, dashboard
    `cff-security`.
  - `84231d7 docs(security): rkhunter + chkrootkit baseline scan report`
    — baseline-skan, см. `prod/deploy/auditd/baseline-scan-2026-05-09.md`.
  - Dependency bump: `requests>=2.32.4`, `python-multipart>=0.0.18`,
    `psutil>=5.9.8`.
  - **GlitchTip wiring.** `SENTRY_DSN` сконфигурирован в
    `/opt/content-fabric/.env`, project `cff-prod` создан в локальном
    GlitchTip (org `CFF`). cff-api + 10 воркеров рестартнуты, smoke-test
    подтверждён. См. §11a.

Будущие аудит-записи добавлять сюда же датой.
