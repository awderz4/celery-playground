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
#   flush     — DANGER: clear all Celery keys (for lab resets)
#
# Requirements: docker-compose up -d redis
# =============================================================================

set -euo pipefail

REDIS="docker-compose exec -T redis redis-cli"

cmd="${1:-help}"

case "$cmd" in

  monitor)
    echo "▶ Streaming all Redis commands — submit a task now (Ctrl-C to stop)"
    echo "  You will see: LPUSH (enqueue) → BRPOP (worker pulls) → SET (result stored)"
    echo ""
    docker-compose exec redis redis-cli MONITOR
    ;;

  queue)
    echo "▶ Broker DB 0 — queue depth and first message"
    echo ""
    echo "Queue length (celery default queue):"
    $REDIS LLEN celery
    echo ""
    echo "First message in queue (raw JSON envelope):"
    $REDIS LRANGE celery 0 0
    echo ""
    echo "All queues with depth > 0:"
    $REDIS --scan --pattern '*' | while read key; do
      type=$($REDIS TYPE "$key" 2>/dev/null | tr -d '\r')
      if [ "$type" = "list" ]; then
        len=$($REDIS LLEN "$key" 2>/dev/null | tr -d '\r')
        if [ "$len" -gt "0" ]; then
          echo "  $key → $len tasks"
        fi
      fi
    done
    ;;

  results)
    echo "▶ Results DB 1 — stored task results with TTLs"
    echo ""
    $REDIS -n 1 --scan --pattern 'celery-task-meta-*' | while read key; do
      ttl=$($REDIS -n 1 TTL "$key" 2>/dev/null | tr -d '\r')
      size=$($REDIS -n 1 STRLEN "$key" 2>/dev/null | tr -d '\r')
      echo "  $key  TTL=${ttl}s  SIZE=${size}B"
    done
    count=$($REDIS -n 1 DBSIZE 2>/dev/null | tr -d '\r')
    echo ""
    echo "Total result keys in DB 1: $count"
    ;;

  dbsize)
    echo "▶ Key counts: DB 0 (broker) vs DB 1 (results)"
    echo ""
    broker=$($REDIS -n 0 DBSIZE 2>/dev/null | tr -d '\r')
    results=$($REDIS -n 1 DBSIZE 2>/dev/null | tr -d '\r')
    echo "  DB 0 (broker)  : $broker keys"
    echo "  DB 1 (results) : $results keys"
    echo ""
    echo "Lab tip: run fire_and_forget tasks and compare DB 1 before/after."
    echo "         DB 1 should NOT grow — fire-and-forget stores nothing."
    ;;

  flush)
    echo "⚠  WARNING: this will delete all Celery keys in DB 0 and DB 1."
    read -r -p "Type 'yes' to confirm: " confirm
    if [ "$confirm" = "yes" ]; then
      $REDIS -n 0 FLUSHDB
      $REDIS -n 1 FLUSHDB
      echo "✅ Flushed both databases."
    else
      echo "Aborted."
    fi
    ;;

  ttl)
    task_id="${2:-}"
    if [ -z "$task_id" ]; then
      echo "Usage: $0 ttl <task-uuid>"
      exit 1
    fi
    key="celery-task-meta-${task_id}"
    echo "▶ TTL and value for task $task_id"
    ttl=$($REDIS -n 1 TTL "$key" 2>/dev/null | tr -d '\r')
    val=$($REDIS -n 1 GET "$key" 2>/dev/null)
    echo "  TTL   : ${ttl}s"
    echo "  Value : $val"
    ;;

  help|*)
    echo "Usage: bash scripts/trace_redis.sh <command>"
    echo ""
    echo "Commands:"
    echo "  monitor        Stream all Redis commands in real-time"
    echo "  queue          Show queue depth and first raw message"
    echo "  results        List all task result keys with TTLs"
    echo "  dbsize         Compare broker vs results DB key counts"
    echo "  ttl <uuid>     Show TTL and value for a specific task result"
    echo "  flush          DANGER: clear all Celery keys (lab reset)"
    ;;
esac

