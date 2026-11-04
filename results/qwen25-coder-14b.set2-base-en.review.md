# Ручной разбор провалов: qwen25-coder-14b.set2-base-en.jsonl

Провалов всего: 364 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-017 en/1

ловушка: the operation date is split across the legacy pair dt_op/posted_at; dates are text, so the month is the first seven characters
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT substr(COALESCE(dt_op, posted_at), 1, 7) AS month, COUNT(*) AS n FROM txn WHERE COALESCE(dt_op, posted_at) >= '2026-01-01' GROUP BY month ORDER BY month
    ('2026-01', 152)
    ('2026-02', 120)
    ('2026-03', 127)
    ('2026-04', 148)
    ('2026-05', 157)
    ('2026-06', 117)
    ('2026-07', 118)
    ('2026-08', 141)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT 
    strftime('%Y-%m', txn.dt_op) AS month, 
    COUNT(*) AS operation_count
FROM 
    txn
WHERE 
    strftime('%Y', txn.dt_op) = '2026'
GROUP BY 
    month
ORDER BY 
    month
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: берёт только dt_op без COALESCE, у старых строк он пуст, выдача пустая

## 2. banking/bank2-042 en/0

ловушка: there is no balance column: it has to be built from dir_cd before it can be compared; the condition is on the aggregate of each account, so the grouping happens twice; currency is a code, needs the lookup join
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT cr.title AS currency, COUNT(*) AS accounts FROM (SELECT a.id, a.cur_cd, SUM(CASE WHEN t.dir_cd = 2 THEN t.amt_cents ELSE -t.amt_cents END) AS net FROM acct a JOIN txn t ON t.acct_id = a.id GROUP BY a.id, a.cur_cd) s JOIN cur_ref cr ON cr.cd = s.cur_cd WHERE s.net < 0 GROUP BY cr.title ORDER BY accounts DESC, cr.title
    ('EUR', 250)
    ('USD', 132)
    ('GBP', 72)

ответ модели:
    SELECT 
    cur_cd, 
    COUNT(*) AS account_count
FROM 
    acct
JOIN 
    txn ON acct.id = txn.acct_id
WHERE 
    dir_cd = 'OUT'
GROUP BY 
    cur_cd
HAVING 
    SUM(amt_cents) > 0
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает код направления со строкой OUT, выдача пустая

## 3. hr/hr2-012 en/0

ловушка: there is no tenure column; it has to be computed from hired_at; 'working' is the status, not the absence of a leaving date
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG((julianday('2026-11-02') - julianday(hired_at)) / 365.25), 1) AS years FROM emp WHERE status_cd = 1
    (6.7,)

ответ модели:
    SELECT AVG(julianday('2026-11-02') - julianday(hired_at)) / 365.25 AS avg_length_of_service
FROM emp
WHERE status_cd = (SELECT cd FROM emp_status_ref WHERE title = 'Active')
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: ищет статус с названием Active, которого в справочнике нет

## 4. hr/hr2-044 en/1

ловушка: the salary in force is the latest from_dt per person, so a plain join averages the history instead; the state is a code, its name lives in emp_status_ref; the currencies must not be mixed, so the euro rows are the only ones that count
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT s.title AS status, ROUND(AVG(p.amount_minor) / 100.0, 2) AS mean_pay FROM emp e JOIN emp_status_ref s ON s.cd = e.status_cd JOIN pay_hist p ON p.emp_id = e.id WHERE p.cur_cd = 1 AND p.from_dt = (SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id) GROUP BY s.title ORDER BY mean_pay DESC, s.title
    ('left', 7017.05)
    ('working', 6619.42)
    ('unpaid leave', 6341.6)

ответ модели:
    SELECT 
    e.status_cd, 
    ROUND(AVG(p.amount_minor), 2) AS mean_salary_eur
FROM 
    emp e
JOIN 
    pay_hist p ON e.id = p.emp_id
JOIN 
    cur_ref c ON p.cur_cd = c.cd
WHERE 
    c.title = 'Euro'
    AND p.from_dt = (
        SELECT MAX(ph.from_dt) 
        FROM pay_hist ph 
        WHERE ph.emp_id = e.id
    )
GROUP BY 
    e.status_cd
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: ищет валюту с названием Euro, которого в справочнике нет

## 5. logistics/log2-006 en/1

ловушка: distance per shipment means summing its legs first and averaging after, not averaging the legs
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(total), 1) AS mean_km FROM (SELECT SUM(dist_km) AS total FROM leg GROUP BY shp_id)
    (3668.7,)

ответ модели:
    SELECT ROUND(AVG(dist_km), 1) AS mean_distance_km
FROM leg
    (1328.9,)

ошибка исполнения: нет

вердикт: model
заметка: усредняет плечи вместо суммы по отправлению

## 6. logistics/log2-013 en/0

ловушка: cost is in minor units; the answer is the ratio of the two sums, not the average of the per-leg ratios
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(cost_cents) / 100.0 / SUM(dist_km), 4) AS per_km FROM leg
    (3.6509,)

ответ модели:
    SELECT AVG(cost_cents / dist_km) AS avg_cost_per_km
FROM leg
    (761.8077777777778,)

ошибка исполнения: нет

вердикт: model
заметка: среднее отношений вместо отношения сумм, и копейки не переведены

## 7. logistics/log2-027 en/0

ловушка: the kind of incident is a code, 3 is the customs hold, and its name lives in kind_ref; two incidents on one shipment must not count it twice
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(DISTINCT s.id) AS n FROM shp s JOIN inc i ON i.shp_id = s.id WHERE i.kind_cd = 3 AND s.status_cd = 2
    (30,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
WHERE id IN (
    SELECT shp_id 
    FROM inc 
    WHERE kind_cd = (SELECT cd FROM kind_ref WHERE title = 'Customs Hold') 
    AND shp_id IN (
        SELECT shp_id 
        FROM shp 
        WHERE status_cd = (SELECT cd FROM status_ref WHERE title = 'Delivered')
    )
)
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: ищет коды по названиям, которых в справочниках нет, ответ 0

## 8. logistics/log2-036 en/0

ловушка: the customer's city is text while the destination is a code, so the join has to resolve the code first; the destination end, not the origin; a customer with no city recorded matches nothing, because NULL is not equal to anything
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM shp s JOIN cust c ON c.id = s.cust_id JOIN loc_ref d ON d.cd = s.dst_cd WHERE c.city = d.title
    (80,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
JOIN cust ON shp.cust_id = cust.id 
WHERE shp.dst_cd = cust.city
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает код пункта назначения с текстом города

## 9. manufacturing/mfg2-008 en/0

ловушка: the price is effective-dated, so the join is on a range and not on equality; valid_to NULL means the window is still open; the movement date is split across the legacy pair dt_op/recorded_at
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title, ROUND(SUM(m.qty * u.to_base * pp.minor / 100.0), 2) AS cost FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id AND COALESCE(m.dt_op, m.recorded_at) >= pp.valid_from AND (pp.valid_to IS NULL OR COALESCE(m.dt_op, m.recorded_at) < pp.valid_to) WHERE m.kind_cd = 3 GROUP BY p.title ORDER BY cost DESC, p.title
    ('plate', 849002.38)
    ('bracket', 787855.88)
    ('bushing', 468658.37)
    ('shaft', 282764.78)
    ('gearwheel', 151865.97)
    ('spring', 16581.37)

ответ модели:
    SELECT 
    p.title AS part_title,
    pp.minor AS scrap_cost
FROM 
    defect d
JOIN 
    mov m ON d.mov_id = m.id
JOIN 
    part p ON m.part_id = p.id
JOIN 
    part_price pp ON p.id = pp.part_id
WHERE 
    pp.valid_from <= d.found_at AND (pp.valid_to IS NULL OR pp.valid_to > d.found_at)
    ('plate', 13363)
    ('plate', 13363)
    ('shaft', 1452)
    ('gearwheel', 4865)
    ('shaft', 1452)
    ('bracket', 1749)
    ('shaft', 1659)
    ('bracket', 1889)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: строит ответ от таблицы дефектов, без суммы и без перевода единиц

## 10. manufacturing/mfg2-015 en/0

ловушка: the rows whose dates run the wrong way have to be excluded or the average mixes negative gaps into it
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at))), 1) AS days FROM defect d JOIN mov m ON m.id = d.mov_id WHERE d.found_at >= COALESCE(m.dt_op, m.recorded_at)
    (404.3,)

ответ модели:
    SELECT AVG(julianday(defect.found_at) - julianday(mov.dt_op)) AS avg_days
FROM defect
JOIN mov ON defect.mov_id = mov.id
WHERE defect.found_at > mov.dt_op
    (429.81065088757396,)

ошибка исполнения: нет

вердикт: model
заметка: без COALESCE на дату операции, среднее 429.8 против 404.3

## 11. manufacturing/mfg2-022 en/1

ловушка: the window covering a date is a comparison on both ends, and the open end is a NULL rather than a far-off date; the price is in minor units
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, pp.minor / 100.0 AS price FROM part p JOIN part_price pp ON pp.part_id = p.id WHERE pp.valid_from <= '2026-03-01' AND (pp.valid_to IS NULL OR pp.valid_to > '2026-03-01') ORDER BY p.code
    ('BR-100', 21.2)
    ('BU-550', 49.22)
    ('GR-440', 48.65)
    ('PL-330', 133.63)
    ('SH-210', 16.59)
    ('SP-660', 23.57)

ответ модели:
    SELECT 
    p.id AS part_id,
    p.title AS part_title,
    pp.minor / 100 AS price_in_whole_units
FROM 
    part p
JOIN 
    part_price pp ON p.id = pp.part_id
WHERE 
    pp.valid_from <= '2026-03-01' AND (pp.valid_to IS NULL OR pp.valid_to > '2026-03-01')
ORDER BY 
    p.id
    (1, 'bracket', 21)
    (2, 'shaft', 16)
    (3, 'plate', 133)
    (4, 'gearwheel', 48)
    (5, 'bushing', 49)
    (6, 'spring', 23)

ошибка исполнения: нет

вердикт: model
заметка: целочисленное деление, 21 вместо 21.2, и лишние столбцы

## 12. manufacturing/mfg2-027 en/1

ловушка: the difference between two text dates needs julianday, subtraction returns nonsense; the movement date is split across the legacy pair dt_op/recorded_at; a defect found before its movement gives a negative number, which the maximum simply ignores
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title, CAST(MAX(julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at))) AS INTEGER) AS days FROM defect d JOIN mov m ON m.id = d.mov_id JOIN part p ON p.id = m.part_id GROUP BY p.title ORDER BY days DESC, p.title
    ('plate', 1065)
    ('bracket', 1044)
    ('bushing', 987)
    ('shaft', 931)
    ('gearwheel', 854)
    ('spring', 727)

ответ модели:
    SELECT 
    p.id AS part_id,
    p.title AS part_title,
    MAX(DATEDIFF(d.found_at, m.dt_op)) AS max_days_to_defect
FROM 
    part p
JOIN 
    mov m ON p.id = m.part_id
LEFT JOIN 
    defect d ON m.id = d.mov_id
GROUP BY 
    p.id, p.title
    ОШИБКА: OperationalError: no such function: DATEDIFF

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: вызывает DATEDIFF, которой в SQLite нет

## 13. manufacturing/mfg2-045 en/1

ловушка: the earliest movement is per part, which makes the subquery correlated; the movement date is split across the legacy pair, inside the subquery as well as outside it; the price is joined on a range, not on equality
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, pp.minor / 100.0 AS price FROM mov m JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id AND pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at)) WHERE COALESCE(m.dt_op, m.recorded_at) = (SELECT MIN(COALESCE(m2.dt_op, m2.recorded_at)) FROM mov m2 WHERE m2.part_id = m.part_id) GROUP BY p.code, pp.minor ORDER BY p.code
    ('BR-100', 14.86)
    ('BU-550', 36.64)
    ('GR-440', 34.5)
    ('PL-330', 88.52)
    ('SH-210', 11.32)
    ('SP-660', 16.07)

ответ модели:
    SELECT 
    p.code AS part_code,
    pp.minor AS price
FROM 
    part p
JOIN 
    mov m ON p.id = m.part_id
JOIN 
    part_price pp ON p.id = pp.part_id
WHERE 
    pp.valid_from <= m.dt_op AND (pp.valid_to IS NULL OR pp.valid_to > m.dt_op)
GROUP BY 
    p.code
ORDER BY 
    MIN(m.dt_op)
    ('BR-100', 1486)
    ('BU-550', 3664)
    ('SH-210', 1132)
    ('PL-330', 8852)
    ('GR-440', 3450)
    ('SP-660', 1607)

ошибка исполнения: нет

вердикт: model
заметка: цена в копейках, 1486 вместо 14.86, и окно не привязано к первому движению

## 14. manufacturing/mfg2-047 en/1

ловушка: the kind is a code, its name lives in mov_kind_ref; the price is joined on a range, and a plain join on part_id multiplies every movement; the quantity has to be converted before it is multiplied by the price
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT k.title AS kind, ROUND(SUM(m.qty * u.to_base * pp.minor / 100.0), 2) AS value FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN mov_kind_ref k ON k.cd = m.kind_cd JOIN part_price pp ON pp.part_id = m.part_id AND pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at)) GROUP BY k.title ORDER BY value DESC, k.title
    ('receipt', 13385594.72)
    ('issue', 13026270.79)
    ('scrap', 2556728.75)

ответ модели:
    SELECT 
    mk.title AS kind_title,
    m.dt_op AS date,
    SUM(pp.minor * m.qty * ur.to_base) AS total_value
FROM 
    mov m
JOIN 
    mov_kind_ref mk ON m.kind_cd = mk.cd
JOIN 
    part_price pp ON m.part_id = pp.part_id
JOIN 
    unit_ref ur ON m.unit_cd = ur.cd
WHERE 
    pp.valid_from <= m.dt_op AND pp.valid_to >= m.dt_op
GROUP BY 
    mk.title, m.dt_op
ORDER BY 
    mk.title, m.dt_op
    ('issue', '2023-09-10', 271136.0)
    ('issue', '2023-09-14', 169404.0)
    ('issue', '2023-09-16', 575082.0)
    ('issue', '2023-09-21', 593400.0)
    ('issue', '2023-10-03', 844868.0000000001)
    ('issue', '2023-10-11', 10312840.0)
    ('issue', '2023-10-14', 1856894.0)
    ('issue', '2023-10-15', 422024.0)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: группирует ещё и по дате, вместо трёх строк сотни

## 15. medicine/med2-007 en/1

ловушка: the admission date has to be assembled from the legacy pair; 'longer than two weeks' is a strict comparison against 14 days
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM enc WHERE status_cd = 2 AND julianday(discharged) - julianday(COALESCE(dt_adm, admitted_at)) > 14
    (210,)

ответ модели:
    SELECT COUNT(*) 
FROM enc 
WHERE discharged = 1 AND (julianday('now') - julianday(dt_adm)) > 14
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает discharged с единицей и считает от сегодняшнего дня

## 16. medicine/med2-011 en/0

ловушка: secondary is primary_flag = 0, the inverse of the flag's name; the name is in dx_ref, not in dx
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT x.title, COUNT(*) AS n FROM dx d JOIN dx_ref x ON x.code = d.code WHERE d.primary_flag = 0 GROUP BY x.title ORDER BY n DESC, x.title
    ('essential hypertension', 85)
    ('gastro-oesophageal reflux', 64)
    ('malignant neoplasm of breast', 62)
    ('acute myocardial infarction', 56)
    ('asthma', 53)
    ('epilepsy', 52)
    ('type 2 diabetes mellitus', 50)
    ('chronic kidney disease', 49)

ответ модели:
    SELECT dx_ref.title, COUNT(*) AS frequency
FROM dx
JOIN dx_ref ON dx.code = dx_ref.code
WHERE dx.primary_flag = 'N'
GROUP BY dx_ref.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает признак с буквой N, выдача пустая

## 17. medicine/med2-020 en/0

ловушка: the admission date is split across the legacy pair; an empty discharge column is a NULL test, not a comparison with a date
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM enc WHERE COALESCE(dt_adm, admitted_at) >= '2026-01-01' AND discharged IS NULL
    (149,)

ответ модели:
    SELECT COUNT(*) 
FROM enc 
WHERE strftime('%Y', dt_adm) = '2026' AND discharged IS NULL
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: берёт только dt_adm без COALESCE, ответ 0

## 18. medicine/med2-039 en/0

ловушка: HAVING over a distinct count, not over a plain count of encounters; the answer is the number of people, so the grouped rows have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT pat_id FROM enc GROUP BY pat_id HAVING COUNT(DISTINCT doc_id) > 1)
    (261,)

ответ модели:
    SELECT COUNT(DISTINCT pat_id) 
FROM enc 
GROUP BY pat_id 
HAVING COUNT(DISTINCT doc_id) > 1
    (1,)
    (1,)
    (1,)
    (1,)
    (1,)
    (1,)
    (1,)
    (1,)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: не считает сгруппированные строки повторно, вернул по единице на пациента

## 19. public_services/gov2-005 en/1

ловушка: the submission date is split across the legacy pair dt_sub/submitted_at; only the closed cases have both ends of the interval
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title, ROUND(AVG(julianday(c.closed_at) - julianday(COALESCE(c.dt_sub, c.submitted_at))), 1) AS days FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL GROUP BY sv.title ORDER BY days DESC, sv.title
    ('building permit', 25.2)
    ('trading licence', 20.4)
    ('residence certificate', 13.9)
    ('land record extract', 10.9)
    ('business registration', 10.3)

ответ модели:
    SELECT 
    s.title AS service_title,
    AVG(julianday(c.closed_at) - julianday(c.submitted_at)) AS mean_days
FROM 
    case_rec c
JOIN 
    service s ON c.service_id = s.id
JOIN 
    stage st ON c.id = st.case_id
JOIN 
    result_ref r ON st.result_cd = r.cd
WHERE 
    r.title = 'Finished'
GROUP BY 
    s.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: фильтрует по несуществующему названию результата, выдача пустая

## 20. public_services/gov2-046 en/1

ловушка: the allowance is a column of the service, so the threshold differs from row to row; the subtraction runs in the opposite direction from the usual lateness question; a case with no closing date cannot qualify and must be excluded
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL AND julianday(c.due_dt) - julianday(c.closed_at) > sv.sla_days * 1.0 / 2
    (206,)

ответ модели:
    SELECT COUNT(*) 
FROM case_rec 
JOIN service ON case_rec.service_id = service.id 
WHERE case_rec.closed_at < case_rec.due_dt 
AND julianday(case_rec.closed_at) - julianday(case_rec.dt_sub) > service.sla_days / 2
    (74,)

ошибка исполнения: нет

вердикт: model
заметка: считает срок от подачи вместо недобега до срока, 74 против 206
