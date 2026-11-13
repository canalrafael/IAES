#!/bin/sh
# /root/attack_listener.sh (VM3)
# Listens on IPC Channel 2 (0x70000000, offset 0: attack_trigger)
#   Value 1: start /root/memhog
#   Value 0: stop /root/memhog

MEMHOG_PID=""
IPC_SIGNAL="/root/ipc_signal"

echo "[VM3] Attack listener started on IPC (0x70000000)..."

while true; do
    if [ -x "$IPC_SIGNAL" ]; then
        STATUS=$($IPC_SIGNAL read 0 2>/dev/null)
        if [ "$STATUS" = "1" ]; then
            if [ -z "$MEMHOG_PID" ] || ! kill -0 $MEMHOG_PID 2>/dev/null; then
                echo "[VM3-IPC] Trigger received: STARTING MEMHOG CONTENTION!"
                /root/memhog &
                MEMHOG_PID=$!
            fi
        elif [ "$STATUS" = "0" ]; then
            if [ -n "$MEMHOG_PID" ] && kill -0 $MEMHOG_PID 2>/dev/null; then
                echo "[VM3-IPC] Trigger received: STOPPING MEMHOG CONTENTION!"
                kill -9 $MEMHOG_PID 2>/dev/null
                killall memhog 2>/dev/null
                MEMHOG_PID=""
            fi
        fi
    fi
    sleep 0.2
done

