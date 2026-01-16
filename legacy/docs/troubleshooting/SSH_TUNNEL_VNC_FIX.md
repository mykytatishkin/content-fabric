# Исправление проблемы с SSH туннелем для VNC (порт 5901)

## Проблема: "channel 3: open failed: connect failed: Connection refused"

### Симптомы
- SSH подключение работает: `ssh root@46.21.250.43` ✅
- SSH туннель не работает: `ssh -L 5901:localhost:5901 root@46.21.250.43` ❌
- Ошибка: `channel 3: open failed: connect failed: Connection refused`

### Причина
SSH туннель пытается подключиться к порту 5901 на удаленном сервере (`localhost:5901` на сервере), но на этом порту нет запущенного сервиса.

Порт 5901 обычно используется для VNC (Virtual Network Computing), но VNC сервер может быть:
- Не установлен
- Не запущен
- Слушает на другом порту
- Заблокирован файрволом

## Диагностика

### 1. Проверка, что слушает на порту 5901 на сервере

Подключитесь к серверу и выполните:

```bash
# Проверка, что слушает на порту 5901
sudo netstat -tlnp | grep 5901
# или
sudo ss -tlnp | grep 5901

# Проверка всех VNC портов (5900-5910)
sudo netstat -tlnp | grep -E "590[0-9]"
```

**Если ничего не выводится** - значит на порту 5901 нет сервиса.

### 2. Проверка запущенных VNC процессов

```bash
# Проверка VNC процессов
ps aux | grep vnc
# или
systemctl list-units | grep vnc
```

### 3. Проверка установленного VNC

```bash
# Проверка установленного VNC
which vncserver
which x11vnc
dpkg -l | grep vnc  # Ubuntu/Debian
rpm -qa | grep vnc  # CentOS/RHEL
```

## Решения

### Решение 1: Установка и запуск VNC сервера

#### Вариант A: TigerVNC (рекомендуется)

```bash
# Установка
sudo apt update
sudo apt install tigervnc-standalone-server tigervnc-common

# Запуск VNC сервера на дисплее :1 (порт 5901)
vncserver :1 -geometry 1920x1080 -depth 24

# Установка пароля (при первом запуске)
vncpasswd
```

#### Вариант B: x11vnc (для существующей X сессии)

```bash
# Установка
sudo apt install x11vnc

# Запуск на порту 5901
x11vnc -display :0 -auth guess -forever -loop -noxdamage -repeat -rfbauth /root/.vnc/passwd -rfbport 5901 -shared
```

#### Вариант C: VNC через systemd (автозапуск)

```bash
# Создание сервиса
sudo nano /etc/systemd/system/vncserver@.service
```

Содержимое файла:

```ini
[Unit]
Description=Start TigerVNC server at startup
After=syslog.target network.target

[Service]
Type=forking
User=root
Group=root
WorkingDirectory=/root

ExecStartPre=/bin/sh -c '/usr/bin/vncserver -kill :%i > /dev/null 2>&1 || :'
ExecStart=/usr/bin/vncserver -depth 24 -geometry 1920x1080 :%i
ExecStop=/usr/bin/vncserver -kill :%i

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
# Перезагрузка systemd
sudo systemctl daemon-reload

# Запуск VNC на дисплее :1
sudo systemctl enable vncserver@1.service
sudo systemctl start vncserver@1.service

# Проверка статуса
sudo systemctl status vncserver@1.service
```

### Решение 2: Проверка правильного порта VNC

VNC использует порты начиная с 5900:
- Дисплей :0 → порт 5900
- Дисплей :1 → порт 5901
- Дисплей :2 → порт 5902
- и т.д.

Если VNC запущен на другом дисплее, используйте соответствующий порт:

```bash
# Если VNC на дисплее :0 (порт 5900)
ssh -L 5900:localhost:5900 root@46.21.250.43

# Если VNC на дисплее :2 (порт 5902)
ssh -L 5902:localhost:5902 root@46.21.250.43
```

### Решение 3: Настройка файрвола

Если VNC запущен, но туннель не работает, проверьте файрвол:

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 5901/tcp
sudo ufw reload

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=5901/tcp
sudo firewall-cmd --reload
```

**Важно:** Для SSH туннеля файрвол на сервере не должен блокировать localhost:5901, так как туннель идет через SSH (порт 22). Но если вы хотите подключиться к VNC напрямую (без SSH туннеля), нужно открыть порт.

### Решение 4: Использование другого порта для туннеля

Если на сервере нет VNC, но вы хотите создать туннель для другого сервиса:

```bash
# Туннель для MySQL (порт 3306)
ssh -L 3306:localhost:3306 root@46.21.250.43

# Туннель для веб-сервера (порт 80)
ssh -L 8080:localhost:80 root@46.21.250.43

# Туннель для другого сервиса
ssh -L LOCAL_PORT:localhost:REMOTE_PORT root@46.21.250.43
```

## Проверка работы туннеля

### 1. После запуска VNC на сервере

```bash
# На сервере: проверка, что VNC слушает
sudo netstat -tlnp | grep 5901
# Должно показать что-то вроде:
# tcp  0  0  127.0.0.1:5901  0.0.0.0:*  LISTEN  12345/Xvnc
```

### 2. Создание туннеля

```bash
# На локальной машине
ssh -L 5901:localhost:5901 root@46.21.250.43
```

### 3. Подключение к VNC через туннель

```bash
# На локальной машине (в другом терминале)
vncviewer localhost:5901
# или
open vnc://localhost:5901  # macOS
```

## Альтернативные решения

### Решение 5: Использование X11 Forwarding (для GUI приложений)

Если вам нужен только доступ к GUI приложениям, используйте X11 forwarding:

```bash
# Подключение с X11 forwarding
ssh -X root@46.21.250.43

# Запуск GUI приложения
firefox
# или
gedit
```

**Требования:**
- На сервере: `xauth` установлен
- На клиенте: X11 сервер (XQuartz на macOS, Xming на Windows)

### Решение 6: Использование noVNC (веб-интерфейс)

Установите noVNC для доступа через браузер:

```bash
# Установка noVNC
sudo apt install novnc websockify

# Запуск (порт 6080)
websockify --web=/usr/share/novnc/ 6080 localhost:5901
```

Затем откройте в браузере: `http://46.21.250.43:6080/vnc.html`

## Полезные команды

### Управление VNC сервером

```bash
# Список запущенных VNC сессий
vncserver -list

# Остановка VNC на дисплее :1
vncserver -kill :1

# Запуск с опциями
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no
```

### Диагностика SSH туннеля

```bash
# Подробный вывод SSH
ssh -v -L 5901:localhost:5901 root@46.21.250.43

# Проверка локального порта
netstat -an | grep 5901  # на локальной машине
lsof -i :5901            # на локальной машине
```

### Проверка подключения через туннель

```bash
# Проверка, что туннель работает
telnet localhost 5901  # на локальной машине
```

## Безопасность

⚠️ **Важно:** VNC по умолчанию не шифрует трафик. Всегда используйте SSH туннель!

```bash
# ✅ Правильно: через SSH туннель
ssh -L 5901:localhost:5901 root@46.21.250.43

# ❌ Неправильно: прямое подключение (небезопасно)
vncviewer 46.21.250.43:5901
```

Для дополнительной безопасности:

```bash
# Запуск VNC только на localhost
vncserver :1 -localhost yes

# Использование SSH туннеля (обязательно)
ssh -L 5901:localhost:5901 root@46.21.250.43
```

## Резюме

1. **Проверьте, запущен ли VNC на сервере:**
   ```bash
   sudo netstat -tlnp | grep 5901
   ```

2. **Если VNC не запущен - установите и запустите:**
   ```bash
   sudo apt install tigervnc-standalone-server
   vncserver :1
   ```

3. **Создайте SSH туннель:**
   ```bash
   ssh -L 5901:localhost:5901 root@46.21.250.43
   ```

4. **Подключитесь к VNC:**
   ```bash
   vncviewer localhost:5901
   ```

