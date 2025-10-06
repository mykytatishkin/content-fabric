# MySQL Setup Guide

## Установка MySQL на сервер

### Ubuntu/Debian

```bash
# Обновление пакетов
sudo apt update

# Установка MySQL Server
sudo apt install mysql-server

# Запуск и включение автозапуска
sudo systemctl start mysql
sudo systemctl enable mysql

# Безопасная настройка MySQL
sudo mysql_secure_installation
```

### CentOS/RHEL/Rocky Linux

```bash
# Установка MySQL Server
sudo yum install mysql-server

# Или для новых версий
sudo dnf install mysql-server

# Запуск и включение автозапуска
sudo systemctl start mysqld
sudo systemctl enable mysqld

# Безопасная настройка
sudo mysql_secure_installation
```

### macOS (с Homebrew)

```bash
# Установка MySQL
brew install mysql

# Запуск MySQL
brew services start mysql

# Безопасная настройка
mysql_secure_installation
```

## Настройка пользователя для внешних подключений

### 1. Подключение к MySQL как root

```bash
sudo mysql -u root -p
```

### 2. Создание пользователя для приложения

```sql
-- Создание пользователя
CREATE USER 'content_fabric_user'@'%' IDENTIFIED BY 'your_secure_password';

-- Предоставление всех привилегий на базу данных
GRANT ALL PRIVILEGES ON content_fabric.* TO 'content_fabric_user'@'%';

-- Применение изменений
FLUSH PRIVILEGES;
```

### 3. Создание базы данных

```sql
-- Создание базы данных
CREATE DATABASE content_fabric CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Подтверждение создания
SHOW DATABASES;
```

### 4. Настройка удаленных подключений

#### Редактирование конфигурации MySQL

```bash
# Найти файл конфигурации
sudo find /etc -name "my.cnf" 2>/dev/null

# Обычно находится в одном из:
# /etc/mysql/my.cnf
# /etc/my.cnf
# /usr/etc/my.cnf
```

#### Добавление в my.cnf:

```ini
[mysqld]
bind-address = 0.0.0.0
port = 3306

# Настройки для лучшей производительности
max_connections = 200
innodb_buffer_pool_size = 256M
innodb_log_file_size = 64M
```

#### Перезапуск MySQL:

```bash
# Ubuntu/Debian
sudo systemctl restart mysql

# CentOS/RHEL
sudo systemctl restart mysqld
```

### 5. Настройка файрвола

#### Ubuntu (ufw):
```bash
sudo ufw allow 3306/tcp
```

#### CentOS/RHEL (firewalld):
```bash
sudo firewall-cmd --permanent --add-port=3306/tcp
sudo firewall-cmd --reload
```

### 6. Проверка подключения

```bash
# Локальное подключение
mysql -u content_fabric_user -p -h localhost content_fabric

# Удаленное подключение (с другого сервера)
mysql -u content_fabric_user -p -h YOUR_SERVER_IP content_fabric
```

## Безопасность

### Рекомендации по безопасности:

1. **Используйте сильные пароли** (минимум 12 символов, смешанные символы)
2. **Ограничьте доступ по IP** если возможно:
   ```sql
   CREATE USER 'content_fabric_user'@'192.168.1.%' IDENTIFIED BY 'password';
   ```
3. **Регулярно обновляйте MySQL**
4. **Используйте SSL соединения** для продакшена
5. **Регулярно делайте бэкапы**

### Настройка SSL (опционально):

```sql
-- Проверка SSL статуса
SHOW VARIABLES LIKE 'have_ssl';

-- Принудительное использование SSL для пользователя
ALTER USER 'content_fabric_user'@'%' REQUIRE SSL;
```

## Мониторинг и обслуживание

### Полезные команды:

```sql
-- Показать все пользователи
SELECT user, host FROM mysql.user;

-- Показать привилегии пользователя
SHOW GRANTS FOR 'content_fabric_user'@'%';

-- Показать активные подключения
SHOW PROCESSLIST;

-- Показать статус сервера
SHOW STATUS;
```

### Логирование:

```bash
# Просмотр логов ошибок
sudo tail -f /var/log/mysql/error.log

# Просмотр общих логов
sudo tail -f /var/log/mysql/mysql.log
```
