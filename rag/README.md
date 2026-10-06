# RAG-бот по документации

Учебный проект: RAG-пайплайн «по шагам» — от скачивания документации до чат-бота
с цитированием источников. Всё поднимается локально в Podman через `podman-compose`.

Корпус для индексации — [документация FastAPI](https://fastapi.tiangolo.com).
Векторная БД — Qdrant, эмбеддинги и LLM — локально через Ollama, UI — Chainlit.

## Архитектура

```
[ingest]  crawl docs → parse → chunk → embed ──┐
   one-shot job                                ▼
                                          [(Qdrant)]  ← dashboard :6333
[app: Chainlit UI + retrieval + LLM] ────►   ▲
                                            [ollama]  LLM + embeddings :11434
```

## Стек

| Слой | Выбор | Почему (кратко) |
|------|-------|-----------------|
| Векторная БД | Qdrant | 1 контейнер, web-UI, фильтры, hybrid search |
| LLM + эмбеддинги | Ollama (`qwen2.5:1.5b`, `nomic-embed-text`) | локально, self-contained, старт с лёгкой модели |
| UI | Chainlit | чат из коробки: стриминг, источники, шаги |
| Оркестрация | podman-compose (через pipx) | всё в одном compose-файле |

Подробнее: [doc/01-tools.md](doc/01-tools.md).

## Быстрый старт

```bash
./run.sh up            # поднять Qdrant + Ollama
./run.sh models        # скачать модели (первый раз ~1.2 ГБ)
./run.sh health        # проверка
./run.sh ingest        # собрать корпус документации в data/raw
```

Дашборд Qdrant: <http://localhost:6333/dashboard>

> Интерфейс — `./run.sh` (не требует `make`). Список команд: `./run.sh help`.

## План и прогресс

Текущий шаг: **Фаза 2 — чанкинг корпуса** (фазы 0–1 завершены).

- [x] **0. Bootstrap** — compose-провайдер, каркас, Qdrant + Ollama, README/doc
- [x] **1. Corpus** — обход FastAPI docs, HTML→Markdown, метаданные (138 страниц)
- [ ] **2. Chunking** — нарезка на чанки с overlap
- [ ] **3. Embeddings + Qdrant** — векторизация и загрузка в БД
- [ ] **4. Retrieval + prompt** — поиск, сборка контекста, citation, CLI
- [ ] **5. UI** — чат на Chainlit со стримингом и источниками
- [ ] **6. RAG+** — hybrid search (BM25+dense), reranker, query rewriting
- [ ] **7. Evaluation** — eval-набор, hit-rate / faithfulness (ragas)
- [ ] **8. Packaging** — profiles, README, воспроизводимость
- [ ] **9. (опц.) iGPU** — Ollama на Radeon 880M, замер tok/s

## Документация

- [doc/INDEX.md](doc/INDEX.md) — содержание
- [doc/01-tools.md](doc/01-tools.md) — выбранные инструменты и аналоги
- [doc/02-corpus.md](doc/02-corpus.md) — сбор и парсинг корпуса

## Структура

```
rag/
  compose.yaml      # qdrant, ollama, ingest (profile tools)
  run.sh            # основной интерфейс (up / models / ingest / ...)
  .env.example
  ingest/           # сервис сбора корпуса (фаза 1)
  doc/              # документация по разделам
  data/             # сырые и обработанные данные (gitignored)
```
