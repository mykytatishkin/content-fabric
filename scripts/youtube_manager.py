#!/usr/bin/env python3
"""
YouTube Database Manager - CLI for managing YouTube channels in database.
"""

import argparse
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import will be handled by scripts/__init__.py
from core.database.mysql_db import get_mysql_database, YouTubeChannel


def cmd_add_channel(args):
    """Add a new YouTube channel."""
    db = get_mysql_database()
    
    success = db.add_channel(
        name=args.name,
        channel_id=args.channel_id,
        client_id=args.client_id,
        client_secret=args.client_secret,
        enabled=not args.disabled
    )
    
    if success:
        print(f"✅ Канал '{args.name}' успешно добавлен в базу данных!")
    else:
        print(f"❌ Ошибка: Канал '{args.name}' уже существует или произошла ошибка")


def cmd_list_channels(args):
    """List all YouTube channels."""
    db = get_mysql_database()
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
    db = get_mysql_database()
    if db.enable_channel(args.name):
        print(f"✅ Канал '{args.name}' включен")
    else:
        print(f"❌ Канал '{args.name}' не найден")


def cmd_disable_channel(args):
    """Disable a channel."""
    db = get_mysql_database()
    if db.disable_channel(args.name):
        print(f"✅ Канал '{args.name}' отключен")
    else:
        print(f"❌ Канал '{args.name}' не найден")


def cmd_delete_channel(args):
    """Delete a channel."""
    db = get_mysql_database()
    if db.delete_channel(args.name):
        print(f"✅ Канал '{args.name}' удален")
    else:
        print(f"❌ Канал '{args.name}' не найден")


def cmd_show_channel(args):
    """Show detailed channel information."""
    db = get_mysql_database()
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
    db = get_mysql_database()
    config = db.export_config()
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"✅ Конфигурация экспортирована в {args.output}")
    else:
        print(json.dumps(config, indent=2, ensure_ascii=False))


def cmd_import_config(args):
    """Import configuration from config.yaml."""
    db = get_mysql_database()
    
    with open(args.file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    imported = db.import_from_config(config)
    print(f"✅ Импортировано {imported} каналов")


def cmd_check_tokens(args):
    """Check token status for all channels."""
    db = get_mysql_database()
    channels = db.get_all_channels(enabled_only=True)
    
    print("🔑 Статус токенов:")
    for channel in channels:
        if db.is_token_expired(channel.name):
            print(f"  ⚠️ {channel.name}: Токен истек")
        else:
            print(f"  ✅ {channel.name}: Токен действителен")


def cmd_setup_demo():
    """Setup demo channels."""
    db = get_mysql_database()
    
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
        description="YouTube Database Manager - управление каналами через БД"
    )
    
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
        'setup-demo': cmd_setup_demo
    }
    
    handler = command_handlers.get(args.command)
    if handler:
        handler(args)
    else:
        print(f"❌ Неизвестная команда: {args.command}")


if __name__ == '__main__':
    main()
