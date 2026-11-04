#!/bin/sh
# Набор 2, прогон в том порядке, который записан в HOLDOUT.md до прогона.
#
# Этот скрипт расходует решающий набор. Прочитайте HOLDOUT.md, раздел про
# заморозку набора 2 и про предсказания, и только потом запускайте, один раз.
#
# Порядок не произвольный. Сначала наш движок и единственный кандидат, потому
# что это и есть вопрос, на который набор отвечает; потом те же веса без
# промпта, потому что без этой строки вклад движка не к чему отнести; потом
# остальные пять участников для таблицы П1 и П3.
#
# Каждая стадия пишет results/<модель>.<стадия>.jsonl и .summary.json. Если
# сводка уже есть, стадия пропускается: прерванную очередь можно продолжить, и
# повторный прогон уже сделанного не нужен и был бы повтором.
#
# Ждите часов, не минут. 576 формулировок на язык, по одному запросу. На
# наборе 1 то же железо давало 6 с на формулировку для 14B и 26 с для Arctic,
# то есть примерно час на язык у первых и четыре у вторых.
set -u
here=$(cd "$(dirname "$0")/.." && pwd)
cd "$here" || exit 1
PY="$here/.venv/bin/python"
CONFIG=configs/holdout2.yaml
DATA=data/holdout2
SET=2

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Этап 1, один раз на всю очередь: набор, не совпавший с заморозкой,
# останавливает всё, а не текущую модель.
log "сверяю набор 2 с заморозкой"
"$PY" -m nl2sql_app.holdout.verify --data "$DATA" --set "$SET" >/dev/null || {
    log "ОСТАНОВ: набор не совпал с замороженным"; exit 1; }

# Модель и её стадии. Наш движок первым, кандидат вторым, голые веса третьими,
# остальные участники после.
PLAN="
qwen25-coder-14b:set2-app-en set2-app-ru
qwen25-coder-14b:set2-app-ord-en set2-app-ord-ru
qwen25-coder-14b:set2-base-en set2-base-ru
qwen25-coder-7b:set2-base-en set2-base-ru
xiyan-7b-q4:set2-base-en set2-base-ru
xiyan-14b-q4:set2-base-en set2-base-ru
arctic-7b-q4:set2-base-en set2-base-ru
arctic-7b-q8:set2-base-en set2-base-ru
"

# Через файл, а не через конвейер. `printf ... | while read` запускает цикл в
# подоболочке, и `exit 1` внутри него выходит из подоболочки, а не из скрипта:
# очередь шла бы дальше после провала, то есть ровно то, что этот скрипт
# обещает не делать. Проверено на игрушечном примере, прежде чем переписать.
plan_file=$(mktemp)
trap 'rm -f "$plan_file"' EXIT HUP INT TERM
printf '%s\n' "$PLAN" > "$plan_file"

while IFS= read -r line; do
    [ -n "$line" ] || continue
    key=${line%%:*}
    stages=${line#*:}

    done_all=1
    for st in $stages; do
        [ -f "results/$key.$st.summary.json" ] || done_all=0
    done
    if [ "$done_all" -eq 1 ]; then
        log "$key $stages уже прогнано, пропускаю"
        continue
    fi

    tag=$("$PY" - "$key" <<'EOF'
import sys, yaml
print(yaml.safe_load(open("configs/holdout2.yaml"))["models"][sys.argv[1]]["model"])
EOF
    ) || { log "ОСТАНОВ: $key нет в $CONFIG"; exit 1; }

    # Весь тег, целиком. На скрининге сравнение по имени до первого двоеточия
    # приняло сборку Q8 за установленную Q4 и выдало 0.0% против тега, которого
    # у Ollama нет. Здесь такая ошибка стоила бы набора.
    if ! ollama list | awk '{print $1}' | grep -qxF "$tag"; then
        log "ОСТАНОВ: $tag не установлен. ollama pull '$tag'"
        exit 1
    fi

    # Запись в журнал нужна один раз на инструмент и набор. Второй вызов для
    # того же инструмента это повтор, и он требует причины, поэтому делается
    # только если записи ещё нет.
    if ! "$PY" - "$key" <<'EOF'
import sys
from nl2sql_app.holdout.verify import previous_runs
raise SystemExit(0 if previous_runs(sys.argv[1], 2) else 1)
EOF
    then
        log "шаг 1: запись прогона $key по набору 2 в журнал"
        "$PY" -m nl2sql_app.holdout.verify --data "$DATA" --set "$SET" --record "$key" || {
            log "ОСТАНОВ: прогон $key не записан, дальше идти нельзя"; exit 1; }
    fi

    log "шаг 2: $key, стадии $stages"
    "$PY" scripts/run_bench.py --config "$CONFIG" --model "$key" \
        --stages $stages >> "logs/$key.set2.log" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
        log "ОСТАНОВ: $key завершился с кодом $rc, см. logs/$key.set2.log"
        exit 1
    fi
    log "$key $stages готово"
done < "$plan_file"

log "очередь по набору 2 пройдена"
echo
echo "Дальше по плану, и это не автоматизируется:"
echo "  ручной разбор минимум 20 случайных провалов на прогон,"
echo "  с разделением на ошибку модели и ложное срабатывание проверяльщика."
echo "  Вердикт без этого шага это вердикт о проверяльщике."
