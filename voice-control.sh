#!/bin/bash
# Voice-to-Text Control Script

case "$1" in
    start)
        echo "Starting Voice-to-Text Push-to-Talk system..."
        # Kill any existing instances first
        pkill -f "start_push_to_talk.py" 2>/dev/null
        pkill -f "start-voice-to-text.sh" 2>/dev/null
        
        # Start in background
        nohup /home/ryan/voice-to-text-system/start-voice-to-text.sh > /dev/null 2>&1 &
        echo "Voice-to-Text system started in background (PID: $!)"
        echo "Hold Alt key to record, release to transcribe."
        ;;
        
    stop)
        echo "Stopping Voice-to-Text system..."
        pkill -f "start_push_to_talk.py"
        pkill -f "start-voice-to-text.sh"
        echo "Voice-to-Text system stopped."
        ;;
        
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
        
    status)
        # start-voice-to-text.sh sleeps briefly before launching Python, so check both.
        if pgrep -f "start_push_to_talk.py" > /dev/null || pgrep -f "start-voice-to-text.sh" > /dev/null; then
            echo "Voice-to-Text system is RUNNING"
            echo "Process details:"
            ps aux | grep -E "start_push_to_talk.py|start-voice-to-text.sh" | grep -v grep
        else
            echo "Voice-to-Text system is NOT RUNNING"
        fi
        ;;
        
    logs)
        LOG_FILE="/home/ryan/voice-to-text-system/logs/voice-to-text-$(date +%Y%m%d).log"
        if [ -f "$LOG_FILE" ]; then
            echo "Showing recent logs from $LOG_FILE:"
            tail -n 50 "$LOG_FILE"
        else
            echo "No log file found for today. Checking push_to_talk.log..."
            tail -n 50 /home/ryan/voice-to-text-system/push_to_talk.log 2>/dev/null || echo "No logs available"
        fi
        ;;
        
    test)
        echo "Testing Voice-to-Text system (will run in foreground, press Ctrl+C to stop)..."
        cd /home/ryan/voice-to-text-system
        .venv/bin/python start_push_to_talk.py
        ;;
        
    *)
        echo "Voice-to-Text Control Script"
        echo "Usage: $0 {start|stop|restart|status|logs|test}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the voice-to-text system in background"
        echo "  stop    - Stop the voice-to-text system"
        echo "  restart - Restart the voice-to-text system"
        echo "  status  - Check if the system is running"
        echo "  logs    - Show recent log entries"
        echo "  test    - Run in foreground for testing (Ctrl+C to stop)"
        echo ""
        echo "How to use when running:"
        echo "  - Hold Alt key to start recording"
        echo "  - Release Alt key to stop recording and transcribe"
        echo "  - Text will be inserted at cursor position"
        ;;
esac
