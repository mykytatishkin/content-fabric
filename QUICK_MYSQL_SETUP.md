# Быстрая настройка MySQL

## 🚀 Быстрый старт

### 1. Установка MySQL на сервер

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install mysql-server
sudo systemctl start mysql
sudo systemctl enable mysql
sudo mysql_secure_installation
```

**CentOS/RHEL:**
```bash
sudo yum install mysql-server
sudo systemctl start mysqld
sudo systemctl enable mysqld
sudo mysql_secure_installation
```

### 2. Создание пользователя и базы данных

```bash
# Подключение к MySQL
sudo mysql -u root -p

# В MySQL консоли:
CREATE DATABASE content_fabric CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'content_fabric_user'@'%' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON content_fabric.* TO 'content_fabric_user'@'%';
FLUSH PRIVILEGES;
EXIT;
```

### 3. Настройка файрвола

```bash
# Ubuntu
sudo ufw allow 3306/tcp

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=3306/tcp
sudo firewall-cmd --reload
```

### 4. Установка Python зависимостей

```bash
pip install mysql-connector-python
# или
pip install -r requirements.txt
```

### 5. Настройка конфигурации

```bash
# Создайте файл конфигурации
cp mysql_config.yaml mysql_config_local.yaml

# Отредактируйте mysql_config_local.yaml:
# - укажите ваш пароль
# - укажите IP адрес сервера если нужно
```

### 6. Создание базы данных и миграция

```bash
# Создание схемы MySQL
python setup_mysql.py --config mysql_config_local.yaml

# Миграция данных из SQLite
python migrate_to_mysql.py \
  --sqlite-path youtube_channels.db \
  --mysql-host your_server_ip \
  --mysql-database content_fabric \
  --mysql-user content_fabric_user \
  --mysql-password your_secure_password
```

### 7. Проверка работы

```bash
# Тест подключения
python setup_mysql.py --config mysql_config_local.yaml --test-only

# Просмотр каналов
python youtube_mysql_manager.py --config mysql_config_local.yaml list

# Статистика
python youtube_mysql_manager.py --config mysql_config_local.yaml stats
```

### 8. Переключение приложения на MySQL

```bash
# Установите переменную окружения
export DB_TYPE=mysql
export MYSQL_HOST=your_server_ip
export MYSQL_DATABASE=content_fabric
export MYSQL_USER=content_fabric_user
export MYSQL_PASSWORD=your_secure_password

# Или добавьте в .env файл:
echo "DB_TYPE=mysql" >> .env
echo "MYSQL_HOST=your_server_ip" >> .env
echo "MYSQL_DATABASE=content_fabric" >> .env
echo "MYSQL_USER=content_fabric_user" >> .env
echo "MYSQL_PASSWORD=your_secure_password" >> .env
```

## 🔧 Полезные команды

### Управление каналами

```bash
# Добавить канал
python youtube_mysql_manager.py add "My Channel" \
  --channel-id "UC123456789" \
  --client-id "your_client_id" \
  --client-secret "your_client_secret"

# Список каналов
python youtube_mysql_manager.py list

# Информация о канале
python youtube_mysql_manager.py show "My Channel"

# Включить/отключить канал
python youtube_mysql_manager.py enable "My Channel"
python youtube_mysql_manager.py disable "My Channel"
```

### Резервное копирование

```bash
# Создание дампа
mysqldump -u content_fabric_user -p content_fabric > backup.sql

# Восстановление
mysql -u content_fabric_user -p content_fabric < backup.sql
```

## 🚨 Устранение неполадок

### Проблемы с подключением

1. **Проверьте статус MySQL:**
   ```bash
   sudo systemctl status mysql
   ```

2. **Проверьте конфигурацию:**
   ```bash
   python setup_mysql.py --test-only
   ```

3. **Проверьте логи:**
   ```bash
   sudo tail -f /var/log/mysql/error.log
   ```

### Проблемы с правами доступа

```bash
# Проверьте права пользователя
mysql -u content_fabric_user -p -e "SHOW GRANTS;"

# Если нужно, обновите права:
mysql -u root -p
GRANT ALL PRIVILEGES ON content_fabric.* TO 'content_fabric_user'@'%';
FLUSH PRIVILEGES;
```

## 📚 Дополнительная документация

- [Полное руководство по настройке MySQL](docs/MYSQL_SETUP_GUIDE.md)
- [Детальное руководство по миграции](docs/MYSQL_MIGRATION_GUIDE.md)
- [Техническая документация](TECHNICAL_DOCS.md)
