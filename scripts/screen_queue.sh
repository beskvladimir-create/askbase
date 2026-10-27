#!/bin/sh
# Run the remaining screening participants one after another, unattended.
#
# One model at a time, on purpose. The machine has 24 GB of unified memory and
# the measurement is as much about latency as about accuracy; two models
# resident at once would evict each other and the seconds per question would
# describe the eviction rather than the model.
#
# Each model is pulled only if it is missing, and the queue stops rather than
# filling the disk: this is somebody's working machine, not a build agent.
#
# The protocol is not an argument here. Sample, seed, stages and concurrency
# come from configs/screen.yaml and are the same for everyone, which is the
# only reason these numbers can be put in one table.
set -u
here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here" || exit 1
PY="$here/.venv/bin/python"
MIN_FREE_GB=6

log() { echo "[$(date '+%H:%M:%S')] $*"; }

free_gb() { df -g /System/Volumes/Data | tail -1 | awk '{print $4}'; }

wait_for_running_bench() {
    while pgrep -f "run_bench.py" > /dev/null 2>&1; do
        sleep 60
    done
}

# model key in screen.yaml -> ollama tag
set -- \
  "xiyan-14b-q4:hf.co/mradermacher/XiYanSQL-QwenCoder-14B-2504-GGUF:Q4_K_M" \
  "qwen25-coder-7b:qwen2.5-coder:7b" \
  "qwen25-coder-14b:qwen2.5-coder:14b" \
  "arctic-7b-q8:hf.co/mradermacher/Arctic-Text2SQL-R1-7B-GGUF:Q8_0"

log "ожидаю, пока закончится текущий прогон"
wait_for_running_bench
log "свободен"

for pair in "$@"; do
    key=${pair%%:*}
    tag=${pair#*:}

    if [ -f "results/$key.base.summary.json" ]; then
        log "$key уже посчитан, пропускаю"
        continue
    fi

    # The whole tag, anchored. Cutting at the first colon compared only the
    # name, so qwen2.5-coder:14b matched the installed qwen2.5-coder:7b and the
    # Q8 Arctic matched the installed Q4. Both "ran" against a tag Ollama does
    # not have, got 500 404s in half a second, and wrote a 0.0% result.
    if ! ollama list | awk '{print $1}' | grep -qxF "$tag"; then
        avail=$(free_gb)
        if [ "$avail" -lt 16 ]; then
            log "ОСТАНОВ: свободно ${avail} ГБ, на скачивание $key не хватит"
            exit 1
        fi
        log "качаю $tag"
        ollama pull "$tag" > "logs/pull-$key.log" 2>&1 || {
            log "ОСТАНОВ: не скачался $tag"; exit 1; }
    fi

    avail=$(free_gb)
    if [ "$avail" -lt "$MIN_FREE_GB" ]; then
        log "ОСТАНОВ: свободно ${avail} ГБ, это меньше порога ${MIN_FREE_GB}"
        exit 1
    fi

    log "замер $key"
    "$PY" scripts/run_bench.py --config configs/screen.yaml --model "$key" \
        --sample 500 --sample-seed 0 --stages base > "logs/$key.base.log" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
        log "$key завершился с кодом $rc, см. logs/$key.base.log"
    else
        log "$key готов"
    fi
done

log "очередь пройдена"
