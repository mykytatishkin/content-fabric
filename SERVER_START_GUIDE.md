# Старт сервера: VNC + Nginx + FastAPI (prod)

Краткий гайд по поднятию сервера с графическим доступом (VNC) и веб-доступом к prod API через Nginx.

**Подробные гайды:**  
- VNC и SSH-туннель — [legacy/docs/troubleshooting/SSH_TUNNEL_VNC_FIX.md](legacy/docs/troubleshooting/SSH_TUNNEL_VNC_FIX.md)  
- Nginx — [docs/NGINX_SETUP.md](docs/NGINX_SETUP.md)

---

## 1. Порядок запуска (на сервере)

### 1.1 VNC (опционально, для графического доступа)

```bash
# Установка (один раз)
sudo apt update
sudo apt install tigervnc-standalone-server tigervnc-common
vncpasswd   # пароль при первом запуске

# Запуск на дисплее :1 (порт 5901)
vncserver :1 -geometry 1920x1080 -depth 24
```

Проверка: `sudo ss -tlnp | grep 5901` — должен слушать 127.0.0.1:5901 (или 0.0.0.0:5901).

**Подключение с локальной машины только через SSH-туннель:**
```bash
ssh -L 5901:localhost:5901 root@46.21.250.43
# В другом терминале:
vncviewer localhost:5901
# или macOS: open vnc://localhost:5901
```

Порт 5901 в ufw **не открывать** — доступ только через туннель.

---

### 1.2 Nginx (reverse proxy для API)

```bash
# Установка (один раз)
sudo apt install nginx

# Конфиг из репозитория (из корня проекта)
sudo cp prod/nginx-content-fabric.conf.example /etc/nginx/sites-available/content-fabric
sudo ln -sf /etc/nginx/sites-available/content-fabric /etc/nginx/sites-enabled/

# Проверка и перезагрузка
sudo nginx -t
sudo systemctl reload nginx
```

Nginx слушает порт **80** и проксирует на `127.0.0.1:8000`.

---

### 1.3 FastAPI (uvicorn)

Приложение должно слушать **только localhost**, чтобы не светить его в интернет напрямую:

```bash
cd /path/to/content-fabric/prod
uvicorn main:app --host 127.0.0.1 --port 8000
```

В проде лучше запускать через systemd/supervisor и без `--reload`.

---

## 2. Firewall (ufw)

Открыты только порты для SSH и веб-доступа. VNC снаружи не открываем.

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # Nginx (HTTP)
# Порт 8000 и 5901 НЕ открывать
sudo ufw enable
sudo ufw status
```

Итог: из интернета доступны только **22** (SSH) и **80** (Nginx → FastAPI). VNC — только через `ssh -L 5901:...`.

---

## 3. Проверка

| Что | Команда / URL |
|-----|----------------|
| VNC слушает | На сервере: `ss -tlnp \| grep 5901` |
| Nginx слушает | На сервере: `ss -tlnp \| grep :80` |
| uvicorn слушает | На сервере: `ss -tlnp \| grep 8000` |
| API из интернета | В браузере: `http://46.21.250.43/` (или свой домен) |
| VNC с ноутбука | Туннель `ssh -L 5901:localhost:5901 root@...`, затем `vncviewer localhost:5901` |

---

## 4. Автозапуск (опционально)

- **Nginx:** обычно уже включён в systemd: `sudo systemctl enable nginx`
- **VNC:** см. [SSH_TUNNEL_VNC_FIX.md](legacy/docs/troubleshooting/SSH_TUNNEL_VNC_FIX.md) — раздел «Решение 1: Вариант C (systemd)»
- **uvicorn:** создать unit в `/etc/systemd/system/` с `ExecStart=uvicorn main:app --host 127.0.0.1 --port 8000` и `WorkingDirectory=/path/to/prod`

---

## 5. Схема доступа

```
Интернет
  ├── :22  (SSH)        → вход на сервер + туннель для VNC
  ├── :80  (Nginx)      → proxy_pass → 127.0.0.1:8000 (FastAPI)
  └── :5901 снаружи закрыт; VNC только через ssh -L 5901:localhost:5901
```

Приложение (uvicorn) слушает только **127.0.0.1:8000** — в интернет не «светится».
