# Ручной разбор провалов: qwen25-coder-14b.set2-app-ru.jsonl

Провалов всего: 296 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-033 ru/1

ловушка: pending is status_cd = 0, and a zero code is a real state and not a missing value; the question is about accounts, so the transactions must not multiply the count
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(DISTINCT a.id) AS n FROM acct a WHERE a.status_cd = 0 AND EXISTS (SELECT 1 FROM txn t WHERE t.acct_id = a.id)
    (31,)

ответ модели:
    SELECT a.id
FROM acct a
JOIN txn t ON a.id = t.acct_id
WHERE a.status_cd = 0
    (27,)
    (486,)
    (35,)
    (527,)
    (343,)
    (281,)
    (124,)
    (409,)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: вернул список счетов вместо их количества

## 2. hr/hr2-008 ru/0

ловушка: one level of hierarchy has to be followed through parent_id; the name has to be resolved to an id before the hierarchy can be used
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT e.full_name FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 AND (d.title = 'Engineering' OR d.parent_id = (SELECT id FROM dept WHERE title = 'Engineering')) ORDER BY e.full_name
    ('Alina Bauer',)
    ('Alina Hale',)
    ('Alina Oduya',)
    ('Alina Oduya',)
    ('Alina Oduya',)
    ('Alina Petran',)
    ('Anna Bauer',)
    ('Anna Kristof',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT e.full_name
FROM emp e
JOIN dept d ON e.dept_id = d.id
WHERE d.title = 'Engineering' OR d.parent_id = 2
    ('Nina Varga',)
    ('Anna Kovach',)
    ('Boris Almeida',)
    ('Sofia Kovach',)
    ('Sofia Soto',)
    ('Pavel Varga',)
    ('Victor Oduya',)
    ('Mark Novak',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: подразделение зашито числом 2 и нет отбора по работающим

## 3. hr/hr2-010 ru/0

ловушка: the same table twice, with a different status condition on each alias
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT e.full_name AS employee, m.full_name AS manager FROM emp e JOIN emp m ON m.id = e.mgr_id WHERE e.status_cd = 1 AND m.status_cd = 3 ORDER BY e.full_name
    ('Alina Kovach', 'Boris Linde')
    ('Alina Oduya', 'Anna Kovach')
    ('Anna Almeida', 'Daniel Petran')
    ('Anna Bauer', 'Pavel Varga')
    ('Anna Linde', 'Vera Soto')
    ('Anna Reiner', 'Boris Hale')
    ('Artem Hale', 'Daniel Kovach')
    ('Artem Marek', 'Mark Novak')
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT e.full_name
FROM emp e
JOIN emp_status_ref esr ON e.status_cd = esr.cd
WHERE esr.title = 'working'
AND e.mgr_id IN (
    SELECT id
    FROM emp
    WHERE status_cd = 3
)
    ('Olga Novak',)
    ('Olga Varga',)
    ('Olga Petran',)
    ('Alina Oduya',)
    ('Anna Almeida',)
    ('Nina Novak',)
    ('Anna Bauer',)
    ('Igor Novak',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: те же 41 сотрудник, проверил запросом; в эталоне лишний столбец с руководителем, которого вопрос не просил

## 4. hr/hr2-030 ru/1

ловушка: consecutive means the nearest later date for that person, which is a correlated minimum; amounts are minor units and must be divided by 100
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(MAX(b.amount_minor - a.amount_minor) / 100.0, 2) AS rise FROM pay_hist a JOIN pay_hist b ON b.emp_id = a.emp_id AND b.from_dt = (SELECT MIN(x.from_dt) FROM pay_hist x WHERE x.emp_id = a.emp_id AND x.from_dt > a.from_dt)
    (8094.0,)

ответ модели:
    SELECT MAX(ROUND((MAX(amount_minor) - MIN(amount_minor)) / 100.0, 2)) AS max_step
FROM (
    SELECT emp_id, amount_minor
    FROM pay_hist
    GROUP BY emp_id
    HAVING COUNT(*) > 1
) AS subquery
    ОШИБКА: OperationalError: misuse of aggregate function MIN()

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: MIN внутри MAX, misuse of aggregate

## 5. hr/hr2-038 ru/0

ловушка: dept joined twice to itself, and COALESCE on the parent is what rolls a sub-department up to its top; the salary in force is the latest from_dt per person, so a plain join multiplies the total by the number of revisions; the currencies must not be added together, so the euro rows are the only ones that count
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT top.title, SUM(p.amount_minor) / 100.0 AS payroll FROM emp e JOIN dept d ON d.id = e.dept_id JOIN dept top ON top.id = COALESCE(d.parent_id, d.id) JOIN pay_hist p ON p.emp_id = e.id WHERE e.status_cd = 1 AND p.cur_cd = 1 AND p.from_dt = (SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id) GROUP BY top.title ORDER BY payroll DESC, top.title
    ('Engineering', 357940.0)
    ('Operations', 254790.0)
    ('Finance', 181600.0)

ответ модели:
    SELECT 
    d.title AS parent_dept_title,
    SUM(p.amount_minor / 100.0) AS total_paid_in_eur
FROM 
    emp e
JOIN 
    dept d ON e.dept_id = d.id
JOIN 
    pay_hist p ON e.id = p.emp_id
JOIN 
    cur_ref c ON p.cur_cd = c.cd
WHERE 
    c.title = 'EUR'
    AND d.parent_id IS NOT NULL
GROUP BY 
    d.parent_id, d.title
    ('Support', 533768.0)
    ('Data', 827645.0)
    ('Platform', 508526.0)

ошибка исполнения: нет

вердикт: model
заметка: группирует по подчинённым отделам вместо верхних, суммы втрое больше

## 6. logistics/log2-031 ru/0

ловушка: the mode is a property of the carrier, so it is two steps away from the leg; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT l.shp_id FROM leg l JOIN carr c ON c.id = l.carr_id GROUP BY l.shp_id HAVING COUNT(DISTINCT c.mode_cd) > 1)
    (434,)

ответ модели:
    SELECT COUNT(*) 
FROM (
    SELECT shp_id 
    FROM leg 
    GROUP BY shp_id 
    HAVING COUNT(DISTINCT carr_id) > 1
)
    (502,)

ошибка исполнения: нет

вердикт: model
заметка: считает разных перевозчиков вместо видов транспорта, 502 против 434

## 7. logistics/log2-044 ru/1

ловушка: the cost is a sum over legs while the weight is a single column of the shipment; an integer division returns zero here, the ratio has to be taken in floating point; the question asks which, so the ratio is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT s.id FROM shp s JOIN leg l ON l.shp_id = s.id GROUP BY s.id, s.weight_kg ORDER BY SUM(l.cost_cents) * 1.0 / s.weight_kg DESC, s.id LIMIT 1
    (271,)

ответ модели:
    SELECT shp.id AS shipment_id, 
       SUM(leg.cost_cents / 100.0) / shp.weight_kg AS cost_per_kg
FROM shp
JOIN leg ON shp.id = leg.shp_id
GROUP BY shp.id
ORDER BY cost_per_kg DESC
LIMIT 1
    (271, 298.9952272727273)

ошибка исполнения: нет

вердикт: evaluator
заметка: та же перевозка 271, но рядом выведено само отношение, которого вопрос не просил

## 8. manufacturing/mfg2-001 ru/0

ловушка: the quantities are in three units, so the only honest total is one per unit; a single SUM adds tonnes to pieces
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT u.title AS unit, SUM(m.qty) AS total FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd GROUP BY u.title ORDER BY u.title
    ('kilogram', 66543.0)
    ('piece', 91727.0)
    ('tonne', 610.6)

ответ модели:
    SELECT 
    mov.unit_cd, 
    unit_ref.title AS unit_title, 
    SUM(mov.qty) AS total_qty
FROM 
    mov
JOIN 
    unit_ref ON mov.unit_cd = unit_ref.cd
GROUP BY 
    mov.unit_cd, unit_ref.title
    (1, 'piece', 91727.0)
    (2, 'kilogram', 66543.0)
    (3, 'tonne', 610.6)

ошибка исполнения: нет

вердикт: evaluator
заметка: те же три итога по единицам, добавлен столбец с кодом единицы

## 9. manufacturing/mfg2-008 ru/0

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
    SUM(pp.minor * d.qty) AS defect_cost
FROM 
    defect d
JOIN 
    mov m ON d.mov_id = m.id
JOIN 
    part p ON m.part_id = p.id
JOIN 
    part_price pp ON p.id = pp.part_id
WHERE 
    pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) 
    AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at))
GROUP BY 
    p.title
    ОШИБКА: OperationalError: no such column: d.qty

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к несуществующей колонке d.qty

## 10. manufacturing/mfg2-017 ru/0

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
    ROUND(SUM(CASE WHEN d.grade_cd IS NOT NULL THEN m.qty * ur.to_base ELSE 0 END) * 100.0 / SUM(m.qty * ur.to_base), 1) AS defect_percentage
FROM 
    mov m
JOIN 
    part p ON m.part_id = p.id
JOIN 
    unit_ref ur ON m.unit_cd = ur.cd
LEFT JOIN 
    defect d ON m.id = d.mov_id
GROUP BY 
    p.title
    ('bracket', 31.6)
    ('bushing', 22.5)
    ('gearwheel', 30.4)
    ('plate', 16.6)
    ('shaft', 27.9)
    ('spring', 13.9)

ошибка исполнения: нет

вердикт: model
заметка: считает брак по наличию дефекта вместо вида движения, 31.6 против 15.2

## 11. manufacturing/mfg2-018 ru/1

ловушка: the comparison has to happen after the conversion, not on qty; a row in pieces has no weight and cannot qualify
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT m.id, p.title AS part, l.title AS line, m.qty * u.to_base AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id JOIN line l ON l.id = m.line_id WHERE u.title IN ('kilogram', 'tonne') AND m.qty * u.to_base > 1000 ORDER BY base_qty DESC, m.id
    (719, 'gearwheel', 'Finishing', 11870.0)
    (523, 'plate', 'Assembly A', 11850.0)
    (13, 'bracket', 'Finishing', 11670.0)
    (209, 'plate', 'Finishing', 11600.0)
    (245, 'bracket', 'Machining', 11590.0)
    (763, 'bushing', 'Finishing', 11490.0)
    (784, 'bracket', 'Assembly A', 11430.0)
    (671, 'plate', 'Assembly B', 11280.0)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT 
    m.id AS mov_id,
    p.title AS part_title,
    l.title AS line_title,
    COALESCE(m.dt_op, m.recorded_at) AS operation_date,
    m.qty * ur.to_base AS total_weight_kg
FROM 
    mov m
JOIN 
    part p ON m.part_id = p.id
JOIN 
    line l ON m.line_id = l.id
JOIN 
    unit_ref ur ON m.unit_cd = ur.cd
WHERE 
    m.qty * ur.to_base > 1000
    (5, 'shaft', 'Finishing', '2025-12-04', 8640.0)
    (13, 'bracket', 'Finishing', '2026-08-18', 11670.0)
    (17, 'bracket', 'Assembly B', '2024-04-29', 9950.0)
    (19, 'shaft', 'Machining', '2025-09-17', 7110.0)
    (24, 'bracket', 'Assembly B', '2025-04-03', 9130.0)
    (25, 'bushing', 'Machining', '2023-11-10', 7420.0)
    (28, 'gearwheel', 'Finishing', '2024-06-19', 3570.0)
    (35, 'bracket', 'Assembly B', '2024-11-28', 8360.0)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: нет отбора по весовым единицам, в выдачу попали штуки, и добавлен столбец с датой

## 12. manufacturing/mfg2-036 ru/1

ловушка: a defect found before its movement would drag the average down and the question excludes it; the movement date is split across the legacy pair dt_op/recorded_at; the grade is a code, its name lives in grade_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT g.title AS grade, ROUND(AVG(julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at))), 2) AS days FROM defect d JOIN mov m ON m.id = d.mov_id JOIN grade_ref g ON g.cd = d.grade_cd WHERE d.found_at >= COALESCE(m.dt_op, m.recorded_at) GROUP BY g.title ORDER BY days DESC, g.title
    ('major', 479.17)
    ('minor', 385.42)
    ('critical', 324.8)

ответ модели:
    SELECT 
    g.title AS grade_title,
    AVG(julianday(d.found_at) - julianday(m.dt_op)) AS avg_days_to_defect
FROM 
    defect d
JOIN 
    mov m ON d.mov_id = m.id
JOIN 
    grade_ref g ON d.grade_cd = g.cd
WHERE 
    d.found_at > m.dt_op
GROUP BY 
    g.title
    ('critical', 344.0)
    ('major', 503.68)
    ('minor', 411.8958333333333)

ошибка исполнения: нет

вердикт: model
заметка: без COALESCE на дату движения, 503.68 против 479.17

## 13. manufacturing/mfg2-045 ru/1

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
    p.id AS part_id,
    p.code AS part_code,
    pp.minor AS price
FROM 
    part p
JOIN 
    mov m ON p.id = m.part_id
JOIN 
    part_price pp ON p.id = pp.part_id
WHERE 
    pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) 
    AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at))
GROUP BY 
    p.id, p.code, pp.minor
ORDER BY 
    p.id
    (1, 'BR-100', 1486)
    (1, 'BR-100', 1749)
    (1, 'BR-100', 1889)
    (1, 'BR-100', 2120)
    (2, 'SH-210', 1132)
    (2, 'SH-210', 1292)
    (2, 'SH-210', 1452)
    (2, 'SH-210', 1659)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: вернул все ценовые окна, а не то, что накрывает первое движение, и цену в копейках

## 14. medicine/med2-012 ru/0

ловушка: HAVING on a filtered count, not WHERE; the filter on primary_flag has to apply before the count, not after
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT e.id, COUNT(*) AS n FROM enc e JOIN dx d ON d.enc_id = e.id WHERE d.primary_flag = 1 GROUP BY e.id HAVING COUNT(*) > 1 ORDER BY n DESC, e.id
    (189, 6)
    (246, 4)
    (279, 4)
    (301, 4)
    (370, 4)
    (419, 4)
    (610, 4)
    (618, 4)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT enc_id
FROM dx
WHERE primary_flag = 1
GROUP BY enc_id
HAVING COUNT(*) > 1
    (1,)
    (3,)
    (11,)
    (17,)
    (20,)
    (25,)
    (26,)
    (27,)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: те же 189 случаев, проверил запросом; в эталоне лишний столбец с числом диагнозов

## 15. medicine/med2-026 ru/0

ловушка: cancelled is status_cd = 3, a code and not a word; two conditions of opposite sign on the same table, and dropping either one changes the set; a patient with no encounter at all must not be counted among them
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.full_name FROM pat p WHERE EXISTS (SELECT 1 FROM enc e WHERE e.pat_id = p.id) AND NOT EXISTS (SELECT 1 FROM enc e WHERE e.pat_id = p.id AND e.status_cd <> 3) ORDER BY p.full_name
    ('Anna Reiner',)
    ('Anna Soto',)
    ('Boris Linde',)
    ('Elena Marek',)
    ('Elena Reiner',)
    ('Igor Kovach',)
    ('Pavel Marek',)
    ('Victor Novak',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT p.full_name
FROM pat p
JOIN enc e ON p.id = e.pat_id
WHERE e.status_cd = 3
GROUP BY p.id
HAVING COUNT(e.id) = COUNT(CASE WHEN e.status_cd = 3 THEN 1 END)
    ('Elena Marek',)
    ('Irina Marek',)
    ('Olga Bauer',)
    ('Timur Benali',)
    ('Nina Oduya',)
    ('Nina Almeida',)
    ('Nina Oduya',)
    ('Nina Kovach',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: HAVING после отбора по отменённым всегда истинно, попали пациенты с любой отменой

## 16. public_services/gov2-003 ru/1

ловушка: the denominator is the closed cases only; the unfinished ones cannot be late yet and must not dilute the share; a percentage needs 100.0, because integer division returns zero
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title, ROUND(100.0 * SUM(CASE WHEN c.closed_at > c.due_dt THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL GROUP BY sv.title ORDER BY pct DESC, sv.title
    ('land record extract', 33.3)
    ('trading licence', 27.7)
    ('residence certificate', 24.1)
    ('business registration', 21.5)
    ('building permit', 20.6)

ответ модели:
    SELECT 
    s.title AS service_title,
    (COUNT(CASE WHEN julianday(c.closed_at) > julianday(c.due_dt) THEN 1 END) * 100.0 / COUNT(*)) AS overdue_percentage
FROM 
    service s
JOIN 
    case_rec c ON s.id = c.service_id
JOIN 
    stage st ON c.id = st.case_id
WHERE 
    st.result_cd = 1
GROUP BY 
    s.title
    ('building permit', 20.833333333333332)
    ('business registration', 18.75)
    ('land record extract', 26.53061224489796)
    ('residence certificate', 20.930232558139537)
    ('trading licence', 22.29299363057325)

ошибка исполнения: нет

вердикт: model
заметка: присоединяет этапы и считает долю не от завершённых дел

## 17. public_services/gov2-005 ru/1

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
    AVG(julianday(c.closed_at) - julianday(COALESCE(c.dt_sub, c.submitted_at))) AS avg_days
FROM 
    case_rec c
JOIN 
    service s ON c.service_id = s.id
JOIN 
    stage st ON c.id = st.case_id
WHERE 
    st.result_cd = 1  -- Only consider approved cases
GROUP BY 
    s.title
    ('building permit', 27.442622950819672)
    ('business registration', 10.232876712328768)
    ('land record extract', 10.30813953488372)
    ('residence certificate', 12.160714285714286)
    ('trading licence', 18.433333333333334)

ошибка исполнения: нет

вердикт: model
заметка: отбирает по результату этапа вместо наличия даты закрытия

## 18. public_services/gov2-019 ru/1

ловушка: 'refused' is a word in result_ref, and the service is two joins away from the stage
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title, COUNT(*) AS n FROM stage s JOIN case_rec c ON c.id = s.case_id JOIN service sv ON sv.id = c.service_id JOIN result_ref r ON r.cd = s.result_cd WHERE r.title = 'refused' GROUP BY sv.title ORDER BY n DESC, sv.title
    ('building permit', 61)
    ('trading licence', 57)
    ('land record extract', 55)
    ('business registration', 49)
    ('residence certificate', 39)

ответ модели:
    SELECT 
    s.case_id,
    sr.title AS service_title,
    COUNT(*) AS refused_count
FROM 
    stage s
JOIN 
    case_rec cr ON s.case_id = cr.id
JOIN 
    service sr ON cr.service_id = sr.id
WHERE 
    s.result_cd = 2
GROUP BY 
    s.case_id, sr.title
    (6, 'building permit', 2)
    (7, 'land record extract', 1)
    (8, 'residence certificate', 1)
    (9, 'building permit', 1)
    (10, 'residence certificate', 1)
    (16, 'residence certificate', 1)
    (18, 'building permit', 1)
    (19, 'land record extract', 2)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: группирует ещё и по делу, и берёт код 2 вместо результата refused

## 19. public_services/gov2-026 ru/1

ловушка: stage joined twice to itself, with the order given by seq rather than by id; an undecided stage is NULL in result_cd, which no equality test matches; two such pairs on one case must not count it twice
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(DISTINCT a.case_id) AS n FROM stage a JOIN stage b ON b.case_id = a.case_id AND b.seq > a.seq WHERE a.result_cd IS NULL AND b.result_cd IS NOT NULL
    (135,)

ответ модели:
    SELECT COUNT(*)
FROM (
    SELECT c.id AS case_id,
           s1.seq AS no_result_seq,
           s2.seq AS with_result_seq
    FROM case_rec c
    JOIN stage s1 ON c.id = s1.case_id
    JOIN stage s2 ON c.id = s2.case_id
    WHERE s1.result_cd IS NULL
      AND s2.result_cd IS NOT NULL
      AND s1.seq < s2.seq
) AS subquery
    (268,)

ошибка исполнения: нет

вердикт: model
заметка: считает пары этапов, а не дела, 268 против 135

## 20. public_services/gov2-034 ru/0

ловушка: the last stage is the largest seq of that case, which is a correlated subquery; an undecided stage is NULL in result_cd, which no equality test matches; the stage and the case disagree in the direction opposite to the previous question
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM stage s JOIN case_rec c ON c.id = s.case_id WHERE s.seq = (SELECT MAX(s2.seq) FROM stage s2 WHERE s2.case_id = s.case_id) AND s.result_cd IS NULL AND c.closed_at IS NOT NULL
    (116,)

ответ модели:
    SELECT COUNT(*) 
FROM case_rec cr
LEFT JOIN stage s ON cr.id = s.case_id
WHERE cr.closed_at IS NOT NULL AND s.result_cd IS NULL
    (390,)

ошибка исполнения: нет

вердикт: model
заметка: берёт любой нерешённый этап, а не последний, 390 против 116
