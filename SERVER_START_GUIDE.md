# Старт/стоп прод-стека CFF

Практический гайд для дежурного: как поднять/опустить production CFF, проверить здоровье, откатить релиз. Сервер: **46.21.250.43** (ZOMRO, Ubuntu 22.04). Домен: **https://aiyoutube.pbnbots.com** (HTTPS на :443, редирект с :80).

> Подробные гайды:
> - Архитектура — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
> - Операции — [docs/PROD_README.md](docs/PROD_README.md)
> - Observability — [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md)
> - Auditd — [prod/deploy/auditd/README.md](prod/deploy/auditd/README.md)
> - AI-агенту — [GEMINI.md](GEMINI.md)

---

## 1. Сервисы

Все 9 cff-* юнитов лежат в `prod/deploy/systemd/`, установлены в `/etc/systemd/system/`.

| Юнит                              | Что делает                                      |
|-----------------------------------|--------------------------------------------------|
| `cff-api.service`                 | FastAPI/uvicorn на 127.0.0.1:8000                |
| `cff-scheduler.service`           | Опрос БД каждые 60с, enqueue в Redis             |
| `cff-publishing-worker.service`   | YouTube uploads (queue: `publishing`)            |
| `cff-notification-worker.service` | Telegram/email (queue: `notifications`)          |
| `cff-voice-worker.service`        | RVC/Silero (queue: `voice`)                      |
| `cff-dle-ingestion-worker.service`| DLE парсинг → задачи (queue: `dle_ingestion`)    |
| `cff-dle-processor-worker.service`| DLE downloader+voice+assemble (queue: `dle_processing`) |
| `cff-shorts-worker.service`       | yt-dlp+Whisper+GPT shorts (queue: `shorts`)      |
| `cff-stats-worker.service`        | Daily YouTube stats (queue: `stats`)             |
| `cff-stream-control-worker.service`| Управление 9 RTMP-стримами (queue: `stream_control`) |

Имена очередей — `prod/shared/queue/config.py:17-26`.

---

## 2. Запуск / остановка

```bash
# Старт всего стека (порядок не важен, юниты упорядочены через After=)
sudo systemctl start cff-api cff-scheduler \
  cff-publishing-worker cff-notification-worker cff-voice-worker \
  cff-dle-ingestion-worker cff-dle-processor-worker \
  cff-shorts-worker cff-stats-worker cff-stream-control-worker

# Остановка всего стека
sudo systemctl stop cff-api cff-scheduler \
  cff-publishing-worker cff-notification-worker cff-voice-worker \
  cff-dle-ingestion-worker cff-dle-processor-worker \
  cff-shorts-worker cff-stats-worker cff-stream-control-worker

# Перезапуск одного сервиса (типичный кейс после деплоя)
sudo systemctl restart cff-api

# Перезапуск всех cff-* (после git pull новой версии)
sudo systemctl restart 'cff-*.service'

# Включить автозапуск при ребуте (один раз после установки)
sudo systemctl enable cff-api cff-scheduler \
  cff-publishing-worker cff-notification-worker cff-voice-worker \
  cff-dle-ingestion-worker cff-dle-processor-worker \
  cff-shorts-worker cff-stats-worker cff-stream-control-worker
```

Stream-юниты (отдельные `stream-*.service`, по одному на канал) перезапускаются через `cff-stream-control-worker`, не руками.

---

## 3. Health checks

```bash
# Состояние всех cff-*
systemctl status 'cff-*.service' --no-pager

# Краткий список: только те что не active
systemctl list-units 'cff-*.service' --state=failed

# Health endpoint (публично через HTTPS)
curl -sS https://aiyoutube.pbnbots.com/health
# Ожидаемо: {"status":"healthy"} или {"status":"degraded"}

# Полная диагностика (только админ — нужна cookie)
curl -sS -b "cff_token=<jwt>" https://aiyoutube.pbnbots.com/health | jq

# Локально на сервере (минует nginx)
curl -sS http://127.0.0.1:8000/health

# Логи API за последние 50 строк
journalctl -u cff-api -n 50 --no-pager

# Логи воркера в реальном времени
journalctl -u cff-publishing-worker -f

# Все ошибки cff-* за час
journalctl -u 'cff-*.service' --since '1 hour ago' -p err --no-pager
```

`/health` проверяет: API, MySQL, Redis (+ длины очередей), диск, память, uptime. Реализация — `prod/main.py:315-403`.

### Очереди Redis

```bash
# Длина каждой очереди
redis-cli LLEN rq:queue:publishing
redis-cli LLEN rq:queue:notifications
redis-cli LLEN rq:queue:voice
redis-cli LLEN rq:queue:dle_ingestion
redis-cli LLEN rq:queue:dle_processing
redis-cli LLEN rq:queue:shorts
redis-cli LLEN rq:queue:stats
redis-cli LLEN rq:queue:stream_control
redis-cli LLEN rq:queue:failed   # должно быть 0 в норме
```

### Grafana / GlitchTip

Доступ только через SSH-туннель (см. `docs/OBSERVABILITY.md`):

```bash
ssh -L 3001:127.0.0.1:3001 -L 8001:127.0.0.1:8001 root@46.21.250.43
# Grafana:    http://127.0.0.1:3001
# GlitchTip:  http://127.0.0.1:8001
```

---

## 4. Деплой и rollback

```bash
# Стандартный деплой
cd /opt/content-fabric
git fetch origin
git checkout main
git pull --ff-only
cd prod && source venv/bin/activate
pip install -r requirements.txt           # только если requirements.txt изменился
sudo systemctl restart 'cff-*.service'
curl -sS https://aiyoutube.pbnbots.com/health   # smoke check

# Откат на предыдущий коммит
cd /opt/content-fabric
git fetch origin
git log --oneline -5                      # выбрать <prev-commit>
git checkout <prev-commit>
sudo systemctl restart 'cff-*.service'
curl -sS https://aiyoutube.pbnbots.com/health
```

Если `pip install` упал — не рестартим воркеры, фиксим деп, потом рестарт.

---

## 5. Firewall (iptables, не ufw!)

С мая 2026 правила вшиты в iptables (коммит 049f140), не используем `ufw`. Политика:

- Внешне открыты: **22** (SSH), **80** (nginx → 301 на HTTPS), **443** (nginx HTTPS).
- Дропаются на INPUT: **25** (SMTP), **110** (POP3), **143** (IMAP), **465**, **587**, **993**, **995** — почтовые порты не нужны, чтобы не светить уязвимости.
- `DOCKER-USER` chain дропает входящие на **5432** (Postgres GlitchTip) и **6379** (Redis) с любых интерфейсов кроме `lo` — Docker иначе обходит INPUT.
- `127.0.0.1:8000` (uvicorn), `127.0.0.1:3001` (Grafana), `127.0.0.1:9090` (Prometheus), `127.0.0.1:8001` (GlitchTip) — только через SSH-туннель.

```bash
# Посмотреть правила
sudo iptables -L INPUT -n -v --line-numbers
sudo iptables -L DOCKER-USER -n -v --line-numbers

# Сохранить (если меняли)
sudo iptables-save > /etc/iptables/rules.v4
```

---

## 6. HTTPS-сертификаты

Конфиг nginx — `prod/deploy/nginx/aiyoutube.pbnbots.com.conf` (на сервере: `/etc/nginx/sites-enabled/`).

```
ssl_certificate     /var/www/httpd-cert/aiyoutube.pbnbots.com_2025-10-04-13-20_13.crt
ssl_certificate_key /var/www/httpd-cert/aiyoutube.pbnbots.com_2025-10-04-13-20_13.key
```

Сертификат выпущен FastPanel (хостинг ZOMRO). Обновление автоматическое через FastPanel UI; ручной перевыпуск:

```bash
# В FastPanel → Domains → aiyoutube.pbnbots.com → SSL → Renew
# После обновления:
sudo nginx -t && sudo systemctl reload nginx
```

Срок жизни — 90 дней (Let's Encrypt). Если в `journalctl -u nginx` видим `SSL_CTX_use_PrivateKey_file failed` — сертификат истёк, идти в FastPanel.

Проверка снаружи:

```bash
curl -vI https://aiyoutube.pbnbots.com/health 2>&1 | grep -E 'expire|HTTP/'
openssl s_client -connect aiyoutube.pbnbots.com:443 -servername aiyoutube.pbnbots.com </dev/null 2>/dev/null | openssl x509 -noout -dates
```

---

## 7. Что НЕ делать

- **Не запускать `sudo ufw enable`.** Мы на iptables; ufw сбросит наши правила и оставит дыры в DOCKER-USER цепочке.
- **Не запускать `nohup uvicorn main:app --host 0.0.0.0 --port 8000`.** Юнит `cff-api.service:14` биндит **127.0.0.1**, наружу торчит только nginx. Биндинг на `0.0.0.0` обходит nginx → пропадают rate-limit, security headers, HTTPS.
- **Не трогать `/opt/content-fabric/prod/tg-app`** и `/var/www/*/tg-app`. Это отдельное приложение другой команды.
- **Не запускать Yii2 / PHP старого приложения.** Миграция завершена (см. `database/DDL/migrations/004_yii_decommission.sql`), legacy-код deprecated.
- **Не редактировать `.env` файлы поверх git'а.** Получить актуальные у @mykytatishkin в ЛС, положить в `/opt/content-fabric/.env` и `/opt/content-fabric/prod/.env/`.
- **Не делать `git pull` без `--ff-only`.** Случайный merge-commit на проде = головная боль при rollback.
- **Не рестартить cff-stream-control-worker без нужды** — он же дёргает 9 stream-юнитов. Если стрим упал, сначала смотрим конкретный `stream-N.service`.

---

## 8. Аварийный план

1. **API не отвечает (`/health` → timeout):**
   ```bash
   sudo systemctl status cff-api
   journalctl -u cff-api -n 100 --no-pager
   sudo systemctl restart cff-api
   ```
2. **Очередь забилась (>500 в `failed`):**
   ```bash
   redis-cli LRANGE rq:queue:failed 0 5     # глянуть несколько jobs
   journalctl -u cff-publishing-worker --since '30 min ago' -p err
   # При необходимости — clear failed после анализа:
   # redis-cli DEL rq:queue:failed
   ```
3. **Полный rollback (см. раздел 4) + уведомить в Telegram-канал команды.**
4. **Сервер целиком лежит:** ZOMRO control panel → reboot, после ребута `systemctl status 'cff-*.service'` (автозапуск через `WantedBy=multi-user.target`).

---

## 9. Схема доступа (итог)

```
Интернет
  ├── :22   SSH                  → вход + туннели для Grafana/GlitchTip/VNC
  ├── :80   nginx                → 301 redirect на :443
  └── :443  nginx (HTTPS)        → proxy_pass http://127.0.0.1:8000

127.0.0.1 only (не торчит наружу):
  :8000   uvicorn (FastAPI)
  :3001   Grafana
  :8001   GlitchTip
  :9090   Prometheus
  :3306   MySQL
  :6379   Redis
  :5901   VNC (если запущен; только через ssh -L)
```
