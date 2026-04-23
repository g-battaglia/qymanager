#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# dev.sh — Unified dev manager for QYConv web GUI
#
# Manages Backend (FastAPI/uvicorn) and Frontend (Vite/React) as background
# processes with PID tracking and log capture.
#
# Compatible with macOS bash 3.2+ (no associative arrays, no wait -n).
#
# Usage:
#   ./web/dev.sh start [service...]    Start all or specific services
#   ./web/dev.sh stop  [service...]    Stop all or specific services
#   ./web/dev.sh restart [service...]  Restart all or specific services
#   ./web/dev.sh status                Show status of all services
#   ./web/dev.sh logs  [service]       Tail logs (all or specific service)
#   ./web/dev.sh help                  Show this help
#
# Services: backend, frontend
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

if [ -z "${BASH_VERSION:-}" ]; then
  echo "Error: this script requires bash."
  echo "  Run it as:  bash web/dev.sh"
  exit 1
fi

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ── Project paths ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

PIDDIR="$SCRIPT_DIR/.dev/pids"
LOGDIR="$SCRIPT_DIR/.dev/logs"

# ── Service metadata (bash 3.2-compatible, no associative arrays) ────────────
svc_port() {
  case "$1" in
    backend)  echo 8000 ;;
    frontend) echo 5173 ;;
  esac
}

svc_label() {
  case "$1" in
    backend)  echo "Backend (FastAPI)" ;;
    frontend) echo "Frontend (Vite/React)" ;;
  esac
}

svc_color() {
  case "$1" in
    backend)  echo "$GREEN" ;;
    frontend) echo "$YELLOW" ;;
  esac
}

ALL_SERVICES="backend frontend"

# ── Logging ──────────────────────────────────────────────────────────────────
timestamp() { date '+%H:%M:%S'; }
log_info()  { printf "${DIM}%s${RESET} ${BLUE}[INFO]${RESET}  %s\n" "$(timestamp)" "$1"; }
log_ok()    { printf "${DIM}%s${RESET} ${GREEN}[ OK ]${RESET}  %s\n" "$(timestamp)" "$1"; }
log_warn()  { printf "${DIM}%s${RESET} ${YELLOW}[WARN]${RESET}  %s\n" "$(timestamp)" "$1"; }
log_error() { printf "${DIM}%s${RESET} ${RED}[ERR!]${RESET}  %s\n" "$(timestamp)" "$1"; }

# ── Helpers ──────────────────────────────────────────────────────────────────

ensure_dirs() {
  mkdir -p "$PIDDIR" "$LOGDIR"
}

is_running() {
  local svc="$1"
  local pidfile="$PIDDIR/$svc.pid"
  if [ -f "$pidfile" ]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    rm -f "$pidfile"
  fi
  return 1
}

get_pid() {
  local pidfile="$PIDDIR/$1.pid"
  [ -f "$pidfile" ] && cat "$pidfile"
}

kill_tree() {
  local pid="$1" sig="${2:-TERM}"
  local children
  children=$(pgrep -P "$pid" 2>/dev/null || true)
  for child in $children; do
    kill_tree "$child" "$sig"
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -"$sig" "$pid" 2>/dev/null || true
  fi
}

is_valid_service() {
  case "$1" in
    backend|frontend) return 0 ;;
    *) return 1 ;;
  esac
}

validate_services() {
  for svc in "$@"; do
    if ! is_valid_service "$svc"; then
      log_error "Unknown service: $svc"
      log_info "Valid services: backend, frontend"
      exit 1
    fi
  done
}

# ── Prerequisites ────────────────────────────────────────────────────────────

check_prereqs() {
  case "$1" in
    backend)
      if ! command -v uv &>/dev/null; then
        log_error "uv not found in PATH"
        log_info "  Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
        return 1
      fi
      if [ ! -f "$REPO_ROOT/pyproject.toml" ]; then
        log_error "pyproject.toml not found at $REPO_ROOT"
        return 1
      fi
      ;;
    frontend)
      if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        log_error "Frontend node_modules not found"
        log_info "  Install: cd web/frontend && npm install"
        return 1
      fi
      ;;
  esac
}

# ── Start ────────────────────────────────────────────────────────────────────

start_service() {
  local svc="$1"
  local label port logfile

  label=$(svc_label "$svc")
  port=$(svc_port "$svc")

  if is_running "$svc"; then
    local pid
    pid=$(get_pid "$svc")
    log_warn "$label is already running (PID $pid)"
    return 0
  fi

  if ! check_prereqs "$svc"; then
    return 1
  fi

  logfile="$LOGDIR/$svc.log"
  : > "$logfile"

  case "$svc" in
    backend)
      (
        cd "$REPO_ROOT"
        export UV_LINK_MODE=copy
        exec uv run qymanager serve --reload --port "$port" 2>&1
      ) >> "$logfile" 2>&1 &
      ;;
    frontend)
      (
        cd "$FRONTEND_DIR"
        exec npm run dev -- --host 127.0.0.1 --port "$port" 2>&1
      ) >> "$logfile" 2>&1 &
      ;;
  esac

  local pid=$!

  sleep 0.5
  if kill -0 "$pid" 2>/dev/null; then
    echo "$pid" > "$PIDDIR/$svc.pid"
    log_ok "$label started (PID $pid) on port $port"
  else
    log_error "$label failed to start — check $logfile"
    wait "$pid" 2>/dev/null || true
    return 1
  fi
}

# ── Stop ─────────────────────────────────────────────────────────────────────

stop_service() {
  local svc="$1"
  local label
  label=$(svc_label "$svc")

  if ! is_running "$svc"; then
    log_info "$label is not running"
    return 0
  fi

  local pid
  pid=$(get_pid "$svc")
  log_info "Stopping $label (PID $pid) ..."

  kill_tree "$pid" TERM

  local waited=0
  while kill -0 "$pid" 2>/dev/null && [ $waited -lt 50 ]; do
    sleep 0.1
    waited=$((waited + 1))
  done

  if kill -0 "$pid" 2>/dev/null; then
    log_warn "Force-killing $label (PID $pid)"
    kill_tree "$pid" 9
    sleep 0.5
  fi

  wait "$pid" 2>/dev/null || true
  rm -f "$PIDDIR/$svc.pid"
  log_ok "$label stopped"
}

# ── Commands ─────────────────────────────────────────────────────────────────

cmd_start() {
  local services="$*"
  if [ -z "$services" ]; then
    services="$ALL_SERVICES"
  fi

  ensure_dirs

  local errors=0
  for svc in $services; do
    if ! start_service "$svc"; then
      errors=$((errors + 1))
    fi
  done

  echo ""
  printf "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  printf "${BOLD}  QYConv — Development Server${RESET}\n"
  printf "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  for svc in $services; do
    if is_running "$svc"; then
      local pid port color label
      pid=$(get_pid "$svc")
      port=$(svc_port "$svc")
      color=$(svc_color "$svc")
      label=$(svc_label "$svc")
      printf "  ${color}%-28s${RESET} http://localhost:%-5s ${DIM}PID %s${RESET}\n" "$label" "$port" "$pid"
    fi
  done
  echo ""
  printf "  ${DIM}Logs: ./web/dev.sh logs [service]${RESET}\n"
  printf "  ${DIM}Stop: ./web/dev.sh stop${RESET}\n"
  printf "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
  echo ""

  if [ $errors -gt 0 ]; then
    log_error "$errors service(s) failed to start"
    return 1
  fi
}

cmd_stop() {
  local services="$*"
  if [ -z "$services" ]; then
    services="$ALL_SERVICES"
  fi

  for svc in $services; do
    stop_service "$svc"
  done
}

cmd_restart() {
  local services="$*"
  if [ -z "$services" ]; then
    services="$ALL_SERVICES"
  fi

  for svc in $services; do
    stop_service "$svc"
  done
  for svc in $services; do
    start_service "$svc"
  done
}

cmd_status() {
  ensure_dirs

  echo ""
  printf "${BOLD}  Service Status${RESET}\n"
  printf "  %-30s %-8s %-8s %s\n" "SERVICE" "PORT" "PID" "STATUS"
  printf "  %s\n" "──────────────────────────────────────────────────────────"

  for svc in $ALL_SERVICES; do
    local port label
    port=$(svc_port "$svc")
    label=$(svc_label "$svc")
    if is_running "$svc"; then
      local pid
      pid=$(get_pid "$svc")
      printf "  %-30s %-8s %-8s ${GREEN}running${RESET}\n" "$label" "$port" "$pid"
    else
      printf "  %-30s %-8s %-8s ${DIM}stopped${RESET}\n" "$label" "$port" "-"
    fi
  done
  echo ""
}

colorize_logs() {
  awk '
    BEGIN {
      red    = "\033[0;31m"
      yellow = "\033[0;33m"
      green  = "\033[0;32m"
      blue   = "\033[0;34m"
      dim    = "\033[2m"
      reset  = "\033[0m"
    }
    /ERROR|CRITICAL|FATAL|Traceback|Exception/ { print red $0 reset; fflush(); next }
    /raise [A-Z]/                              { print red $0 reset; fflush(); next }
    / 5[0-9][0-9] /                            { print red $0 reset; fflush(); next }
    /WARNING|WARN/                             { print yellow $0 reset; fflush(); next }
    / 4[0-9][0-9] /                            { print yellow $0 reset; fflush(); next }
    /INFO/                                     { print blue $0 reset; fflush(); next }
    / 2[0-9][0-9] /                            { print green $0 reset; fflush(); next }
    /DEBUG/                                    { print dim $0 reset; fflush(); next }
    { print; fflush() }
  '
}

cmd_logs() {
  ensure_dirs

  if [ $# -eq 0 ]; then
    local logfiles=""
    for svc in $ALL_SERVICES; do
      local logfile="$LOGDIR/$svc.log"
      if [ -f "$logfile" ]; then
        logfiles="$logfiles $logfile"
      fi
    done
    if [ -z "$logfiles" ]; then
      log_info "No log files found. Start services first."
      return 0
    fi
    # shellcheck disable=SC2086
    tail -f $logfiles | colorize_logs
  else
    local svc="$1"
    local logfile="$LOGDIR/$svc.log"
    if [ ! -f "$logfile" ]; then
      log_error "No log file for '$svc'"
      return 1
    fi
    tail -f "$logfile" | colorize_logs
  fi
}

cmd_help() {
  cat <<'HELP'
QYConv Web GUI — Development Manager

Usage:
  bash web/dev.sh <command> [args...]

Commands:
  start   [service...]    Start all services, or specific ones
  stop    [service...]    Stop all services, or specific ones
  restart [service...]    Restart all or specific services
  status                  Show status of all services
  logs    [service]       Tail log output (all or specific service)
  help                    Show this help

Services:
  backend   FastAPI/uvicorn on port 8000 (with --reload)
  frontend  Vite/React dev server on port 5173 (proxy /api → :8000)

Notes:
  - By default, start/stop/restart operate on both backend and frontend.
  - PID files and logs live in web/.dev/ (git-ignored).
  - Backend requires: uv (https://astral.sh/uv), pyproject.toml web extras.
  - Frontend requires: node_modules (run: cd web/frontend && npm install).

Examples:
  bash web/dev.sh start                    # Start both services
  bash web/dev.sh start backend            # Start only backend
  bash web/dev.sh stop frontend            # Stop only frontend
  bash web/dev.sh restart backend          # Restart backend
  bash web/dev.sh logs backend             # Tail backend logs
  bash web/dev.sh logs                     # Tail all logs
  bash web/dev.sh status                   # Check what's running
HELP
}

# ── Main ─────────────────────────────────────────────────────────────────────

if [ $# -eq 0 ]; then
  cmd_help
  exit 0
fi

COMMAND="$1"
shift

case "$COMMAND" in
  start)
    [ $# -gt 0 ] && validate_services "$@"
    cmd_start "$@"
    ;;
  stop)
    [ $# -gt 0 ] && validate_services "$@"
    cmd_stop "$@"
    ;;
  restart)
    [ $# -gt 0 ] && validate_services "$@"
    cmd_restart "$@"
    ;;
  status)
    cmd_status
    ;;
  logs)
    [ $# -gt 0 ] && validate_services "$1"
    cmd_logs "$@"
    ;;
  help|--help|-h)
    cmd_help
    ;;
  *)
    log_error "Unknown command: $COMMAND"
    echo "Run 'bash web/dev.sh help' for usage"
    exit 1
    ;;
esac
