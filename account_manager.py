#!/usr/bin/env python3
"""
Утилита для управления множественными аккаунтами социальных сетей.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Добавить путь к модулям
sys.path.append(str(Path(__file__).parent / "src"))

from src.auto_poster import SocialMediaAutoPoster
from src.logger import get_logger


def main():
    parser = argparse.ArgumentParser(
        description="Управление множественными аккаунтами социальных сетей"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Команда для проверки статуса аккаунтов
    status_parser = subparsers.add_parser('status', help='Проверить статус всех аккаунтов')
    status_parser.add_argument('--platform', choices=['instagram', 'tiktok', 'youtube'], 
                              help='Проверить только конкретную платформу')
    status_parser.add_argument('--json', action='store_true', help='Вывод в JSON формате')
    
    # Команда для авторизации аккаунтов
    auth_parser = subparsers.add_parser('authorize', help='Авторизовать аккаунты')
    auth_parser.add_argument('--platform', choices=['instagram', 'tiktok', 'youtube'], 
                            help='Авторизовать аккаунты конкретной платформы')
    auth_parser.add_argument('--account', help='Авторизовать конкретный аккаунт')
    auth_parser.add_argument('--all', action='store_true', help='Авторизовать все аккаунты')
    auth_parser.add_argument('--no-browser', action='store_true', help='Не открывать браузер автоматически')
    
    # Команда для обновления токенов
    refresh_parser = subparsers.add_parser('refresh', help='Обновить токены аккаунтов')
    refresh_parser.add_argument('--platform', choices=['instagram', 'tiktok', 'youtube'], 
                               help='Обновить токены конкретной платформы')
    refresh_parser.add_argument('--account', help='Обновить токен конкретного аккаунта')
    
    # Команда для валидации аккаунтов
    validate_parser = subparsers.add_parser('validate', help='Валидировать аккаунты')
    validate_parser.add_argument('--platform', choices=['instagram', 'tiktok', 'youtube'], 
                                help='Валидировать аккаунты конкретной платформы')
    validate_parser.add_argument('--json', action='store_true', help='Вывод в JSON формате')
    
    # Команда для получения URL авторизации
    url_parser = subparsers.add_parser('auth-url', help='Получить URL для авторизации')
    url_parser.add_argument('platform', choices=['instagram', 'tiktok', 'youtube'], 
                           help='Платформа')
    url_parser.add_argument('account', help='Имя аккаунта')
    
    # Команда для добавления токена вручную
    token_parser = subparsers.add_parser('add-token', help='Добавить токен вручную')
    token_parser.add_argument('platform', choices=['instagram', 'tiktok', 'youtube'], 
                             help='Платформа')
    token_parser.add_argument('account', help='Имя аккаунта')
    token_parser.add_argument('access_token', help='Токен доступа')
    token_parser.add_argument('--refresh-token', help='Токен обновления')
    token_parser.add_argument('--expires-in', type=int, help='Время жизни токена в секундах')
    
    # Команда для удаления токена
    remove_parser = subparsers.add_parser('remove-token', help='Удалить токен аккаунта')
    remove_parser.add_argument('platform', choices=['instagram', 'tiktok', 'youtube'], 
                              help='Платформа')
    remove_parser.add_argument('account', help='Имя аккаунта')
    
    # Команда для получения информации о токене
    info_parser = subparsers.add_parser('token-info', help='Получить информацию о токене')
    info_parser.add_argument('platform', choices=['instagram', 'tiktok', 'youtube'], 
                            help='Платформа')
    info_parser.add_argument('account', help='Имя аккаунта')
    
    # Команда для добавления нового канала
    add_channel_parser = subparsers.add_parser('add-channel', help='Добавить новый YouTube канал')
    add_channel_parser.add_argument('name', help='Имя канала в системе')
    add_channel_parser.add_argument('channel_id', help='ID YouTube канала')
    add_channel_parser.add_argument('--auto-auth', action='store_true', 
                                   help='Автоматически авторизовать канал после добавления')
    
    # Команда для миграции из YAML в базу данных
    migrate_parser = subparsers.add_parser('migrate', help='Мигрировать каналы из YAML в базу данных')
    migrate_parser.add_argument('--dry-run', action='store_true', 
                               help='Показать что будет мигрировано без выполнения')
    
    # Команда для работы с базой данных
    db_parser = subparsers.add_parser('db', help='Управление базой данных каналов')
    db_subparsers = db_parser.add_subparsers(dest='db_command', help='Команды базы данных')
    
    # db list - список каналов в БД
    db_list_parser = db_subparsers.add_parser('list', help='Показать все каналы в базе данных')
    db_list_parser.add_argument('--enabled-only', action='store_true', help='Показать только включенные каналы')
    
    # db add - добавить канал в БД
    db_add_parser = db_subparsers.add_parser('add', help='Добавить канал в базу данных')
    db_add_parser.add_argument('name', help='Имя канала')
    db_add_parser.add_argument('channel_id', help='ID YouTube канала')
    db_add_parser.add_argument('--client-id', help='OAuth Client ID (по умолчанию из .env)')
    db_add_parser.add_argument('--client-secret', help='OAuth Client Secret (по умолчанию из .env)')
    db_add_parser.add_argument('--disabled', action='store_true', help='Добавить как отключенный')
    
    # db remove - удалить канал из БД
    db_remove_parser = db_subparsers.add_parser('remove', help='Удалить канал из базы данных')
    db_remove_parser.add_argument('name', help='Имя канала для удаления')
    info_parser.add_argument('--json', action='store_true', help='Вывод в JSON формате')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Инициализировать автопостер
    try:
        auto_poster = SocialMediaAutoPoster()
        logger = get_logger("account_manager")
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        return
    
    # Выполнить команду
    try:
        if args.command == 'status':
            handle_status(auto_poster, args)
        elif args.command == 'authorize':
            handle_authorize(auto_poster, args)
        elif args.command == 'refresh':
            handle_refresh(auto_poster, args)
        elif args.command == 'validate':
            handle_validate(auto_poster, args)
        elif args.command == 'auth-url':
            handle_auth_url(auto_poster, args)
        elif args.command == 'add-token':
            handle_add_token(auto_poster, args)
        elif args.command == 'remove-token':
            handle_remove_token(auto_poster, args)
        elif args.command == 'token-info':
            handle_token_info(auto_poster, args)
        elif args.command == 'add-channel':
            handle_add_channel(auto_poster, args)
        elif args.command == 'migrate':
            handle_migrate(auto_poster, args)
        elif args.command == 'db':
            handle_db_command(auto_poster, args)
            
    except Exception as e:
        print(f"❌ Ошибка выполнения команды: {e}")


def handle_status(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команду status."""
    print("🔍 Проверка статуса аккаунтов...")
    
    system_status = auto_poster.get_system_status()
    account_status = system_status.get('account_status', {})
    token_status = system_status.get('token_status', {})
    
    if args.json:
        print(json.dumps({
            'account_status': account_status,
            'token_status': token_status
        }, indent=2, ensure_ascii=False))
        return
    
    platforms = [args.platform] if args.platform else ['instagram', 'tiktok', 'youtube']
    
    for platform in platforms:
        platform_accounts = account_status.get('platforms', {}).get(platform, {})
        platform_tokens = token_status.get('platforms', {}).get(platform, {})
        
        print(f"\n📱 {platform.upper()}:")
        print(f"   Всего аккаунтов: {platform_accounts.get('total', 0)}")
        print(f"   Авторизованных: {platform_accounts.get('authorized', 0)}")
        
        if platform_tokens:
            print(f"   Действительных токенов: {platform_tokens.get('valid', 0)}")
            print(f"   Истекших токенов: {platform_tokens.get('expired', 0)}")
        
        accounts = platform_accounts.get('accounts', {})
        for account_name, account_info in accounts.items():
            status_icon = "✅" if account_info.get('authorized') else "❌"
            token_icon = "🟢" if account_info.get('token_valid') else "🔴"
            
            print(f"   {status_icon} {account_name}")
            if account_info.get('expires_at'):
                print(f"      Токен истекает: {account_info['expires_at']}")
            if account_info.get('last_refreshed'):
                print(f"      Последнее обновление: {account_info['last_refreshed']}")


def handle_authorize(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команду authorize."""
    if args.all:
        print("🔐 Авторизация всех аккаунтов...")
        results = auto_poster.authorize_all_accounts(args.platform)
        
        for platform, accounts in results.items():
            print(f"\n📱 {platform.upper()}:")
            for account_name, result in accounts.items():
                if result.get('success'):
                    print(f"   ✅ {account_name} - успешно авторизован")
                else:
                    print(f"   ❌ {account_name} - ошибка: {result.get('error')}")
                    
    elif args.platform and args.account:
        print(f"🔐 Авторизация {args.platform}:{args.account}...")
        result = auto_poster.authorize_account(
            platform=args.platform,
            account_name=args.account,
            auto_open_browser=not args.no_browser
        )
        
        if result.get('success'):
            print(f"✅ Аккаунт {args.platform}:{args.account} успешно авторизован")
            if result.get('expires_in'):
                print(f"   Токен действителен {result['expires_in']} секунд")
        else:
            print(f"❌ Ошибка авторизации: {result.get('error')}")
            
    else:
        print("❌ Укажите --all или --platform и --account")


def handle_refresh(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команду refresh."""
    print("🔄 Обновление токенов...")
    
    results = auto_poster.refresh_account_tokens(args.platform, args.account)
    
    for account_key, success in results.items():
        if success:
            print(f"✅ {account_key} - токен обновлен")
        else:
            print(f"❌ {account_key} - не удалось обновить токен")


def handle_validate(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команду validate."""
    print("✅ Валидация аккаунтов...")
    
    results = auto_poster.validate_all_accounts_extended()
    
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    
    platforms = [args.platform] if args.platform else results.keys()
    
    for platform in platforms:
        if platform not in results:
            continue
            
        print(f"\n📱 {platform.upper()}:")
        accounts = results[platform]
        
        for account_name, account_info in accounts.items():
            if account_info.get('valid'):
                print(f"   ✅ {account_name} - валиден")
            else:
                print(f"   ❌ {account_name} - невалиден")
                if account_info.get('error'):
                    print(f"      Ошибка: {account_info['error']}")
                
                print(f"      Включен: {account_info.get('enabled', False)}")
                print(f"      Есть токен: {account_info.get('has_token', False)}")
                print(f"      Токен валиден: {account_info.get('token_valid', False)}")


def handle_auth_url(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команду auth-url."""
    print(f"🔗 Получение URL авторизации для {args.platform}:{args.account}...")
    
    url = auto_poster.get_account_authorization_url(args.platform, args.account)
    
    if url:
        print(f"✅ URL авторизации:")
        print(f"   {url}")
        print("\n📋 Скопируйте ссылку и откройте в браузере для авторизации")
    else:
        print("❌ Не удалось получить URL авторизации")


def handle_add_token(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команду add-token."""
    print(f"➕ Добавление токена для {args.platform}:{args.account}...")
    
    success = auto_poster.add_account_token(
        platform=args.platform,
        account_name=args.account,
        access_token=args.access_token,
        refresh_token=args.refresh_token,
        expires_in=args.expires_in
    )
    
    if success:
        print(f"✅ Токен успешно добавлен для {args.platform}:{args.account}")
    else:
        print(f"❌ Не удалось добавить токен для {args.platform}:{args.account}")


def handle_remove_token(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команду remove-token."""
    print(f"➖ Удаление токена для {args.platform}:{args.account}...")
    
    success = auto_poster.remove_account_token(args.platform, args.account)
    
    if success:
        print(f"✅ Токен успешно удален для {args.platform}:{args.account}")
    else:
        print(f"❌ Не удалось удалить токен для {args.platform}:{args.account}")


def handle_token_info(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команду token-info."""
    print(f"ℹ️ Информация о токене {args.platform}:{args.account}...")
    
    info = auto_poster.get_account_token_info(args.platform, args.account)
    
    if not info:
        print(f"❌ Токен не найден для {args.platform}:{args.account}")
        return
    
    if args.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return
    
    print(f"📊 Информация о токене:")
    print(f"   Платформа: {info['platform']}")
    print(f"   Аккаунт: {info['account_name']}")
    print(f"   Есть refresh токен: {info['has_refresh_token']}")
    print(f"   Истекает: {info['expires_at'] or 'Никогда'}")
    print(f"   Создан: {info['created_at'] or 'Неизвестно'}")
    print(f"   Последнее обновление: {info['last_refreshed'] or 'Никогда'}")
    print(f"   Истек: {'Да' if info['is_expired'] else 'Нет'}")
    
    if info.get('scope'):
        print(f"   Права доступа: {info['scope']}")


def handle_add_channel(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команду add-channel."""
    from src.database_config_loader import DatabaseConfigLoader
    
    print(f"➕ Добавление нового YouTube канала: {args.name}")
    
    # Создаем DatabaseConfigLoader для работы с БД
    db_loader = DatabaseConfigLoader()
    
    # Добавляем канал в базу данных
    success = db_loader.add_youtube_channel(
        name=args.name,
        channel_id=args.channel_id
    )
    
    if success:
        print(f"✅ Канал '{args.name}' успешно добавлен в базу данных!")
        
        if args.auto_auth:
            print(f"🔐 Авторизация канала '{args.name}'...")
            auth_result = auto_poster.oauth_manager.authorize_account("youtube", args.name)
            if auth_result.get('success'):
                print(f"✅ Канал '{args.name}' успешно авторизован!")
            else:
                print(f"❌ Ошибка авторизации: {auth_result.get('error')}")
    else:
        print(f"❌ Ошибка: Канал '{args.name}' уже существует или произошла ошибка")


def handle_migrate(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команду migrate."""
    from src.database_config_loader import DatabaseConfigLoader
    
    print("🔄 Миграция каналов из YAML в базу данных...")
    
    db_loader = DatabaseConfigLoader()
    
    if args.dry_run:
        print("🔍 Режим предварительного просмотра:")
        # Загружаем YAML конфигурацию
        yaml_config = auto_poster.config
        youtube_accounts = yaml_config.get('accounts', {}).get('youtube', [])
        
        print(f"📋 Найдено {len(youtube_accounts)} каналов в YAML:")
        for account in youtube_accounts:
            name = account.get('name', 'Unknown')
            channel_id = account.get('channel_id', 'Unknown')
            enabled = account.get('enabled', True)
            status = "✅" if enabled else "❌"
            print(f"   {status} {name} ({channel_id})")
        
        print("\n💡 Для выполнения миграции запустите команду без --dry-run")
    else:
        migrated_count = db_loader.migrate_from_yaml()
        print(f"✅ Мигрировано {migrated_count} каналов из YAML в базу данных")
        
        if migrated_count > 0:
            print("💡 Теперь вы можете использовать базу данных для управления каналами")
            print("   Используйте: python3 account_manager.py db list")


def handle_db_command(auto_poster: SocialMediaAutoPoster, args):
    """Обработать команды работы с базой данных."""
    from src.database_config_loader import DatabaseConfigLoader
    
    db_loader = DatabaseConfigLoader()
    
    if args.db_command == 'list':
        print("📺 Каналы в базе данных:")
        status = db_loader.get_channel_status()
        
        if status['total'] == 0:
            print("📭 Каналы не найдены")
            return
        
        print(f"   Всего: {status['total']}")
        print(f"   Включенных: {status['enabled']}")
        print(f"   Авторизованных: {status['authorized']}")
        print(f"   Действительных токенов: {status['valid_tokens']}")
        print(f"   Истекших токенов: {status['expired_tokens']}")
        print()
        
        for name, info in status['channels'].items():
            if args.enabled_only and not info['enabled']:
                continue
                
            status_icon = "✅" if info['enabled'] else "❌"
            auth_icon = "🔑" if info['authorized'] else "🔒"
            token_icon = "🟢" if info['token_valid'] else "🔴"
            
            print(f"   {status_icon} {auth_icon} {token_icon} {name}")
            if info['expires_at']:
                print(f"      Токен истекает: {info['expires_at']}")
            if info['created_at']:
                print(f"      Создан: {info['created_at']}")
    
    elif args.db_command == 'add':
        print(f"➕ Добавление канала '{args.name}' в базу данных...")
        success = db_loader.add_youtube_channel(
            name=args.name,
            channel_id=args.channel_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
            enabled=not args.disabled
        )
        
        if success:
            print(f"✅ Канал '{args.name}' успешно добавлен!")
        else:
            print(f"❌ Ошибка: Канал '{args.name}' уже существует")
    
    elif args.db_command == 'remove':
        print(f"🗑️ Удаление канала '{args.name}' из базы данных...")
        success = db_loader.remove_youtube_channel(args.name)
        
        if success:
            print(f"✅ Канал '{args.name}' успешно удален!")
        else:
            print(f"❌ Ошибка: Канал '{args.name}' не найден")


if __name__ == "__main__":
    main()
