# Настройка Nginx для Content Fabric prod

## Назначение

Nginx выступает reverse proxy для FastAPI-приложения (uvicorn), которое слушает порт 8000. Запросы снаружи идут на порт 80/443, Nginx перенаправляет их на `127.0.0.1:8000`.

## Исходный конфиг

Пример конфигурации: [prod/nginx-content-fabric.conf.example](../prod/nginx-content-fabric.conf.example)

```nginx
server {
    listen 80;
    server_name 46.21.250.43 _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Варианты развёртывания

### Доступ по IP

```nginx
server_name 46.21.250.43 _;
```

- `46.21.250.43` — IP сервера
- `_` — fallback для любых имён, если другие `server` не подошли

### Доступ по домену

```nginx
server_name your-domain.com www.your-domain.com;
```

## Шаги установки

1. **Скопировать конфиг** в директорию Nginx:
   ```bash
   sudo cp prod/nginx-content-fabric.conf.example /etc/nginx/sites-available/content-fabric
   ```
   Или в `conf.d/`:
   ```bash
   sudo cp prod/nginx-content-fabric.conf.example /etc/nginx/conf.d/content-fabric.conf
   ```

2. **Создать symlink** (если используется `sites-available` / `sites-enabled`):
   ```bash
   sudo ln -s /etc/nginx/sites-available/content-fabric /etc/nginx/sites-enabled/
   ```

3. **Проверить приоритет**: если FastPanel или другой default-сайт перехватывает трафик, добавь в блок `server`:
   ```nginx
   listen 80 default_server;
   ```

4. **Проверить и перезагрузить**:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

## Интеграция с FastPanel

Если используется FastPanel:

1. Открой панель (например, `https://46.21.250.43:8888`)
2. Создай новый сайт
3. Домен: `46.21.250.43` или свой домен
4. Настрой **Reverse Proxy** на `http://127.0.0.1:8000`

FastPanel сам сгенерирует конфиг Nginx; ручная правка может быть перезаписана при обновлениях.

## Альтернатива: прямой доступ на порт 8000

Без Nginx можно ходить напрямую на uvicorn:

1. **Запуск uvicorn** с привязкой ко всем интерфейсам:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. **Открыть порт в firewall**:
   ```bash
   sudo ufw allow 8000
   sudo ufw reload
   ```

3. **Доступ**: `http://46.21.250.43:8000/`

Минус: нет HTTPS, нет удобного управления через панель.
