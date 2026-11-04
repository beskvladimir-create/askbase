# Ручной разбор провалов: qwen25-coder-14b.set2-app-ord-en.jsonl

Провалов всего: 255 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-034 en/0

ловушка: loan joined twice to itself, with the pair taken once by comparing ids; a loan without a closing date has no end, so NULL has to stand for the far future
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT DISTINCT c.full_name FROM loan l1 JOIN loan l2 ON l2.cust_id = l1.cust_id AND l2.id > l1.id JOIN cust c ON c.id = l1.cust_id WHERE l1.opened_at <= COALESCE(l2.closed_at, '9999-12-31') AND l2.opened_at <= COALESCE(l1.closed_at, '9999-12-31') ORDER BY c.full_name
    ('Alina Marek',)
    ('Alina Soto',)
    ('Anna Petran',)
    ('Artem Benali',)
    ('Artem Kovach',)
    ('Artem Kristof',)
    ('Boris Almeida',)
    ('Boris Kovach',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT DISTINCT c1.full_name
FROM cust c1
JOIN loan l1 ON c1.id = l1.cust_id
JOIN loan l2 ON c1.id = l2.cust_id
WHERE l1.id != l2.id
AND (
    (l1.opened_at <= l2.opened_at AND l1.closed_at > l2.opened_at)
    OR (l2.opened_at <= l1.opened_at AND l2.closed_at > l1.opened_at)
)
    ('Alina Soto',)
    ('Boris Kovach',)
    ('Mark Kristof',)
    ('Victor Petran',)
    ('Anna Petran',)
    ('Igor Bauer',)
    ('Irina Marek',)
    ('Vera Reiner',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: NULL в дате закрытия не считается бесконечностью, часть перекрытий потеряна

## 2. hr/hr2-040 en/1

ловушка: an inner join drops the people with no absence and raises the average; SUM over no rows is NULL rather than zero, so it has to be replaced before the averaging
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(k), 2) AS mean_days FROM (SELECT e.id, COALESCE(SUM(a.days), 0) AS k FROM emp e LEFT JOIN absence a ON a.emp_id = e.id GROUP BY e.id)
    (18.15,)

ответ модели:
    SELECT ROUND(COALESCE(SUM(days), 0) / COUNT(DISTINCT emp_id), 2) AS mean_absence_days
FROM absence
    (22.0,)

ошибка исполнения: нет

вердикт: model
заметка: делит на число отсутствовавших, а не на всех сотрудников, 22.0 против 18.15

## 3. logistics/log2-006 en/0

ловушка: distance per shipment means summing its legs first and averaging after, not averaging the legs
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(total), 1) AS mean_km FROM (SELECT SUM(dist_km) AS total FROM leg GROUP BY shp_id)
    (3668.7,)

ответ модели:
    SELECT CAST(SUM(T2.dist_km) AS REAL) / COUNT(T1.id) AS avg_dist_km
FROM shp AS T1
JOIN leg AS T2 ON T1.id = T2.shp_id
    (1328.8933333333334,)

ошибка исполнения: нет

вердикт: model
заметка: делит сумму плеч на число строк соединения, 1328.9 против 3668.7

## 4. logistics/log2-030 en/0

ловушка: leg joined twice to itself, once as the first and once as the last; the last leg is the largest seq of that shipment, which is a correlated subquery; a single-leg shipment satisfies the equality trivially and the question excludes it
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM leg l1 JOIN leg l2 ON l2.shp_id = l1.shp_id WHERE l1.seq = 1 AND l2.seq = (SELECT MAX(seq) FROM leg WHERE shp_id = l1.shp_id) AND l2.seq > 1 AND l1.carr_id = l2.carr_id
    (6,)

ответ модели:
    SELECT COUNT(*) 
FROM (
    SELECT shp_id 
    FROM leg 
    GROUP BY shp_id 
    HAVING MIN(seq) = MAX(seq)
) AS single_leg_shipments
    (145,)

ошибка исполнения: нет

вердикт: model
заметка: считает перевозки из одного плеча, то есть ровно исключённый случай

## 5. logistics/log2-037 en/1

ловушка: an inner join drops the shipments with no leg and raises the average; COUNT(*) counts the row the outer join produced, so the count has to be over the leg's own column
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(k), 2) AS mean_legs FROM (SELECT s.id, COUNT(l.id) AS k FROM shp s LEFT JOIN leg l ON l.shp_id = s.id GROUP BY s.id)
    (2.57,)

ответ модели:
    SELECT CAST(COUNT(*) AS REAL) / COUNT(DISTINCT shp_id) AS mean_legs_per_shipment
FROM leg
    (2.7607361963190185,)

ошибка исполнения: нет

вердикт: model
заметка: перевозки без плеч не попали в среднее, 2.76 против 2.57

## 6. logistics/log2-041 en/0

ловушка: two joins to reach it: incident to shipment to the state lookup; the state is a code, its name lives in status_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT st.title AS status, COUNT(*) AS n FROM inc i JOIN shp s ON s.id = i.shp_id JOIN status_ref st ON st.cd = s.status_cd GROUP BY st.title ORDER BY n DESC, st.title
    ('delivered', 182)
    ('in transit', 44)
    ('booked', 27)
    ('lost', 7)

ответ модели:
    SELECT 
    l.title AS state, 
    COUNT(*) AS incident_count
FROM 
    inc 
JOIN 
    shp ON inc.shp_id = shp.id
JOIN 
    loc_ref l ON shp.dst_cd = l.cd
GROUP BY 
    l.title
    ('Avelin', 33)
    ('Eastvale', 39)
    ('Harrow', 26)
    ('Kesling', 27)
    ('Lowick', 34)
    ('Marden', 31)
    ('Northport', 25)
    ('Thorne', 45)

ошибка исполнения: нет

вердикт: model
заметка: группирует по городу назначения вместо состояния отправления

## 7. logistics/log2-045 en/0

ловушка: the country of arrival is two steps from the leg: shipment, then the destination code; the destination end, not the origin; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT l.carr_id FROM leg l JOIN shp s ON s.id = l.shp_id JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY l.carr_id HAVING COUNT(DISTINCT d.country) > 1)
    (45,)

ответ модели:
    SELECT COUNT(DISTINCT carr_id) 
FROM (
    SELECT l.carr_id, lr.country 
    FROM leg l 
    JOIN shp s ON l.shp_id = s.id 
    JOIN loc_ref lr ON s.dst_cd = lr.cd 
    GROUP BY l.carr_id, lr.country 
    HAVING COUNT(DISTINCT lr.country) > 1
)
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: distinct внутри группы по стране всегда 1, ответ 0

## 8. manufacturing/mfg2-008 en/1

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
    SUM(m.qty * pp.minor) AS total_value
FROM 
    mov m
JOIN 
    part p ON m.part_id = p.id
JOIN 
    part_price pp ON m.part_id = pp.part_id
    AND m.dt_op >= pp.valid_from
    AND (m.dt_op < pp.valid_to OR pp.valid_to IS NULL)
JOIN 
    mov_kind_ref mk ON m.kind_cd = mk.cd
WHERE 
    mk.title = 'scrap'
GROUP BY 
    p.title
    ('bracket', 7894433.13)
    ('bushing', 2349802.34)
    ('gearwheel', 7977819.77)
    ('plate', 30179877.44)
    ('shaft', 4815686.84)
    ('spring', 1196165.0)

ошибка исполнения: нет

вердикт: model
заметка: нет перевода единиц и копеек, суммы на порядок больше

## 9. manufacturing/mfg2-009 en/1

ловушка: here the range join is wrong: the question names one price, the open one, and a join on part_id alone multiplies every movement by the four price rows it has
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title, ROUND(SUM(m.qty * u.to_base * pp.minor / 100.0), 2) AS cost FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id WHERE pp.valid_to IS NULL GROUP BY p.title ORDER BY cost DESC, p.title
    ('plate', 16282147.35)
    ('bracket', 6168415.6)
    ('gearwheel', 5076043.7)
    ('bushing', 3683280.26)
    ('shaft', 2744815.5)
    ('spring', 269664.37)

ответ модели:
    SELECT 
    p.id AS part_id,
    p.title AS part_title,
    SUM(m.qty * pp.minor) AS total_value
FROM 
    mov m
JOIN 
    part p ON m.part_id = p.id
JOIN 
    part_price pp ON p.id = pp.part_id
    AND pp.valid_from <= COALESCE(m.dt_op, m.recorded_at)
    AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at))
GROUP BY 
    p.id, p.title
    (1, 'bracket', 96959263.59)
    (2, 'shaft', 61116100.18)
    (3, 'plate', 309851149.18)
    (4, 'gearwheel', 82977123.88)
    (5, 'bushing', 44862288.35)
    (6, 'spring', 8234924.55)

ошибка исполнения: нет

вердикт: model
заметка: взял цену на дату движения, хотя вопрос просил текущую открытую

## 10. manufacturing/mfg2-017 en/0

ловушка: both the numerator and the denominator need the unit conversion, and leaving it out of one of the two skews the share
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title, ROUND(100.0 * SUM(CASE WHEN m.kind_cd = 3 THEN m.qty * u.to_base ELSE 0 END) / SUM(m.qty * u.to_base), 1) AS pct FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id GROUP BY p.title ORDER BY pct DESC, p.title
    ('bushing', 15.4)
    ('bracket', 15.2)
    ('shaft', 12.0)
    ('spring', 7.9)
    ('plate', 7.3)
    ('gearwheel', 3.4)

ответ модели:
    SELECT 
    p.title AS part_title,
    SUM(CASE WHEN mk.title = 'scrap' THEN m.qty * ur.to_base ELSE 0 END) / SUM(m.qty * ur.to_base) * 100 AS scrap_share
FROM 
    mov m
JOIN 
    part p ON m.part_id = p.id
JOIN 
    mov_kind_ref mk ON m.kind_cd = mk.cd
JOIN 
    unit_ref ur ON m.unit_cd = ur.cd
GROUP BY 
    p.title
ORDER BY 
    scrap_share DESC
    ('bushing', 15.411649940534256)
    ('bracket', 15.18646700783261)
    ('shaft', 12.021154427319432)
    ('spring', 7.88392623022463)
    ('plate', 7.32323854076901)
    ('gearwheel', 3.445532787670839)

ошибка исполнения: нет

вердикт: evaluator
заметка: те же доли, отличие только в отсутствии округления до одного знака

## 11. manufacturing/mfg2-032 en/0

ловушка: the shift belongs to the line, not to the movement, so it is one step further away; the price is joined on a range, and a plain join on part_id multiplies every movement by its number of price windows; the quantity has to be converted before it is multiplied by the price
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT s.title AS shift, ROUND(SUM(m.qty * u.to_base * pp.minor / 100.0), 2) AS value FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN line l ON l.id = m.line_id JOIN shift_ref s ON s.cd = l.shift_cd JOIN part_price pp ON pp.part_id = m.part_id AND pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at)) GROUP BY s.title ORDER BY value DESC, s.title
    ('night', 16740230.61)
    ('day', 12228363.65)

ответ модели:
    SELECT 
    l.title AS line_title,
    s.title AS shift_title,
    p.title AS part_title,
    m.qty * ur.to_base AS value_moved,
    pp.minor AS price_in_force
FROM 
    mov m
JOIN 
    line l ON m.line_id = l.id
JOIN 
    shift_ref s ON l.shift_cd = s.cd
JOIN 
    part p ON m.part_id = p.id
JOIN 
    unit_ref ur ON m.unit_cd = ur.cd
JOIN 
    part_price pp ON p.id = pp.part_id
JOIN 
    grade_ref g ON d.grade_cd = g.cd
JOIN 
    defect d ON m.id = d.mov_id
WHERE 
    pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at))
ORDER BY 
    l.title, s.title, m.dt_op
    ('Assembly A', 'day', 'shaft', 399.0, 1659)
    ('Assembly A', 'day', 'shaft', 167.0, 1659)
    ('Assembly A', 'day', 'bracket', 171.0, 2120)
    ('Assembly A', 'day', 'plate', 233.0, 13363)
    ('Assembly A', 'day', 'bracket', 171.0, 2120)
    ('Assembly A', 'day', 'bushing', 328.0, 4922)
    ('Assembly A', 'day', 'shaft', 374.0, 1452)
    ('Assembly A', 'day', 'shaft', 149.0, 1452)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: вернул построчную детализацию вместо двух итогов по сменам

## 12. medicine/med2-032 en/1

ловушка: how many departments exist is a fact of doc, not a number to hard-code; the department belongs to the doctor, so it is one step beyond the encounter
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT e.pat_id FROM enc e JOIN doc d ON d.id = e.doc_id GROUP BY e.pat_id HAVING COUNT(DISTINCT d.dept) = (SELECT COUNT(DISTINCT dept) FROM doc))
    (4,)

ответ модели:
    SELECT doc.dept, COUNT(DISTINCT enc.pat_id) AS patient_count
FROM enc
JOIN doc ON enc.doc_id = doc.id
GROUP BY doc.dept
    ('cardiology', 170)
    ('endocrinology', 160)
    ('neurology', 116)
    ('oncology', 139)
    ('surgery', 132)

ошибка исполнения: нет

вердикт: model
заметка: вернул число пациентов по каждому отделению вместо тех, кто был во всех

## 13. medicine/med2-042 en/0

ловушка: the route is a code, its name lives in route_ref; the length of stay is a difference of two text dates and needs julianday; the share counts the qualifying rows against all rows of the group, so the condition goes inside the aggregate
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS route, ROUND(100.0 * SUM(CASE WHEN x.days > julianday(e.discharged) - julianday(COALESCE(e.dt_adm, e.admitted_at)) THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct FROM rx x JOIN route_ref r ON r.cd = x.route_cd JOIN enc e ON e.id = x.enc_id WHERE e.discharged IS NOT NULL GROUP BY r.title ORDER BY pct DESC, r.title
    ('intravenous', 70.24)
    ('inhalation', 62.98)
    ('topical', 61.89)
    ('oral', 56.67)

ответ модели:
    SELECT 
    rr.title AS route_of_administration,
    ROUND(SUM(CASE WHEN rx.days > (julianday(enc.discharged) - julianday(enc.dt_adm)) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS percentage
FROM 
    rx
JOIN 
    enc ON rx.enc_id = enc.id
JOIN 
    route_ref rr ON rx.route_cd = rr.cd
GROUP BY 
    rr.title
    ('inhalation', 12.5)
    ('intravenous', 15.53)
    ('oral', 12.03)
    ('topical', 12.53)

ошибка исполнения: нет

вердикт: model
заметка: потерян COALESCE на дату поступления и отбор по выписанным

## 14. public_services/gov2-004 en/1

ловушка: the filter has to be strict here, because a case closed on the due date is not late and would pull the average towards zero
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(julianday(closed_at) - julianday(due_dt)), 1) AS days FROM case_rec WHERE closed_at > due_dt
    (21.0,)

ответ модели:
    SELECT AVG(julianday(COALESCE(closed_at, CURRENT_DATE)) - julianday(due_dt)) AS mean_days_past_due
FROM case_rec
WHERE COALESCE(closed_at, CURRENT_DATE) > due_dt
    (92.032,)

ошибка исполнения: нет

вердикт: model
заметка: подставляет сегодняшнюю дату незакрытым делам, 92.0 против 21.0

## 15. public_services/gov2-007 en/0

ловушка: an unfinished case has no closing date, so lateness has to be measured against the given date and not against closed_at
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec WHERE closed_at IS NULL AND due_dt < '2026-11-02'
    (73,)

ответ модели:
    SELECT COUNT(*) 
FROM case_rec 
WHERE COALESCE(dt_sub, submitted_at) <= '2026-11-02' 
  AND due_dt < '2026-11-02' 
  AND id NOT IN (SELECT case_id FROM stage WHERE result_cd IN (1, 2, 3))
    (155,)

ошибка исполнения: нет

вердикт: model
заметка: определяет незавершённость по этапам, а не по дате закрытия, 155 против 73

## 16. public_services/gov2-026 en/0

ловушка: stage joined twice to itself, with the order given by seq rather than by id; an undecided stage is NULL in result_cd, which no equality test matches; two such pairs on one case must not count it twice
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(DISTINCT a.case_id) AS n FROM stage a JOIN stage b ON b.case_id = a.case_id AND b.seq > a.seq WHERE a.result_cd IS NULL AND b.result_cd IS NOT NULL
    (135,)

ответ модели:
    SELECT COUNT(*) AS undecided_cases
FROM (
    SELECT c.id AS case_id,
           MAX(s1.seq) AS max_undecided_seq
    FROM case_rec c
    JOIN stage s1 ON c.id = s1.case_id
    LEFT JOIN stage s2 ON c.id = s2.case_id AND s2.seq > s1.seq
    WHERE s2.result_cd IS NULL
    GROUP BY c.id
    HAVING COUNT(DISTINCT s1.result_cd) > 1
) AS undecided_cases
    (51,)

ошибка исполнения: нет

вердикт: model
заметка: считает не те пары этапов, 51 против 135

## 17. public_services/gov2-026 en/1

ловушка: stage joined twice to itself, with the order given by seq rather than by id; an undecided stage is NULL in result_cd, which no equality test matches; two such pairs on one case must not count it twice
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(DISTINCT a.case_id) AS n FROM stage a JOIN stage b ON b.case_id = a.case_id AND b.seq > a.seq WHERE a.result_cd IS NULL AND b.result_cd IS NOT NULL
    (135,)

ответ модели:
    SELECT COUNT(*)
FROM case_rec AS cr
JOIN stage AS s1 ON cr.id = s1.case_id
JOIN stage AS s2 ON cr.id = s2.case_id
WHERE s1.result_cd = 0 AND s2.result_cd IN (1, 2, 3) AND s1.seq < s2.seq
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: ищет нерешённый этап как result_cd = 0, а там NULL, ответ 0

## 18. public_services/gov2-028 en/1

ловушка: the deadline is inclusive, so landing on it is neither late nor early and both strict comparisons miss this group; the share counts the qualifying rows against all rows of the group, so the condition goes inside the aggregate
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title, ROUND(100.0 * SUM(CASE WHEN c.closed_at = c.due_dt THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL GROUP BY sv.title ORDER BY pct DESC, sv.title
    ('building permit', 12.21)
    ('trading licence', 12.16)
    ('business registration', 10.0)
    ('land record extract', 8.02)
    ('residence certificate', 4.46)

ответ модели:
    SELECT 
    s.title AS service_title,
    ROUND(SUM(CASE WHEN cr.closed_at = cr.due_dt THEN 1 ELSE 0 END) * 100.0 / COUNT(cr.id), 2) AS percentage_on_time
FROM 
    service s
JOIN 
    case_rec cr ON s.id = cr.service_id
GROUP BY 
    s.title
    ('building permit', 10.74)
    ('business registration', 9.03)
    ('land record extract', 7.1)
    ('residence certificate', 3.85)
    ('trading licence', 11.69)

ошибка исполнения: нет

вердикт: model
заметка: в знаменателе все дела, а не только закрытые

## 19. public_services/gov2-030 en/0

ловушка: how many regions exist is a fact of region_ref, not a number to hard-code; the region is one step beyond the office, which is itself one step beyond the case
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT c.applicant_id FROM case_rec c JOIN office o ON o.id = c.office_id GROUP BY c.applicant_id HAVING COUNT(DISTINCT o.region_cd) = (SELECT COUNT(*) FROM region_ref))
    (21,)

ответ модели:
    SELECT r.title AS region, COUNT(DISTINCT a.id) AS applicant_count
FROM region_ref r
JOIN office o ON r.cd = o.region_cd
JOIN case_rec c ON o.id = c.office_id
JOIN applicant a ON c.applicant_id = a.id
GROUP BY r.title
    ('Eastvale', 114)
    ('Marden', 116)
    ('Northport', 176)
    ('Thorne', 108)

ошибка исполнения: нет

вердикт: model
заметка: вернул разрез по регионам вместо числа заявителей, подавших во всех

## 20. public_services/gov2-040 en/0

ловушка: case_rec joined twice to itself, with the pair taken once by comparing ids; the submission date is split across the legacy pair, so the equality is between two coalesced expressions
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec a JOIN case_rec b ON b.applicant_id = a.applicant_id AND b.id > a.id AND COALESCE(a.dt_sub, a.submitted_at) = COALESCE(b.dt_sub, b.submitted_at) WHERE a.service_id <> b.service_id
    (3,)

ответ модели:
    SELECT COUNT(*) AS count
FROM (
    SELECT applicant_id, dt_sub, COUNT(DISTINCT service_id) AS service_count
    FROM case_rec
    GROUP BY applicant_id, dt_sub
    HAVING service_count > 1
) AS subquery
    (129,)

ошибка исполнения: нет

вердикт: model
заметка: группирует по dt_sub без COALESCE и считает заявителей, а не пары дел
