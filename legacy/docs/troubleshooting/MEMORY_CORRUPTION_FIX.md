# Исправление ошибки "free(): invalid next size (normal)"

## Проблема

Процесс падал с ошибкой:
```
free(): invalid next size (normal)
Aborted (core dumped)
```

Эта ошибка указывает на **повреждение кучи (heap corruption)** в C/C++ коде, что обычно происходит при неправильном управлении памятью.

## Причина

Проблема была вызвана тем, что **ре-аутентификация YouTube каналов запускалась в daemon thread** (`daemon=True`), который может быть убит в любой момент, когда основной процесс завершается.

Когда основной процесс падал или завершался:
1. Daemon thread немедленно убивался системой
2. Playwright браузер мог находиться в процессе работы с памятью
3. Ресурсы не успевали правильно освободиться
4. Это вызывало повреждение кучи и падение процесса

## Решение

### 1. Изменен тип потока ре-аутентификации

**Было:**
```python
reauth_thread = threading.Thread(
    target=self._run_reauth_in_background,
    args=(channel_name,),
    daemon=True,  # ❌ Проблема!
    name=f"Reauth-{channel_name}"
)
```

**Стало:**
```python
reauth_thread = threading.Thread(
    target=self._run_reauth_in_background,
    args=(channel_name,),
    daemon=False,  # ✅ Исправлено
    name=f"Reauth-{channel_name}"
)
```

### 2. Улучшена обработка исключений в Playwright

Добавлена защита от ошибок при закрытии ресурсов Playwright:

```python
finally:
    # Ensure proper cleanup of Playwright resources
    try:
        await context.close()
    except Exception as e:
        LOGGER.warning(f"Error closing context: {e}")
    
    try:
        await playwright.stop()
    except Exception as e:
        LOGGER.warning(f"Error stopping Playwright: {e}")
```

### 3. Добавлено отслеживание потоков ре-аутентификации

Теперь все потоки ре-аутентификации отслеживаются и правильно завершаются при остановке worker'а:

```python
# Track reauth threads for proper cleanup
self.reauth_threads: Dict[str, threading.Thread] = {}
```

### 4. Улучшен метод stop()

При остановке worker'а теперь ждем завершения всех потоков ре-аутентификации:

```python
def stop(self):
    """Stop the task worker."""
    self.running = False
    if self.worker_thread:
        self.worker_thread.join(timeout=5)
    
    # Wait for reauth threads to complete (with timeout)
    if self.reauth_threads:
        for channel_name, thread in self.reauth_threads.items():
            if thread.is_alive():
                thread.join(timeout=30)  # Give time to clean up
```

## Файлы изменены

1. `app/task_worker.py`:
   - Изменен `daemon=True` на `daemon=False` для потоков ре-аутентификации
   - Добавлено отслеживание потоков ре-аутентификации
   - Улучшена обработка исключений
   - Улучшен метод `stop()`

2. `core/auth/reauth/playwright_client.py`:
   - Улучшена обработка исключений при закрытии ресурсов Playwright
   - Добавлена защита от ошибок при cleanup

## Рекомендации

1. **Не используйте daemon threads для операций, требующих правильного завершения**
   - Playwright, браузеры, работа с памятью требуют корректного cleanup
   - Daemon threads могут быть убиты в любой момент

2. **Всегда используйте context managers для ресурсов**
   - Playwright использует `async with`, что гарантирует правильное закрытие

3. **Добавляйте обработку исключений в finally блоках**
   - Даже при ошибках ресурсы должны освобождаться

4. **Отслеживайте долгоживущие потоки**
   - При остановке приложения ждите их завершения

## Тестирование

После исправления процесс должен:
- ✅ Корректно обрабатывать ре-аутентификацию
- ✅ Правильно закрывать ресурсы Playwright
- ✅ Не падать с ошибками памяти
- ✅ Корректно завершаться при остановке

## Мониторинг

Следите за логами:
- `Started re-authentication thread for channel {channel_name}`
- `Completed re-authentication process for channel {channel_name}`
- `Playwright shutdown completed for channel {channel_name}`

Если видите предупреждения о ошибках при cleanup, это может указывать на проблемы с ресурсами.

