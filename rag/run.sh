#!/usr/bin/env bash
# run.sh — основной интерфейс проекта (не требует make).
# Запуск: ./run.sh <команда>
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE="${COMPOSE:-podman-compose}"
ENV_FILE=".env"

EMBED_MODEL="nomic-embed-text"
LLM_MODEL="qwen2.5:1.5b"

usage() {
  cat <<'EOF'
RAG helper

  ./run.sh up            Поднять Qdrant и Ollama
  ./run.sh down          Остановить контейнеры (данные сохраняются)
  ./run.sh ps            Статус контейнеров
  ./run.sh logs [svc]    Логи (можно указать сервис: qdrant | ollama)
  ./run.sh models        Скачать модели (embeddings + LLM)
  ./run.sh models-list   Показать скачанные модели
  ./run.sh health        Проверить Qdrant и Ollama
  ./run.sh ingest [args] Собрать образ и разово запустить crawl в контейнере
                         (args: --limit N --concurrency N --out DIR --force ...)
  ./run.sh ingest-local [args]
                         Запустить crawl в локальном venv (ingest/.venv)
  ./run.sh help          Эта справка
EOF
}

ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    cp .env.example "$ENV_FILE"
    echo ".env создан из .env.example"
  fi
}

check_up() {
  if ! podman container exists rag-ollama 2>/dev/null; then
    echo "Контейнеры не подняты. Сначала: ./run.sh up" >&2
    exit 1
  fi
}

case "${1:-help}" in
  up)
    ensure_env
    "$COMPOSE" up -d
    ;;
  down)
    "$COMPOSE" down
    ;;
  ps)
    "$COMPOSE" ps
    ;;
  logs)
    shift
    "$COMPOSE" logs -f "$@"
    ;;
  models)
    check_up
    podman exec rag-ollama ollama pull "$EMBED_MODEL"
    podman exec rag-ollama ollama pull "$LLM_MODEL"
    ;;
  models-list)
    check_up
    podman exec rag-ollama ollama list
    ;;
  health)
    echo -n "qdrant: "
    curl -s -m 10 http://localhost:6333/healthz || { echo "недоступен"; exit 1; }
    echo
    echo -n "ollama: "
    curl -s -m 10 http://localhost:11434/api/version || { echo "недоступен"; exit 1; }
    echo
    ;;
  ingest)
    ensure_env
    shift
    # профиль "tools" включаем явно (podman-compose 1.6: --profile до subcommand)
    "$COMPOSE" --profile tools build ingest
    "$COMPOSE" --profile tools run --rm ingest python -m ingest crawl "$@"
    ;;
  ingest-local)
    shift
    if [[ ! -x ingest/.venv/bin/python ]]; then
      echo "Нет ingest/.venv. Создайте окружение:" >&2
      echo "  cd ingest && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
      exit 1
    fi
    ingest/.venv/bin/python -m ingest crawl "$@"
    ;;
  help|*)
    usage
    ;;
esac
