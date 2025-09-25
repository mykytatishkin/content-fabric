#!/usr/bin/env python3
"""
Скрипт для автоматического добавления YouTube каналов в конфигурацию.
"""

import argparse
import yaml
import sys
from pathlib import Path

def add_youtube_channel(channel_name, channel_id=None, enabled=True):
    """Добавить новый YouTube канал в конфигурацию."""
    
    config_path = "config.yaml"
    
    # Загрузить конфигурацию
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Проверить, существует ли уже канал
    existing_channels = config.get('accounts', {}).get('youtube', [])
    for channel in existing_channels:
        if channel.get('name') == channel_name:
            print(f"❌ Канал '{channel_name}' уже существует!")
            return False
    
    # Добавить новый канал
    new_channel = {
        'name': channel_name,
        'channel_id': channel_id or f"{channel_name.lower()}-channel",
        'client_id': "${YOUTUBE_MAIN_CLIENT_ID}",
        'client_secret': "${YOUTUBE_MAIN_CLIENT_SECRET}",
        'credentials_file': "credentials.json",
        'enabled': enabled
    }
    
    existing_channels.append(new_channel)
    config['accounts']['youtube'] = existing_channels
    
    # Сохранить конфигурацию
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    print(f"✅ Канал '{channel_name}' успешно добавлен в конфигурацию!")
    return True

def list_youtube_channels():
    """Показать список всех YouTube каналов."""
    
    config_path = "config.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    channels = config.get('accounts', {}).get('youtube', [])
    
    if not channels:
        print("📭 YouTube каналы не найдены")
        return
    
    print("📺 YouTube каналы:")
    for i, channel in enumerate(channels, 1):
        status = "✅" if channel.get('enabled', False) else "❌"
        channel_id = channel.get('channel_id', 'не указан')
        print(f"  {i}. {status} {channel['name']} (ID: {channel_id})")

def main():
    parser = argparse.ArgumentParser(description="Управление YouTube каналами")
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Команда добавления канала
    add_parser = subparsers.add_parser('add', help='Добавить новый канал')
    add_parser.add_argument('name', help='Название канала')
    add_parser.add_argument('--channel-id', help='ID канала (опционально)')
    add_parser.add_argument('--disabled', action='store_true', help='Добавить отключенным')
    
    # Команда списка каналов
    subparsers.add_parser('list', help='Показать список каналов')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        enabled = not args.disabled
        add_youtube_channel(args.name, args.channel_id, enabled)
    elif args.command == 'list':
        list_youtube_channels()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
