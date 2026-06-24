#!/usr/bin/env bash
# TT_SQL_PLATFORM - Stop all services
pkill -f "uvicorn main:app" 2>/dev/null && echo "[OK] Backend stopped"  || echo "[--] Backend not running"
pkill -f "gateway"          2>/dev/null && echo "[OK] Gateway stopped"  || echo "[--] Gateway not running"
pkill -f "vite"             2>/dev/null && echo "[OK] Frontend stopped" || echo "[--] Frontend not running"
