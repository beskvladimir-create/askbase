#!/bin/sh
# Run every participant over held-out set 1, in the order the plan fixes.
#
# Set 1 is spent by this script. It is run once, its failures are then read by
# hand, and that reading makes it development data: from that moment it may not
# decide anything (HOLDOUT.md, "After the run"). So this is not a script to try
# out. Read HOLDOUT.md first, then run it once.
#
# Two steps per model, in this order, because the second refuses without the
# first: the journal entry, then the two language stages. The journal is what
# makes a repeat visible and what makes a repeat need a stated reason.
#
# One model at a time and one request at a time. The stand refuses a
# concurrency above 1 here: П5 is a threshold on p95 latency and this set
# calibrates it, so requests in flight would measure the queue.
#
# Expect hours, not minutes. 192 wordings per model, six models, and the
# verbose ones take ten times as long per answer as the terse ones. The
# screening numbers in results/*.base.summary.json are the guide.
set -u
here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here" || exit 1
PY="$here/.venv/bin/python"
CONFIG=configs/holdout.yaml
DATA=data/holdout

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# Same six as the screening, so the two sets can be read side by side.
MODELS="arctic-7b-q4 arctic-7b-q8 xiyan-7b-q4 xiyan-14b-q4 qwen25-coder-7b qwen25-coder-14b"

# Before anything, and once: a set that does not match the freeze stops the
# whole queue rather than the current model. If the set moved, every result
# after it would be from a different experiment.
log "сверяю набор с заморозкой"
"$PY" -m nl2sql_app.holdout.verify --data "$DATA" || {
    log "ОСТАНОВ: набор не совпал с замороженным"; exit 1; }

for key in $MODELS; do
    if [ -f "results/$key.holdout-ru.summary.json" ]; then
        log "$key уже прогнан по набору, пропускаю"
        continue
    fi

    tag=$("$PY" - "$key" <<'EOF'
import sys, yaml
print(yaml.safe_load(open("configs/holdout.yaml"))["models"][sys.argv[1]]["model"])
EOF
    ) || { log "ОСТАНОВ: $key нет в $CONFIG"; exit 1; }

    # The whole tag, anchored. Cutting at the first colon compared only the
    # name, so the Q8 build matched the installed Q4, "ran" against a tag
    # Ollama does not have and wrote out a 0.0% result. That mistake cost two
    # bogus entries in results/ during the screening; here it would cost the
    # set, which cannot be regenerated as unseen.
    if ! ollama list | awk '{print $1}' | grep -qxF "$tag"; then
        log "ОСТАНОВ: $tag не установлен. ollama pull '$tag'"
        exit 1
    fi

    log "шаг 1: запись прогона $key в журнал"
    "$PY" -m nl2sql_app.holdout.verify --data "$DATA" --record "$key" || {
        log "ОСТАНОВ: прогон $key не записан, дальше идти нельзя"; exit 1; }

    log "шаг 2: замер $key на двух языках"
    "$PY" scripts/run_bench.py --config "$CONFIG" --model "$key" \
        --stages holdout-en holdout-ru > "logs/$key.holdout.log" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
        # Not a 0% result and not a reason to go on to the next model. A failed
        # run is not a result, and a queue that walks past one spends the set
        # on runs nobody will trust.
        log "ОСТАНОВ: $key завершился с кодом $rc, см. logs/$key.holdout.log"
        exit 1
    fi
    log "$key готов"
done

log "очередь пройдена"
echo
echo "Дальше по плану, и это не автоматизируется:"
echo "  ручной разбор минимум 20 случайных провалов на прогон,"
echo "  с разделением на ошибку модели и ложное срабатывание проверяльщика."
echo "  Вердикт без этого шага это вердикт о проверяльщике."
