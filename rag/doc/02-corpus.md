# 02. Сбор и парсинг корпуса

Фаза 1. Сервис `ingest` скачивает документацию FastAPI, превращает HTML в
Markdown и складывает страницы вместе с манифестом метаданных. Эмбеддингов и
Qdrant на этой фазе **нет** — только подготовка сырого корпуса.

## Цель фазы

Получить локальную копию доков в виде, удобном для будущей нарезки на чанки:

- чистый Markdown по одной странице на файл;
- метаданные (URL, раздел, заголовок, хэш) для фильтрации и дедупликации;
- детерминированный результат, пригодный для повторных запусков.

## Как работает

```
sitemap.xml → select (allowlist) → fetch (IPv4, retry) → parse → data/raw
```

| Шаг | Модуль | Что делает |
|-----|--------|------------|
| Sitemap | `sitemap.py` | тянет `sitemap.xml`, достаёт `<loc>`, нормализует URL |
| Отбор | `settings.py` / `sitemap.py` | оставляет только разделы из allowlist |
| Загрузка | `fetch.py` | `httpx` с форсом IPv4, 3 попытки, `Semaphore(concurrency)` |
| Парсинг | `parse.py` | берёт `<article>`, чистит обвязку, конвертит в Markdown |
| Запись | `crawl.py` | файлы страниц + `manifest.jsonl`, идемпотентно по хэшу |

### Sitemap и allowlist

Источник — `https://fastapi.tiangolo.com/sitemap.xml` (152 URL, только
английский). Отбираются разделы:

- префиксы: `/tutorial/`, `/advanced/`, `/reference/`, `/deployment/`, `/how-to/`;
- одиночные страницы: `/features/`, `/learn/`, `/python-types/`, `/async/`,
  `/fastapi-cli/`, `/editor-support/`, `/project-generation/`.

Из 152 URL в корпус попадает **138** страниц (отсеиваются переводы, корень и
служебные страницы). Список меняется через `INCLUDE_PREFIXES` (через запятую).

### Парсинг страницы

Контент лежит в `<article class="md-content__inner md-typeset">` (MkDocs
Material). Заголовок берётся из `<h1>`, при отсутствии — из `<title>` с
отрезанным суффиксом ` - FastAPI`. Перед конвертацией вырезается навигационная
обвязка: `script`, `style`, `nav`, `header`, `footer`, `a.headerlink`,
`.md-header-anchor`, `.md-source`, `.md-content__button`, блок
«Was this page helpful?»/`.md-feedback`. Если `<article>` нет — fallback на
`<main>`/`<body>`. Markdownify вызывается с ATX-заголовками (##) и языком кода
из класса `language-…`.

## Структура `data/raw`

```
data/raw/
  manifest.jsonl            # по строке JSON на страницу
  pages/<section>/<slug>.md # слаг = путь без слэшей, '/' → '_', корень → index
```

Пример: `/tutorial/first-steps/` → `data/raw/pages/tutorial/tutorial_first-steps.md`.

### Поля манифеста

| Поле | Пример | Смысл |
|------|--------|-------|
| `url` | `https://fastapi.tiangolo.com/tutorial/first-steps/` | нормализованный URL |
| `path` | `/tutorial/first-steps/` | путь без query/fragment |
| `section` | `tutorial` | первый сегмент пути (`general` для корня) |
| `title` | `First Steps` | заголовок страницы |
| `content_sha256` | `a1b2…` | SHA-256 Markdown, ключ идемпотентности |
| `char_count` | `12345` | длина Markdown в символах |
| `fetched_at` | `2026-10-05T19:14:47+00:00` | время загрузки (UTC ISO) |
| `file` | `raw/pages/tutorial/tutorial_first-steps.md` | путь относительно `DATA_DIR` |

При повторном запуске страница с тем же `content_sha256` не перезаписывается.
Флаг `--force` отключает проверку. При `--limit` (частичный прогон для отладки)
`manifest.jsonl` не перезаписывается, чтобы не потерять полный набор.

## Ограничения

- **Табы.** На страницах есть переключаемые табы (`div.tabbed-content`) —
  в корпусе они идут подряд, дублирование вариантов допустимо.
- **Без эмбеддингов.** Фаза намеренно не трогает Ollama и Qdrant.
- **IPv6.** На хосте нет IPv6, поэтому HTTP-клиент форсит IPv4 через
  `httpx.AsyncHTTPTransport(local_address="0.0.0.0")`.
- **SELinux.** Bind-mount `./data:/app/data:Z` обязателен, иначе rootless
  Podman не даёт контейнеру доступ к каталогу (Fedora, Enforcing).
- **Терминальный вывод.** Некоторые примеры сохраняют ANSI→HTML разметку
  (`<font>`, `<span>`) — это часть содержимого страницы.

## Запуск

Локально (нужен venv в `ingest/`):

```bash
cd ingest && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
cd .. && ./run.sh ingest-local            # полный crawl в data/raw
./run.sh ingest-local --limit 5 --force   # быстрая проверка
```

В контейнере (профиль `tools`, не поднимается с `./run.sh up`):

```bash
./run.sh ingest --limit 5   # собрать образ и разово запустить crawl
```

Прямой CLI:

```bash
python -m ingest crawl [--limit N] [--concurrency N] [--out DIR] [--base-url URL] [--force]
```

Лог печатает прогресс по страницам и итог: скачано / ошибок / записано /
пропущено / `.md` / размер манифеста. Если не скачалась ни одна страница —
код выхода `1`.

## Тесты

Без сети, на фикстурах `tests/fixtures/`:

```bash
cd ingest && .venv/bin/ruff check src tests && .venv/bin/pytest -q
```

Проверяются: разбор sitemap и фильтрация `/translations/`, нормализация URL,
`section`, заголовок, наличие ```` ```python ````, отсутствие мусора
(nav/headerlink/feedback), детерминированность SHA-256.
