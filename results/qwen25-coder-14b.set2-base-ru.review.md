# Ручной разбор провалов: qwen25-coder-14b.set2-base-ru.jsonl

Провалов всего: 398 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-017 ru/1

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
    COUNT(*) AS txn_count
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
заметка: только dt_op без COALESCE, выдача пустая

## 2. banking/bank2-040 ru/1

ловушка: spending is dir_cd = 1, and the denominator has to carry the same condition as the numerator; the merchant group lives in mcc_ref, the code on txn is not an answer; an integer division returns zero here, the ratio has to be taken in floating point
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT m.grp, ROUND(100.0 * SUM(t.amt_cents) / (SELECT SUM(amt_cents) FROM txn WHERE dir_cd = 1), 2) AS pct FROM txn t JOIN mcc_ref m ON m.code = t.mcc WHERE t.dir_cd = 1 GROUP BY m.grp ORDER BY pct DESC, m.grp
    ('hospitality', 26.33)
    ('retail', 25.38)
    ('health', 13.24)
    ('cash', 11.93)
    ('utilities', 11.65)
    ('travel', 11.46)

ответ модели:
    SELECT 
    mcc_ref.grp AS group_title,
    SUM(CASE WHEN txn.dir_cd = 'D' THEN txn.amt_cents ELSE 0 END) AS total_spent,
    ROUND(SUM(CASE WHEN txn.dir_cd = 'D' THEN txn.amt_cents ELSE 0 END) * 100.0 / 
         (SELECT SUM(CASE WHEN txn.dir_cd = 'D' THEN txn.amt_cents ELSE 0 END) FROM txn), 2) AS percentage
FROM 
    txn
JOIN 
    mcc_ref ON txn.mcc = mcc_ref.code
GROUP BY 
    mcc_ref.grp
ORDER BY 
    total_spent DESC
    ('utilities', 0, None)
    ('travel', 0, None)
    ('retail', 0, None)
    ('hospitality', 0, None)
    ('health', 0, None)
    ('cash', 0, None)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает код направления с буквой D, все суммы нулевые

## 3. hr/hr2-008 ru/0

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
WHERE d.title = 'Engineering' OR d.parent_id IN (
    SELECT id FROM dept WHERE title = 'Engineering'
)
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
заметка: нет отбора по работающим, набор другой

## 4. hr/hr2-041 ru/0

ловушка: the earliest date is per department, which makes the subquery correlated; the same condition on the status has to hold inside the subquery as outside it; the answer is a person, so the minimum cannot simply be selected on its own
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title AS department, e.full_name FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 AND e.hired_at = (SELECT MIN(e2.hired_at) FROM emp e2 WHERE e2.dept_id = e.dept_id AND e2.status_cd = 1) ORDER BY d.title, e.full_name
    ('Data', 'Irina Soto')
    ('Engineering', 'Alina Oduya')
    ('Finance', 'Pavel Soto')
    ('Operations', 'Boris Kristof')
    ('Platform', 'Boris Almeida')
    ('Support', 'Sofia Hale')

ответ модели:
    SELECT d.title AS department_title, e.full_name AS employee_name
FROM dept d
JOIN emp e ON d.id = e.dept_id
WHERE e.status_cd = (SELECT cd FROM emp_status_ref WHERE title = 'Active')
AND e.hired_at = (
    SELECT MIN(hired_at)
    FROM emp
    WHERE dept_id = d.id AND status_cd = (SELECT cd FROM emp_status_ref WHERE title = 'Active')
)
ORDER BY d.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: статус ищется по названию Active, которого нет, выдача пустая

## 5. logistics/log2-003 ru/0

ловушка: delivered is status_cd = 2; a lost shipment can carry a delivery attempt date, so delivered_at IS NOT NULL is the wrong test and overcounts
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 2
    (502,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
WHERE status_cd = (SELECT cd FROM status_ref WHERE title = 'Delivered')
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: статус ищется по названию Delivered, которого нет, ответ 0

## 6. logistics/log2-005 ru/0

ловушка: cost is stored in minor units and must be divided by 100
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT SUM(cost_cents) / 100.0 AS total FROM leg
    (8733093.17,)

ответ модели:
    SELECT SUM(cost_cents) AS total_cost_cents
FROM leg
    (873309317,)

ошибка исполнения: нет

вердикт: model
заметка: копейки не переведены в денежные единицы

## 7. logistics/log2-018 ru/1

ловушка: the dispatch date is split across the legacy pair dt_disp/dispatched_at; delivered is the status, not the presence of a delivery date; dates are text, so the difference needs julianday
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(julianday(delivered_at) - julianday(COALESCE(dt_disp, dispatched_at))), 1) AS days FROM shp WHERE status_cd = 2
    (20.0,)

ответ модели:
    SELECT AVG(julianday(shp.delivered_at) - julianday(shp.dispatched_at)) AS avg_delivery_time_days
FROM shp
JOIN status_ref ON shp.status_cd = status_ref.cd
WHERE status_ref.title = 'Delivered'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: без COALESCE на дату отправки, результат None

## 8. logistics/log2-028 ru/1

ловушка: anti-join through a second table: the status is on the shipment, not on the leg; lost is status_cd = 3, a code and not a word
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT c.title FROM carr c WHERE NOT EXISTS ( SELECT 1 FROM leg l JOIN shp s ON s.id = l.shp_id WHERE l.carr_id = c.id AND s.status_cd = 3) ORDER BY c.title
    ('Bauer Haulage',)
    ('Hale Transit',)
    ('Kristof Logistics',)
    ('Marek Logistics',)
    ('Petran Haulage',)

ответ модели:
    SELECT c.title
FROM carr c
WHERE c.id NOT IN (
    SELECT l.carr_id
    FROM leg l
    JOIN status_ref sr ON l.status_cd = sr.cd
    WHERE sr.title = 'Lost'
)
    ОШИБКА: OperationalError: no such column: l.status_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к leg.status_cd, которого нет

## 9. logistics/log2-047 ru/1

ловушка: the difference between two text dates needs julianday, subtraction returns nonsense; the dispatch date is split across the legacy pair dt_disp/dispatched_at; only delivered shipments have both dates, and a lost one with a date would spoil the average
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.country, ROUND(AVG(julianday(s.delivered_at) - julianday(COALESCE(s.dt_disp, s.dispatched_at))), 2) AS days FROM shp s JOIN loc_ref d ON d.cd = s.dst_cd WHERE s.status_cd = 2 GROUP BY d.country ORDER BY days DESC, d.country
    ('Breland', 20.95)
    ('Dornia', 20.14)
    ('Cavira', 19.43)
    ('Aldoria', 19.37)

ответ модели:
    SELECT 
    l.country, 
    ROUND(AVG(julianday(s.delivered_at) - julianday(s.dispatched_at)), 2) AS avg_days
FROM 
    shp s
JOIN 
    loc_ref l ON s.dst_cd = l.cd
GROUP BY 
    l.country
    ('Aldoria', 19.98)
    ('Breland', 21.41)
    ('Cavira', 20.01)
    ('Dornia', 20.64)

ошибка исполнения: нет

вердикт: model
заметка: нет отбора по доставленным и нет COALESCE, значения другие

## 10. manufacturing/mfg2-007 ru/0

ловушка: the price table joined to itself under two aliases, each picked by a different rule; a percentage needs 100.0, because integer division returns zero
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, ROUND(100.0 * (last.minor - first.minor) / first.minor, 1) AS pct FROM part p JOIN part_price last ON last.part_id = p.id AND last.valid_to IS NULL JOIN part_price first ON first.part_id = p.id AND first.valid_from = ( SELECT MIN(p2.valid_from) FROM part_price p2 WHERE p2.part_id = p.id ) ORDER BY pct DESC, p.code
    ('PL-330', 51.0)
    ('SP-660', 46.7)
    ('SH-210', 46.6)
    ('BR-100', 42.7)
    ('GR-440', 41.0)
    ('BU-550', 34.3)

ответ модели:
    SELECT 
    p.id AS part_id,
    p.title AS part_title,
    ROUND(((pp_last.minor - pp_first.minor) * 100.0 / pp_first.minor), 1) AS price_change_percent
FROM 
    part p
JOIN 
    part_price pp_first ON p.id = pp_first.part_id
JOIN 
    part_price pp_last ON p.id = pp_last.part_id
WHERE 
    pp_first.valid_from = (
        SELECT MIN(valid_from) 
        FROM part_price 
        WHERE part_id = p.id
    )
    AND pp_last.valid_to = (
        SELECT MAX(valid_to) 
        FROM part_price 
        WHERE part_id = p.id
    )
    (1, 'bracket', 27.1)
    (2, 'shaft', 28.3)
    (3, 'plate', 31.6)
    (4, 'gearwheel', 22.9)
    (5, 'bushing', 30.6)
    (6, 'spring', 24.7)

ошибка исполнения: нет

вердикт: model
заметка: последняя цена берётся по MAX(valid_to), а открытое окно имеет NULL, проценты другие

## 11. manufacturing/mfg2-012 ru/1

ловушка: critical is grade_cd = 3, a code; the part is reached through the movement, not from the defect
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, p.title, COUNT(*) AS n FROM defect d JOIN mov m ON m.id = d.mov_id JOIN part p ON p.id = m.part_id WHERE d.grade_cd = 3 GROUP BY p.id, p.code, p.title ORDER BY n DESC, p.code
    ('BR-100', 'bracket', 16)
    ('PL-330', 'plate', 10)
    ('SH-210', 'shaft', 10)
    ('GR-440', 'gearwheel', 2)
    ('BU-550', 'bushing', 1)

ответ модели:
    SELECT 
    p.code AS part_code,
    p.title AS part_title,
    COUNT(d.id) AS critical_defect_count
FROM 
    part p
JOIN 
    mov m ON p.id = m.part_id
JOIN 
    defect d ON m.id = d.mov_id
JOIN 
    grade_ref g ON d.grade_cd = g.cd
WHERE 
    g.title = 'критический'
GROUP BY 
    p.id, p.code, p.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: ищет степень по русскому названию, в справочнике они английские, выдача пустая

## 12. manufacturing/mfg2-017 ru/0

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
    part p
JOIN 
    mov m ON p.id = m.part_id
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

## 13. manufacturing/mfg2-034 ru/0

ловушка: the open window is the one with no valid_to, which no date comparison finds; the movement date is split across the legacy pair dt_op/recorded_at
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, COUNT(*) AS n FROM mov m JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id AND pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) WHERE pp.valid_to IS NULL GROUP BY p.code ORDER BY n DESC, p.code
    ('BR-100', 86)
    ('SH-210', 63)
    ('PL-330', 42)
    ('GR-440', 36)
    ('BU-550', 14)
    ('SP-660', 5)

ответ модели:
    SELECT 
    p.id AS part_id, 
    p.title AS part_title, 
    COUNT(m.id) AS open_price_window_movements
FROM 
    part p
JOIN 
    mov m ON p.id = m.part_id
JOIN 
    part_price pp ON p.id = pp.part_id
WHERE 
    m.dt_op BETWEEN pp.valid_from AND pp.valid_to
GROUP BY 
    p.id, p.title
    (1, 'bracket', 222)
    (2, 'shaft', 155)
    (3, 'plate', 108)
    (4, 'gearwheel', 73)
    (5, 'bushing', 43)
    (6, 'spring', 17)

ошибка исполнения: нет

вердикт: model
заметка: BETWEEN не находит открытое окно с NULL, числа втрое больше

## 14. manufacturing/mfg2-037 ru/0

ловушка: the threshold is a scalar subquery that has to convert the units as well; comparing the raw quantity adds pieces to tonnes and the answer looks plausible
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.qty * u.to_base > (SELECT AVG(m2.qty * u2.to_base) FROM mov m2 JOIN unit_ref u2 ON u2.cd = m2.unit_cd)
    (93,)

ответ модели:
    SELECT COUNT(*) 
FROM mov 
WHERE qty * to_base > (SELECT AVG(qty * to_base) FROM mov)
    ОШИБКА: OperationalError: no such column: to_base

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к to_base без присоединения справочника единиц

## 15. manufacturing/mfg2-042 ru/1

ловушка: the shift belongs to the line, not to the movement; the night shift is shift_cd = 2, a code and not a word; the question asks which, so the count is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title FROM mov m JOIN part p ON p.id = m.part_id JOIN line l ON l.id = m.line_id WHERE l.shift_cd = 2 GROUP BY p.title ORDER BY COUNT(*) DESC, p.title LIMIT 1
    ('bracket',)

ответ модели:
    SELECT p.title
FROM part p
JOIN mov m ON p.id = m.part_id
JOIN line l ON m.line_id = l.id
JOIN shift_ref sr ON l.shift_cd = sr.cd
WHERE sr.title = 'Ночная'
GROUP BY p.title
ORDER BY COUNT(m.id) DESC
LIMIT 1
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: ищет смену по русскому названию, выдача пустая

## 16. manufacturing/mfg2-044 ru/1

ловушка: two defects on one movement must not count it twice; the unit is a code, its name lives in unit_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT u.title AS unit, COUNT(DISTINCT m.id) AS movements FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN defect d ON d.mov_id = m.id GROUP BY u.title ORDER BY movements DESC, u.title
    ('piece', 100)
    ('kilogram', 76)
    ('tonne', 22)

ответ модели:
    SELECT p.id AS part_id, COUNT(DISTINCT m.id) AS distinct_defective_moves
FROM part p
JOIN mov m ON p.id = m.part_id
JOIN defect d ON m.id = d.mov_id
GROUP BY p.id
    (1, 66)
    (2, 51)
    (3, 37)
    (4, 26)
    (5, 14)
    (6, 4)

ошибка исполнения: нет

вердикт: model
заметка: группирует по детали вместо единицы измерения

## 17. medicine/med2-024 ru/1

ловушка: the question is about the migration itself, so the two columns must be counted apart instead of being merged with COALESCE; the status name comes from the lookup
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS status, SUM(CASE WHEN e.dt_adm IS NOT NULL THEN 1 ELSE 0 END) AS legacy_column, SUM(CASE WHEN e.admitted_at IS NOT NULL THEN 1 ELSE 0 END) AS new_column FROM enc e JOIN status_ref r ON r.cd = e.status_cd GROUP BY r.title ORDER BY r.title
    ('active', 45, 97)
    ('cancelled', 25, 45)
    ('discharged', 184, 434)
    ('planned', 16, 54)

ответ модели:
    SELECT 
    sr.title AS status_title,
    COUNT(CASE WHEN e.dt_adm = e.admitted_at THEN 1 END) AS cases_with_dt_adm_equal_admitted_at,
    COUNT(CASE WHEN e.dt_adm <> e.admitted_at THEN 1 END) AS cases_with_dt_adm_not_equal_admitted_at
FROM 
    enc e
JOIN 
    status_ref sr ON e.status_cd = sr.cd
GROUP BY 
    sr.title
    ('active', 0, 0)
    ('cancelled', 0, 0)
    ('discharged', 0, 0)
    ('planned', 0, 0)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает две колонки между собой вместо подсчёта непустых в каждой

## 18. medicine/med2-034 ru/1

ловушка: the age is counted at the admission date, not at today's date; the admission date is split across the legacy pair dt_adm/admitted_at; dt_b is a text date, so the age needs julianday and a division by 365.25
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM enc e JOIN pat p ON p.id = e.pat_id WHERE (julianday(COALESCE(e.dt_adm, e.admitted_at)) - julianday(p.dt_b)) / 365.25 > 80
    (81,)

ответ модели:
    SELECT COUNT(*) AS admissions_count
FROM enc
JOIN pat ON enc.pat_id = pat.id
WHERE enc.dt_adm >= DATE_ADD(pat.dt_b, INTERVAL 80 YEAR)
    ОШИБКА: OperationalError: near "80": syntax error

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: вызывает DATE_ADD с INTERVAL, синтаксиса нет в SQLite

## 19. public_services/gov2-039 ru/1

ловушка: the share is of two aggregates over the same group, and the numerator carries two conditions at once; an integer division returns zero here, the ratio has to be taken in floating point; the question asks which, so the share is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT o.title FROM case_rec c JOIN office o ON o.id = c.office_id GROUP BY o.title ORDER BY SUM(CASE WHEN c.closed_at IS NULL AND c.due_dt < '2026-11-02' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) DESC, o.title LIMIT 1
    ('Northport east',)

ответ модели:
    SELECT o.title AS office_title
FROM office o
JOIN case_rec cr ON o.id = cr.office_id
JOIN stage s ON cr.id = s.case_id
JOIN result_ref rr ON s.result_cd = rr.cd
WHERE cr.dt_sub = '2026-11-02'
GROUP BY o.title
ORDER BY SUM(CASE WHEN rr.title = 'Успешно' THEN 1 ELSE 0 END) / COUNT(*) DESC
LIMIT 1
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: фильтрует по дате подачи вместо просрочки, выдача пустая

## 20. public_services/gov2-040 ru/1

ловушка: case_rec joined twice to itself, with the pair taken once by comparing ids; the submission date is split across the legacy pair, so the equality is between two coalesced expressions
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec a JOIN case_rec b ON b.applicant_id = a.applicant_id AND b.id > a.id AND COALESCE(a.dt_sub, a.submitted_at) = COALESCE(b.dt_sub, b.submitted_at) WHERE a.service_id <> b.service_id
    (3,)

ответ модели:
    SELECT 
    a.full_name, 
    cr.dt_sub, 
    COUNT(DISTINCT s.title) AS service_count
FROM 
    applicant a
JOIN 
    case_rec cr ON a.id = cr.applicant_id
JOIN 
    service s ON cr.service_id = s.id
GROUP BY 
    a.full_name, 
    cr.dt_sub
HAVING 
    COUNT(DISTINCT s.title) > 1
    ('Alina Almeida', None, 4)
    ('Alina Hale', None, 2)
    ('Alina Kovach', None, 2)
    ('Alina Linde', None, 3)
    ('Alina Marek', None, 2)
    ('Alina Oduya', None, 4)
    ('Alina Reiner', None, 4)
    ('Anna Almeida', None, 4)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: считает заявителей с разными услугами, а не пары дел, и дата пустая
