# 🖱️ Последовательность нажатий кнопок при автоматической авторизации

> Детальное описание всех кнопок и их порядка нажатия в процессе OAuth авторизации

**Версия:** 2.0.0  
**Дата:** 2025-01-XX

---

## 📋 Содержание

1. [Общая последовательность](#общая-последовательность)
2. [Детальное описание каждого этапа](#детальное-описание-каждого-этапа)
3. [Селекторы и методы поиска кнопок](#селекторы-и-методы-поиска-кнопок)
4. [Обработка различных сценариев](#обработка-различных-сценариев)

---

## 🔄 Общая последовательность

### Полный поток нажатий:

```
1. Account Chooser (если показывается)
   └─> [Выбор аккаунта] или [Use another account]

2. Email ввод
   └─> [Next] (#identifierNext)

3. Password ввод
   └─> [Next] (#passwordNext) или [Enter]

4. Account Recovery Prompt (если показывается)
   └─> [Skip] / [Пропустить] / [Пропустити]

5. MFA Challenge (если требуется)
   └─> [More ways to verify] (опционально)
   └─> [Ввод кода вручную] (если нет TOTP)

6. Unverified App Screen (если показывается)
   └─> [Continue] (jsname="V67aGc")

7. Consent Screen
   └─> [Select All] (jsname="YPqjbf") - чекбокс
   └─> [Continue] / [Allow] (jsname="V67aGc")

8. No Access Dialog (если появляется)
   └─> [Cancel] / [Go back]
   └─> Поиск и клик [Continue] (jsname="V67aGc")
```

---

## 📝 Детальное описание каждого этапа

### 1. Account Chooser (Выбор аккаунта)

**Когда показывается:**
- Если в браузере сохранено несколько аккаунтов Google
- При первом входе с нового устройства

**Кнопки:**

#### 1.1. Выбор аккаунта из списка
```python
# Селектор: div[data-identifier]
# Действие: Клик по тайлу с нужным email
account_tiles = page.locator("div[data-identifier]")
# Поиск по email или channel_name
await tile.click()
```

**Логика:**
- Ищет тайлы с `data-identifier`, содержащим email
- Сравнивает с `credential.login_email` и `credential.channel_name`
- Кликает по найденному тайлу

#### 1.2. "Use another account" (если нужный аккаунт не найден)
```python
# Селектор: div[jsname='ksKsZd']
# Текст: "Use another account" / "Використати інший обліковий запис"
chooser_link = page.locator("div[jsname='ksKsZd']").first
await chooser_link.click()
```

**Fallback:**
- Если не найден нужный аккаунт, кликает первый тайл
- Или кликает "Use another account" для ввода email вручную

**Файл:** `core/auth/reauth/playwright_client.py:388-430`

---

### 2. Email ввод

**Когда показывается:**
- После выбора аккаунта или клика "Use another account"
- Если аккаунт не найден в списке

**Действия:**

#### 2.1. Заполнение email поля
```python
# Селектор: input[type="email"]:visible
email_field = page.locator('input[type="email"]:visible')
await email_field.first.fill(credential.login_email)
```

#### 2.2. Нажатие кнопки Next
```python
# Селектор: #identifierNext button:visible
# Текст: "Next" / "Далее" / "Далі"
identifier_button = page.locator("#identifierNext button:visible")
await identifier_button.first.click()
```

**Задержки:**
- После заполнения email: `_human_pause()` (200-400ms)
- После клика: `wait_for_timeout(1500ms)`

**Файл:** `core/auth/reauth/playwright_client.py:2340-2358`

---

### 3. Password ввод

**Когда показывается:**
- После успешного ввода email и нажатия Next

**Действия:**

#### 3.1. Заполнение password поля
```python
# Селектор: input[type="password"]:visible
password_field = page.locator('input[type="password"]:visible')
await password_field.first.fill(credential.login_password)
```

#### 3.2. Нажатие кнопки Next или Enter
```python
# Метод 1: Кнопка Next
# Селектор: #passwordNext button:visible
password_next = page.locator("#passwordNext button:visible")
if await password_next.count():
    await password_next.first.click()
else:
    # Метод 2: Нажатие Enter
    await page.keyboard.press("Enter")
```

**Задержки:**
- После заполнения: `_human_pause()` (200-400ms)
- После клика: ожидание `networkidle` или `wait_for_timeout(2000ms)`

**Файл:** `core/auth/reauth/playwright_client.py:2361-2389`

---

### 4. Account Recovery Prompt (Пропуск recovery информации)

**Когда показывается:**
- Google может предложить добавить recovery email/phone
- Не критично для авторизации, можно пропустить

**Кнопки:**

```python
# Тексты кнопок (в порядке приоритета):
labels = ("Пропустити", "Пропустить", "Skip", "Продовжити", "Continue")

# Поиск и клик
for label in labels:
    locator = page.locator(f"text='{label}'").first
    if await locator.count():
        await locator.click()
        return

# Fallback: поиск по button с текстом "Skip"
skip_locator = page.locator("button", has_text="Skip").first
if await skip_locator.count():
    await skip_locator.click()
```

**Задержки:**
- После клика: `wait_for_timeout(human_delay_range_ms[0])` (200-400ms)

**Файл:** `core/auth/reauth/playwright_client.py:505-532`

---

### 5. MFA Challenge (Двухфакторная аутентификация)

**Когда показывается:**
- Если включена двухфакторная аутентификация
- После ввода пароля

**Действия:**

#### 5.1. Опционально: "More ways to verify"
```python
# Тексты ссылок:
more_links = (
    page.locator("text='More ways to verify'"),
    page.locator("text='Інші способи підтвердження'"),
    page.locator("text='Другие способы подтверждения'"),
)

# Клик по первой найденной
for locator in more_links:
    if await locator.count():
        await locator.first.click()
        return
```

#### 5.2. Ввод MFA кода
**Текущая реализация:**
- Если настроен `totp_secret` - планируется автоматическая генерация (в разработке)
- Если нет - ожидается ручной ввод с уведомлением

**Селекторы полей ввода:**
```python
mfa_selectors = [
    ("input[name='idvPin']", "Google запрашивает код подтверждения"),
    ("input[name='totpPin']", "Google запрашивает TOTP код"),
    ("input[type='tel']", "Google запрашивает код подтверждения на телефон"),
]
```

**Файл:** `core/auth/reauth/playwright_client.py:433-502`

---

### 6. Unverified App Screen ("Google hasn't verified this app")

**Когда показывается:**
- Если OAuth приложение не прошло верификацию Google
- При первом использовании нового Client ID

**Кнопка:**

```python
# Селектор: div[jsname='V67aGc']
# Текст: "Continue" / "Продолжить" / "Продовжити"

# Метод 1: Прямой поиск по селектору
button = page.locator("div[jsname='V67aGc']").first
await button.scroll_into_view_if_needed()
await _human_like_click(button, page, browser_config)

# Метод 2: Поиск по тексту с проверкой jsname
# Ищет элементы с текстом "Continue" и проверяет jsname родителя

# Метод 3: JavaScript клик
await page.evaluate("""
  const button = document.querySelector('div[jsname="V67aGc"]');
  if (button) {
    button.scrollIntoView();
    button.click();
  }
""")
```

**Задержки:**
- Перед поиском: `wait_for_timeout(500-1000ms)`
- После клика: `wait_for_timeout(1000-1500ms)`

**Файл:** `core/auth/reauth/playwright_client.py:1688-1842`

---

### 7. Consent Screen (Экран разрешений)

**Когда показывается:**
- После успешного входа
- Перед получением authorization code

**Действия:**

#### 7.1. Выбор всех scope (чекбокс "Select All")

**Метод 1: Чекбокс с jsname="YPqjbf"**
```python
# Селектор: div[jsname='YPqjbf'] input[type='checkbox']
select_all_checkbox = surface.locator("div[jsname='YPqjbf'] input[type='checkbox']")
if not await select_all_checkbox.first.is_checked():
    await select_all_checkbox.first.click()
```

**Метод 2: Поиск по тексту "Select all"**
```python
# Тексты: "Select all" / "Выбрать все" / "Вибрати все"
locator = surface.locator("text='Select all'").first
if await locator.count():
    await locator.first.click()
```

**Метод 3: Клик по всем неотмеченным чекбоксам**
```python
# Клик по каждому unchecked checkbox (кроме Select All)
checkboxes = surface.locator("input[type='checkbox']:not(:checked)")
for checkbox in checkboxes:
    await checkbox.click()
```

**Задержки:**
- Между кликами чекбоксов: `random.uniform(0.1, 0.3)` секунды

**Файл:** `core/auth/reauth/playwright_client.py:886-1009`

#### 7.2. Нажатие кнопки Continue/Allow

**Метод 1: Прямой поиск по jsname="V67aGc"**
```python
# Селектор: div[jsname='V67aGc']
await surface.wait_for_selector("div[jsname='V67aGc']", state="visible", timeout=15000)
button = surface.locator("div[jsname='V67aGc']").first
await button.scroll_into_view_if_needed()
await _human_like_click(button, page_obj, browser_config)
```

**Метод 2: Поиск по тексту с проверкой jsname**
```python
# Ищет элементы с текстом "Continue" / "Allow" / "Продолжить" / "Разрешить"
# Проверяет, что родитель имеет jsname="V67aGc"
button_info = await surface.evaluate("""
  // Находит элемент с текстом "continue"
  // Проверяет jsname родителя
""")
```

**Метод 3: Поиск в Shadow DOM**
```python
# Рекурсивный поиск в Shadow DOM
shadow_result = await surface.evaluate("""
  function findInShadow(root) {
    // Поиск [jsname="V67aGc"] в Shadow DOM
  }
""")
```

**Метод 4: Поиск всех кликабельных элементов**
```python
# Ищет все button, div[role="button"], a, [onclick], [tabindex]
# Проверяет jsname="V67aGc"
all_buttons = await surface.evaluate("""
  const selectors = ['button', 'div[role="button"]', 'a', '[onclick]', '[tabindex]'];
  // Проверяет jsname="V67aGc"
""")
```

**Поддерживаемые тексты:**
- Английский: "Continue", "Allow"
- Русский: "Продолжить", "Разрешить"
- Украинский: "Продовжити", "Дозволити"

**Задержки перед кликом:**
1. Ожидание загрузки: `wait_for_load_state("networkidle")` (до 15 сек)
2. Начальная пауза: `random.uniform(0.5, 1.0)` секунды
3. Прокрутка вниз: `_scroll_to_bottom()` (симуляция чтения)
4. Пауза после прокрутки: `random.uniform(0.3, 0.6)` секунды
5. Симуляция активности: `_simulate_human_activity()` (движения мыши)
6. Финальная пауза: `random.uniform(0.3, 0.6)` секунды
7. Прокрутка к кнопке: `scroll_into_view_if_needed()`
8. Пауза после прокрутки: `random.uniform(0.3, 0.5)` секунды

**Файл:** `core/auth/reauth/playwright_client.py:1036-1405`

---

### 8. No Access Dialog ("You did not allow any access")

**Когда показывается:**
- Если после клика Continue не были выбраны scope
- Редкий случай, когда чекбоксы не были отмечены

**Действия:**

#### 8.1. Обнаружение диалога
```python
# Тексты для обнаружения:
no_access_texts = [
    "You did not allow any access",
    "did not allow any access",
    "Do you want to continue without allowing",
]
```

#### 8.2. Нажатие Cancel/Go back
```python
# Кнопки для клика:
cancel_buttons = [
    surface.locator("button:has-text('Go back')"),
    surface.locator("button:has-text('Cancel')"),
    surface.locator("text='Go back'"),
    surface.locator("text='Cancel'"),
]

for cancel_btn in cancel_buttons:
    if await cancel_btn.count() > 0:
        await cancel_btn.click(timeout=5000)
        return
```

#### 8.3. Повторная попытка
После клика Cancel/Go back:
1. Просто ищется и нажимается кнопка Continue с `jsname="V67aGc"`
2. Без повторного выбора scope (они уже должны быть выбраны)

```python
# После клика Go back просто ищем Continue кнопку
button = surface.locator("div[jsname='V67aGc']").first
if await button.count() > 0:
    await button.scroll_into_view_if_needed()
    await _human_like_click(button, page_obj, browser_config)
    # или
    await button.click(timeout=5000, delay=random.randint(50, 100))
```

**Файл:** `core/auth/reauth/playwright_client.py:747-835`

---

## 🔍 Селекторы и методы поиска кнопок

### Основные селекторы:

| Кнопка | Селектор | jsname | Тексты |
|--------|----------|--------|--------|
| Account Chooser | `div[data-identifier]` | - | Email аккаунта |
| Use another account | `div[jsname='ksKsZd']` | `ksKsZd` | "Use another account" |
| Email Next | `#identifierNext button` | - | "Next" / "Далее" |
| Password Next | `#passwordNext button` | - | "Next" / "Далее" |
| Skip Recovery | `text='Skip'` | - | "Skip" / "Пропустить" |
| Select All | `div[jsname='YPqjbf'] input` | `YPqjbf` | "Select all" |
| Continue/Allow | `div[jsname='V67aGc']` | `V67aGc` | "Continue" / "Allow" |
| Cancel/Go back | `button:has-text('Go back')` | - | "Go back" / "Cancel" |

### Методы поиска кнопок:

#### 1. Прямой селектор (наиболее надежный)
```python
button = page.locator("div[jsname='V67aGc']").first
await button.click()
```

#### 2. Поиск по тексту
```python
button = page.locator("text='Continue'").first
await button.click()
```

#### 3. Поиск с проверкой атрибутов
```python
# Ищет элемент с текстом и проверяет jsname родителя
button_info = await page.evaluate("""
  // Находит элемент с текстом
  // Проверяет jsname родителя
""")
```

#### 4. JavaScript клик
```python
await page.evaluate("""
  const button = document.querySelector('div[jsname="V67aGc"]');
  button.click();
""")
```

#### 5. Human-like клик (симуляция человека)
```python
await _human_like_click(button, page, browser_config)
# Включает:
# - Движение мыши к кнопке
# - Небольшую задержку
# - Клик с задержкой
```

---

## 🎯 Обработка различных сценариев

### Сценарий 1: Первый вход (новый аккаунт)

```
1. Account Chooser → [Use another account]
2. Email ввод → [Next]
3. Password ввод → [Next]
4. Account Recovery → [Skip]
5. Consent Screen → [Select All] → [Continue]
```

### Сценарий 2: Аккаунт уже сохранен

```
1. Account Chooser → [Выбор аккаунта из списка]
2. Password ввод → [Next]
3. Consent Screen → [Select All] → [Continue]
```

### Сценарий 3: С MFA

```
1. Account Chooser → [Выбор аккаунта]
2. Email ввод → [Next]
3. Password ввод → [Next]
4. MFA Challenge → [Ввод кода вручную]
5. Consent Screen → [Select All] → [Continue]
```

### Сценарий 4: Неверифицированное приложение

```
1. Account Chooser → [Выбор аккаунта]
2. Email ввод → [Next]
3. Password ввод → [Next]
4. Unverified App Screen → [Continue] (V67aGc)
5. Consent Screen → [Select All] → [Continue]
```

### Сценарий 5: Ошибка "No access"

```
1. Consent Screen → [Select All] → [Continue]
2. No Access Dialog → [Go back]
3. Consent Screen → [Continue] (jsname="V67aGc") - без повторного выбора scope
```

---

## ⏱️ Временные задержки

### Задержки между действиями:

| Действие | Задержка | Причина |
|----------|----------|---------|
| После заполнения email | 200-400ms | Симуляция человека |
| После клика Next (email) | 1500ms | Ожидание загрузки |
| После заполнения password | 200-400ms | Симуляция человека |
| После клика Next (password) | До networkidle или 2000ms | Ожидание загрузки |
| После клика Skip | 200-400ms | Симуляция человека |
| Перед выбором scope | 0.5-1.0 сек | Ожидание загрузки |
| Между кликами чекбоксов | 100-300ms | Симуляция человека |
| Перед кликом Continue | 0.3-0.6 сек | Симуляция чтения |
| После прокрутки | 0.3-0.6 сек | Симуляция человека |
| После клика Continue | 1000-1500ms | Ожидание редиректа |

### Human-like активности:

```python
async def _simulate_human_activity(page, browser_config):
    # Случайные движения мыши
    # Случайные паузы
    # Прокрутка страницы
    # Небольшие задержки
```

---

## 🔄 Retry логика

### Повторные попытки:

1. **No Access Dialog:**
   - При обнаружении диалога → клик Cancel/Go back
   - После Go back → просто поиск и клик Continue (jsname="V67aGc") без повторного выбора scope

2. **Неудачный клик кнопки:**
   - Метод 1 (селектор) → Метод 2 (текст) → Метод 3 (Shadow DOM) → Метод 4 (все элементы)

3. **Login Flow:**
   - Максимум 5 попыток в цикле `_complete_login_flow()`
   - Каждая попытка обрабатывает один этап

---

## 📊 Логирование

Все клики логируются с уровнем INFO:

```python
LOGGER.info("🖱️  Clicking 'Next' button after email for %s", channel_name)
LOGGER.info("✅ Successfully clicked Continue button for %s", channel_name)
LOGGER.warning("⚠️  Could not find Continue button for %s", channel_name)
```

**Формат логов:**
- 🖱️ - Клик кнопки
- ✅ - Успешное действие
- ⚠️ - Предупреждение
- 🔍 - Поиск элемента

---

## 🛠️ Отладка

### Полезные команды для отладки:

```python
# Скриншот перед кликом
await page.screenshot(path="before_click.png")

# Логирование состояния страницы
await _log_page_state(page, "before clicking button", credential)

# Проверка видимости элемента
is_visible = await button.is_visible()

# Получение текста элемента
text = await button.inner_text()

# Проверка атрибутов
jsname = await button.get_attribute("jsname")
```

---

## 📚 Связанные файлы

- `core/auth/reauth/playwright_client.py` - Основная логика автоматизации
- `core/auth/reauth/oauth_flow.py` - OAuth flow
- `core/auth/reauth/service.py` - Оркестрация процесса
- `app/task_worker.py` - Запуск переавторизации

---

**Версия документации:** 2.0.0  
**Последнее обновление:** 2025-01-XX  
**Автор:** Content Fabric Team

