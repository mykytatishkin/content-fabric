#!/usr/bin/env python3
"""
YouTube MySQL Database Manager - CLI for managing YouTube channels in MySQL database.
"""

import argparse
import sys
import json
import os
import yaml
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.database import get_database_by_type
from src.mysql_database import YouTubeMySQLDatabase


def load_config(config_file: str = None) -> dict:
    """Load MySQL configuration."""
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f) if config_file.endswith('.json') else yaml.safe_load(f)
            return config.get('mysql', {})
    
    # Fallback to environment variables
    return {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'database': os.getenv('MYSQL_DATABASE', 'content_fabric'),
        'user': os.getenv('MYSQL_USER', 'content_fabric_user'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci'
    }


def get_database_instance(config_file: str = None) -> YouTubeMySQLDatabase:
    """Get MySQL database instance."""
    config = load_config(config_file)
    return YouTubeMySQLDatabase(config)


def cmd_add_channel(args):
    """Add a new YouTube channel."""
    db = get_database_instance(args.config)
    
    success = db.add_channel(
        name=args.name,
        channel_id=args.channel_id,
        client_id=args.client_id,
        client_secret=args.client_secret,
        enabled=not args.disabled
    )
    
    if success:
        print(f"✅ Канал '{args.name}' успешно добавлен в MySQL базу данных!")
    else:
        print(f"❌ Ошибка: Канал '{args.name}' уже существует или произошла ошибка")


def cmd_list_channels(args):
    """List all YouTube channels."""
    db = get_database_instance(args.config)
    channels = db.get_all_channels(enabled_only=args.enabled_only)
    
    if not channels:
        print("📭 YouTube каналы не найдены")
        return
    
    print("📺 YouTube каналы:")
    for i, channel in enumerate(channels, 1):
        status = "✅" if channel.enabled else "❌"
        token_status = "🔑" if channel.access_token else "🔒"
        expired = "⚠️" if db.is_token_expired(channel.name) else "✅"
        
        print(f"  {i}. {status} {channel.name} (ID: {channel.channel_id})")
        print(f"     Токен: {token_status} {expired}")
        if channel.token_expires_at:
            print(f"     Истекает: {channel.token_expires_at}")


def cmd_enable_channel(args):
    """Enable a channel."""
    db = get_database_instance(args.config)
    if db.enable_channel(args.name):
        print(f"✅ Канал '{args.name}' включен")
    else:
        print(f"❌ Канал '{args.name}' не найден")


def cmd_disable_channel(args):
    """Disable a channel."""
    db = get_database_instance(args.config)
    if db.disable_channel(args.name):
        print(f"✅ Канал '{args.name}' отключен")
    else:
        print(f"❌ Канал '{args.name}' не найден")


def cmd_delete_channel(args):
    """Delete a channel."""
    db = get_database_instance(args.config)
    if db.delete_channel(args.name):
        print(f"✅ Канал '{args.name}' удален")
    else:
        print(f"❌ Канал '{args.name}' не найден")


def cmd_show_channel(args):
    """Show detailed channel information."""
    db = get_database_instance(args.config)
    channel = db.get_channel(args.name)
    
    if not channel:
        print(f"❌ Канал '{args.name}' не найден")
        return
    
    print(f"📺 Канал: {channel.name}")
    print(f"   ID: {channel.channel_id}")
    print(f"   Client ID: {channel.client_id[:20]}...")
    print(f"   Статус: {'✅ Включен' if channel.enabled else '❌ Отключен'}")
    print(f"   Токен: {'🔑 Есть' if channel.access_token else '🔒 Нет'}")
    print(f"   Истекает: {channel.token_expires_at or 'Не установлено'}")
    print(f"   Создан: {channel.created_at}")
    print(f"   Обновлен: {channel.updated_at}")


def cmd_export_config(args):
    """Export configuration to config.yaml format."""
    db = get_database_instance(args.config)
    config = db.export_config()
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ Конфигурация экспортирована в {args.output}")
    else:
        print(json.dumps(config, indent=2, ensure_ascii=False))


def cmd_import_config(args):
    """Import configuration from config.yaml."""
    db = get_database_instance(args.config)
    
    with open(args.file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    imported = db.import_from_config(config)
    print(f"✅ Импортировано {imported} каналов")


def cmd_check_tokens(args):
    """Check token status for all channels."""
    db = get_database_instance(args.config)
    channels = db.get_all_channels(enabled_only=True)
    
    print("🔑 Статус токенов:")
    for channel in channels:
        if db.is_token_expired(channel.name):
            print(f"  ⚠️ {channel.name}: Токен истек")
        else:
            print(f"  ✅ {channel.name}: Токен действителен")


def cmd_database_stats(args):
    """Show database statistics."""
    db = get_database_instance(args.config)
    stats = db.get_database_stats()
    
    print("📊 Статистика базы данных:")
    print(f"   Всего каналов: {stats.get('total_channels', 0)}")
    print(f"   Включенных: {stats.get('enabled_channels', 0)}")
    print(f"   Отключенных: {stats.get('disabled_channels', 0)}")
    print(f"   Всего токенов: {stats.get('total_tokens', 0)}")
    print(f"   Истекших токенов: {stats.get('expired_tokens', 0)}")


def cmd_setup_demo():
    """Setup demo channels."""
    db = get_database_instance()
    
    # Add demo channels
    demo_channels = [
        {
            'name': 'Teasera',
            'channel_id': 'teasera-git',
            'client_id': '${YOUTUBE_TEASERA_CLIENT_ID}',
            'client_secret': '${YOUTUBE_TEASERA_CLIENT_SECRET}',
            'enabled': True
        },
        {
            'name': 'Andrew Garle',
            'channel_id': '@AndrewGarle',
            'client_id': '${YOUTUBE_ANDREW_CLIENT_ID}',
            'client_secret': '${YOUTUBE_ANDREW_CLIENT_SECRET}',
            'enabled': True
        }
    ]
    
    added_count = 0
    for channel_data in demo_channels:
        if db.add_channel(**channel_data):
            added_count += 1
    
    print(f"✅ Добавлено {added_count} демо каналов")
    print("📝 Не забудьте обновить .env файл с реальными credentials!")


def main():
    parser = argparse.ArgumentParser(
        description="YouTube MySQL Database Manager - управление каналами через MySQL БД"
    )
    parser.add_argument('--config', default='mysql_config.yaml', 
                       help='MySQL configuration file')
    
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Add channel command
    add_parser = subparsers.add_parser('add', help='Добавить новый канал')
    add_parser.add_argument('name', help='Название канала')
    add_parser.add_argument('--channel-id', required=True, help='ID канала')
    add_parser.add_argument('--client-id', required=True, help='Client ID')
    add_parser.add_argument('--client-secret', required=True, help='Client Secret')
    add_parser.add_argument('--disabled', action='store_true', help='Добавить отключенным')
    
    # List channels command
    list_parser = subparsers.add_parser('list', help='Показать список каналов')
    list_parser.add_argument('--enabled-only', action='store_true', help='Только включенные каналы')
    
    # Enable/disable commands
    enable_parser = subparsers.add_parser('enable', help='Включить канал')
    enable_parser.add_argument('name', help='Название канала')
    
    disable_parser = subparsers.add_parser('disable', help='Отключить канал')
    disable_parser.add_argument('name', help='Название канала')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Удалить канал')
    delete_parser.add_argument('name', help='Название канала')
    
    # Show channel command
    show_parser = subparsers.add_parser('show', help='Показать информацию о канале')
    show_parser.add_argument('name', help='Название канала')
    
    # Export/import commands
    export_parser = subparsers.add_parser('export', help='Экспортировать конфигурацию')
    export_parser.add_argument('--output', help='Файл для экспорта')
    
    import_parser = subparsers.add_parser('import', help='Импортировать конфигурацию')
    import_parser.add_argument('file', help='Файл конфигурации')
    
    # Check tokens command
    subparsers.add_parser('check-tokens', help='Проверить статус токенов')
    
    # Database stats command
    subparsers.add_parser('stats', help='Показать статистику базы данных')
    
    # Setup demo command
    subparsers.add_parser('setup-demo', help='Настроить демо каналы')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Route to command handler
    command_handlers = {
        'add': cmd_add_channel,
        'list': cmd_list_channels,
        'enable': cmd_enable_channel,
        'disable': cmd_disable_channel,
        'delete': cmd_delete_channel,
        'show': cmd_show_channel,
        'export': cmd_export_config,
        'import': cmd_import_config,
        'check-tokens': cmd_check_tokens,
        'stats': cmd_database_stats,
        'setup-demo': cmd_setup_demo
    }
    
    handler = command_handlers.get(args.command)
    if handler:
        try:
            handler(args)
        except Exception as e:
            print(f"❌ Ошибка выполнения команды: {e}")
    else:
        print(f"❌ Неизвестная команда: {args.command}")


if __name__ == '__main__':
    main()
