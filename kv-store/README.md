# kv-store

An educational Go project: a simple in-memory key-value store with a text protocol over TCP.

## What's implemented

- **TCP server** (`server/`) — worker pool, connection queue, registered commands, graceful shutdown on signals, request size limit and read timeout.
- **Client** (`cmd/kv-client/`) — interactive CLI: reads commands from stdin, sends them to the server, and prints the response.
- **Storage** (`storage/`) — three backends behind a common `Storage` interface (`Get` / `Set` / `WaitForStop`):
  - `single-threaded` — all operations are funneled through a channel to a single worker goroutine (no locks);
  - `rw-mutex` — `map` + `sync.RWMutex`;
  - `sharded-mutex` — sharding by FNV hash of the key across N mutexes.
- Tests for the server and each storage backend.

## Protocol commands

```
get <key>      # get a value
set <key> <value>   # set a value
```

## Running

```bash
go run ./cmd/kv-store -addr 0.0.0.0:9000 -backend single-threaded
go run ./cmd/kv-client -addr localhost:9000
```

`-backend` — one of: `single-threaded` (default), `rw-mutex`, `sharded-mutex`.

## Tests

```bash
go test ./...
```
