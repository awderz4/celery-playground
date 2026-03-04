#!/usr/bin/env bash
# =============================================================================
# trace_redis.sh  —  Module 1: Trace a Task Through Redis
# =============================================================================
# Usage:
#   bash scripts/trace_redis.sh [command]
#
# Commands:
#   monitor   — Stream every Redis command in real-time (Ctrl-C to stop)
#   queue     — Show current queue depth and first message
#   results   — List all stored task result keys with TTLs
#   dbsize    — Compare DB 0 (broker) vs DB 1 (results) key counts
#   ttl <id>  — Show TTL and size of a specific task result
#   flush     — DANGER: clear all Celery keys (for lab resets)
#
# Requirements: docker compose up -d redis
#
# NOTE: Redis container is celery-playground-redis, mapped to host port 6380.
#       The default Celery queue key is 'default' (not 'celery').
#       Use 'docker exec' — redis-cli is not required on the host.
# =============================================================================

set -euo pipefail

CONTAINER="celery-playground-redis"
REDIS="docker exec -i ${CONTAINER} redis-cli"

# Verify container is running
if ! docker inspect -f '{{.State.Running}}' "${CONTAINER}" 2>/dev/null | grep -q true; then
  echo "❌ Redis container '${CONTAINER}' is not running."
  echo "   Start it with: docker compose up redis -d"
  exit 1
fi

cmd="${1:-help}"

case "$cmd" in

  monitor)
    echo "▶ Streaming all Redis commands — submit a task now (Ctrl-C to stop)"
    echo "  You will see: LPUSH (enqueue) → BRPOP (worker pulls) → SET (result stored)"
    echo ""
    docker exec -it "${CONTAINER}" redis-cli MONITOR
    ;;

  queue)
    echo "▶ Broker DB 0 — queue depth and messages"
    echo ""
    echo "Queue 'default' length:"
    $REDIS LLEN default
    echo ""
    echo "First message in 'default' queue (raw JSON envelope):"
    $REDIS LRANGE default 0 0
    echo ""
    echo "All list keys with depth > 0 (all active queues):"
    for key in $($REDIS --scan --pattern '*'); do
      type=$($REDIS TYPE "$key" 2>/dev/null | tr -d '\r')
      if [ "$type" = "list" ]; then
        len=$($REDIS LLEN "$key" 2>/dev/null | tr -d '\r')
        if [ "${len:-0}" -gt "0" ]; then
          echo "  $key → $len tasks"
        fi
      fi
    done
    ;;

  results)
    echo "▶ Results DB 0 — stored task results (celery-task-meta-*)"
    echo ""
    for key in $($REDIS --scan --pattern 'celery-task-meta-*'); do
      ttl=$($REDIS TTL "$key" 2>/dev/null | tr -d '\r')
      size=$($REDIS STRLEN "$key" 2>/dev/null | tr -d '\r')
      echo "  $key  TTL=${ttl}s  SIZE=${size}B"
    done
    count=$(($REDIS --scan --pattern 'celery-task-meta-*' | wc -l) 2>/dev/null || echo "?")
    echo ""
    echo "Total result keys: ${count}"
    ;;

  dbsize)
    echo "▶ Key counts in Redis DB 0"
    echo ""
    total=$($REDIS DBSIZE 2>/dev/null | tr -d '\r')
    queue=$($REDIS LLEN default 2>/dev/null | tr -d '\r')
    echo "  Total keys in DB 0 : $total"
    echo "  'default' queue    : $queue tasks"
    echo ""
    echo "Lab tip: submit fire_and_forget tasks and watch total keys."
    echo "         With ignore_result=True: no celery-task-meta-* keys added."
    ;;

  flush)
    echo "⚠  WARNING: this will delete ALL keys in Redis DB 0."
    read -r -p "Type 'yes' to confirm: " confirm
    if [ "$confirm" = "yes" ]; then
      $REDIS FLUSHDB
      echo "✅ Flushed DB 0."
    else
      echo "Aborted."
    fi
    ;;

  ttl)
    task_id="${2:-}"
    if [ -z "$task_id" ]; then
      echo "Usage: bash scripts/trace_redis.sh ttl <task-uuid>"
      exit 1
    fi
    key="celery-task-meta-${task_id}"
    echo "▶ TTL and value for task ${task_id}"
    ttl=$($REDIS TTL "$key" 2>/dev/null | tr -d '\r')
    size=$($REDIS STRLEN "$key" 2>/dev/null | tr -d '\r')
    val=$($REDIS GET "$key" 2>/dev/null)
    echo "  Key   : $key"
    echo "  TTL   : ${ttl}s"
    echo "  Size  : ${size}B"
    echo "  Value : $val"
    ;;

  help|*)
    echo "Usage: bash scripts/trace_redis.sh <command>"
    echo ""
    echo "Commands:"
    echo "  monitor        Stream all Redis commands in real-time"
    echo "  queue          Show all queue depths and first raw message"
    echo "  results        List all task result keys with TTLs"
    echo "  dbsize         Show total key counts"
    echo "  ttl <uuid>     Show TTL and value for a specific task result"
    echo "  flush          DANGER: clear all keys (lab reset)"
    echo ""
    echo "Redis access: docker exec ${CONTAINER} redis-cli"
    echo "Queue key   : 'default'  (CELERY_TASK_DEFAULT_QUEUE)"
    ;;
esac

