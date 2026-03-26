# Гайд: Авторизация YouTube каналов на сервере

## Обзор каналов

### Группа A: Каналы с токенами и credentials (автоматический reauth)

Эти каналы имеют email/пароль в базе и привязанный Google Console. Reauth работает автоматически через Selenium.

| ID | Канал | Email | Console | TOTP | Токен истекает |
|----|-------|-------|---------|------|----------------|
| 5 | audiokniga-one | audioknigaone@gmail.com | Console 1 | - | 2026-02-25 |
| 6 | Popadanciaudio | popadanciaudio@gmail.com | Console 1 | - | 2026-03-02 |
| 7 | onlineaudioknigicom | knigiaudio.biz@gmail.com | Console 1 | - | 2026-02-28 |
| 8 | chitaemvslux | wiktordrozdowicz78@gmail.com | mir-knig-info | - | 2026-02-28 |
| 12 | knigionlineclub | paraknigorg81@gmail.com | mir-knig-info | - | 2026-03-02 |
| 13 | paraknigorgonline | paraknigorg77@gmail.com | mir-knig-info | - | 2026-03-02 |
| 17 | Readbooks-online | readliclubinfo@gmail.com | mir-knig-info | - | 2026-02-26 |
| 21 | knigabooks | knigabooks.ru@gmail.com | YouTube Stats | TOTP | 2026-02-26 |
| 26 | bazaknig_net | ytubaza6@gmail.com | content-fabric | - | 2026-03-02 |
| 28 | xobiATVUA | 5481184@gmail.com | Console 1 | - | 2026-02-28* |
| 29 | bazaknig1 | bazaknig21@gmail.com | Console 1 | - | 2026-03-02 |
| 31 | babysmilevlog | babysmilevlog@gmail.com | Console 1 | - | 2026-02-28 |
| 32 | knigbaza7 | knigbaza3@gmail.com | mybooks_club | - | 2026-03-02 |
| 47 | knigbaza | knigbaza56@gmail.com | Console 1 | - | 2026-03-02 |
| 48 | knigovabaza | knigbaza56@gmail.com | Console 1 | - | 2026-02-25 |

### Группа B: Каналы без токенов (нужна первичная авторизация)

Включены (`enabled=1`), есть email/пароль, но **нет токенов** и **нет Google Console** (`console_id=NULL`).

| ID | Канал | Email | Проблема |
|----|-------|-------|----------|
| 46 | girl_vibestv | blogeri789@gmail.com | Нет console_id |
| 49 | youtubebaza-h8s | y7728700@gmail.com | Нет console_id |
| 50 | ytub-b9i | y7728700@gmail.com | Нет console_id |
| 51 | YouTube9 | u60962770@gmail.com | Нет console_id |
| 52 | YouTube11 | u608502@gmail.com | Нет console_id |
| 53 | YouTube7_0 | utub86520@gmail.com | Нет console_id |
| 54 | Дитячі канали | ditacikanali@gmail.com | Нет console_id |
| 55 | Канали новин | kanalinovin831@gmail.com | Нет console_id |
| 56 | Блог чоловіки | blogericoloviki24@gmail.com | Нет console_id |
| 57 | Блогери жінки | blogerizinki@gmail.com | Нет console_id |
| 58 | Топ шоу ру | topsooru@gmail.com | Нет console_id |

### Группа C: Отключенные каналы (`enabled=0`)

ID: 2, 3, 4, 9, 19, 20, 23, 25, 27, 30, 33 — пропускаем.

---

## Пошаговый алгоритм

### Шаг 1: Подготовка — назначить Google Console каналам Группы B

Каналы 46–58 не имеют `console_id`. Без него reauth не знает какой `client_id`/`client_secret` использовать.

**Вариант 1** — использовать fallback из `.env` (`YOUTUBE_MAIN_CLIENT_ID`). Уже настроено, но нужно проверить что этот client_id имеет YouTube Data API v3 включённый.

**Вариант 2** — назначить console_id через админку или SQL:

```sql
-- Пример: назначить Console 1 (id=1) всем каналам без console_id
UPDATE platform_channels
SET console_id = 1
WHERE id IN (46,49,50,51,52,53,54,55,56,57,58)
AND console_id IS NULL;
```

### Шаг 2: Reauth каналов Группы A (автоматический)

Подключиться к серверу:

```bash
ssh root@46.21.250.43
```

Запустить reauth для всех активных каналов:

```bash
cd /opt/content-fabric/prod
source venv/bin/activate

# Все активные каналы (которые имеют credentials)
python -m cli.reauth --all --headless --no-browser
```

Или по одному для контроля:

```bash
# Каналы без TOTP (должны пройти автоматически)
python -m cli.reauth --channel-id 5 6 7 8 12 13 17 26 28 29 31 32 47 48 --headless --no-browser
```

**Что произойдёт:**
- Selenium откроет Chrome в виртуальном дисплее
- Автоматически введёт email → пароль
- Если Google не запросит доп. проверку — авторизация пройдёт
- Если Google запросит "Tap Yes on phone" — см. Шаг 4

### Шаг 3: Reauth канала knigabooks (ID 21, с TOTP)

```bash
python -m cli.reauth --channel-id 21 --headless --no-browser
```

**Известная проблема:** Google не предлагает Authenticator как метод верификации при входе с сервера. Вместо этого показывает device protection challenge:

![2-Step Verification selection page](reauth_guide_images/02_2step_selection.png)

*На скрине: Google показывает варианты "Tap Yes on phone", SMS (недоступен), Passkey, но НЕ показывает "Google Authenticator".*

**Решение:** см. Шаг 4 или Шаг 5.

### Шаг 4: Ручное подтверждение через телефон

Для каналов, где Google требует "Tap Yes on your phone":

1. Запустить reauth на сервере
2. В течение 2 минут открыть телефон с аккаунтом Google
3. Нажать "Yes, it's me" на push-уведомлении Google
4. Selenium подхватит редирект и завершит авторизацию

**Важно:** нужен доступ к телефону, привязанному к каждому Google аккаунту.

### Шаг 5: Однократный вход для "доверенного устройства"

Чтобы сервер стал "доверенным" и в будущем Google не запрашивал device protection:

1. Установить VNC на сервере (если нет):
```bash
apt install -y tigervnc-standalone-server
vncpasswd  # задать пароль
vncserver :1 -geometry 1920x1080
```

2. Подключиться к VNC с локальной машины:
```bash
ssh -L 5901:localhost:5901 root@46.21.250.43
# Открыть VNC viewer на localhost:5901
```

3. В VNC открыть Chrome:
```bash
DISPLAY=:1 chromium-browser
```

4. Зайти в Google аккаунт вручную, пройти все проверки, поставить галку "Don't ask again on this device"

5. После этого автоматический reauth должен работать без device protection.

### Шаг 6: Reauth каналов Группы B

После назначения `console_id` (Шаг 1):

```bash
python -m cli.reauth --channel-id 46 49 50 51 52 53 54 55 56 57 58 --headless --no-browser
```

### Шаг 7: Проверка результатов

```bash
# Проверить статус токенов в БД
mysql -u content_fabric_user -pmysqlpassword content_fabric -e "
SELECT id, name,
  CASE WHEN access_token IS NOT NULL THEN 'OK' ELSE 'MISSING' END as token,
  token_expires_at
FROM platform_channels
WHERE enabled = 1
ORDER BY token_expires_at;
"

# Проверить логи последних reauth
mysql -u content_fabric_user -pmysqlpassword content_fabric -e "
SELECT channel_id, status, error_message, initiated_at
FROM channel_reauth_audit_logs
ORDER BY initiated_at DESC LIMIT 20;
"

# Скриншоты ошибок Selenium
ls -la data/logs/reauth_failures/
```

---

## Типичные ошибки и решения

### "This browser or app may not be secure"

![Browser not secure error](reauth_guide_images/01_browser_not_secure.png)

**Причина:** Google заблокировал headless Chrome.
**Решение:** Уже исправлено — используется Xvfb виртуальный дисплей вместо `--headless`.

### "Timed out waiting for response from authorization server"

**Причина:** Selenium не смог пройти Google проверку, и OAuth callback на localhost не получил код авторизации.
**Решение:**
- Проверить скриншоты в `data/logs/reauth_failures/`
- Скорее всего Google требует подтверждение на телефоне (Шаг 4)

### "OAuth credentials not configured"

**Причина:** У канала нет `console_id` и нет `YOUTUBE_MAIN_CLIENT_ID` в `.env`.
**Решение:** Назначить `console_id` каналу (Шаг 1).

### Google Authenticator (TOTP) не появляется как опция

![Recovery page without TOTP](reauth_guide_images/04_recovery_page.png)

**Причина:** При входе с нового устройства Google показывает device protection, а не стандартную 2FA.
**Решение:**
1. Зайти в [настройки аккаунта Google](https://myaccount.google.com/signinoptions/two-step-verification) и убедиться что Authenticator app включён
2. Сделать сервер "доверенным устройством" (Шаг 5)

---

## Порядок выполнения (чеклист)

- [ ] **1.** Назначить `console_id` каналам 46–58 (Группа B)
- [ ] **2.** Запустить reauth для каналов без TOTP (Группа A без ID 21):
  ```
  python -m cli.reauth --channel-id 5 6 7 8 12 13 17 26 28 29 31 32 47 48 --headless --no-browser
  ```
- [ ] **3.** Для каналов, потребовавших phone confirmation — подтвердить на телефоне и перезапустить
- [ ] **4.** Сделать сервер "доверенным" для `knigabooks.ru@gmail.com` (Шаг 5)
- [ ] **5.** Запустить reauth для ID 21 (knigabooks)
- [ ] **6.** Запустить reauth для каналов Группы B (46–58)
- [ ] **7.** Проверить результаты (Шаг 7)
