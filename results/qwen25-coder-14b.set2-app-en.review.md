# Ручной разбор провалов: qwen25-coder-14b.set2-app-en.jsonl

Провалов всего: 245 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-034 en/1

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
WHERE l1.opened_at < l2.opened_at
AND l1.closed_at IS NULL
AND l2.closed_at IS NULL
AND l1.id != l2.id
    ('Nina Bauer',)
    ('Timur Varga',)
    ('Boris Kovach',)
    ('Boris Almeida',)
    ('Alina Soto',)
    ('Anna Petran',)
    ('Timur Petran',)
    ('Artem Kovach',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: берёт только пары, где оба кредита не закрыты, и теряет перекрытия с закрытым

## 2. hr/hr2-037 en/1

ловушка: the comparison is against the parent's own count, which is a correlated subquery inside HAVING; a department with no parent is not a sub-department and must be excluded; working is status_cd = 1, and the leaving date does not decide it
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title AS department, COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 AND d.parent_id IS NOT NULL GROUP BY d.id, d.title HAVING COUNT(*) > (SELECT COUNT(*) FROM emp e2 WHERE e2.dept_id = d.parent_id AND e2.status_cd = 1) ORDER BY n DESC, d.title
    ('Data', 32)
    ('Platform', 32)

ответ модели:
    SELECT 
    sub_dept.title AS sub_department,
    sub_dept_headcount AS working_headcount
FROM (
    SELECT 
        e.dept_id AS sub_dept_id,
        COUNT(e.id) AS sub_dept_headcount
    FROM 
        emp e
    JOIN 
        emp_status_ref esr ON e.status_cd = esr.cd
    WHERE 
        esr.title = 'working'
    GROUP BY 
        e.dept_id
) sub_dept
JOIN 
    dept d ON sub_dept.sub_dept_id = d.id
WHERE 
    sub_dept.sub_dept_headcount > (
        SELECT 
            COUNT(e.id)
        FROM 
            emp e
        JOIN 
            emp_status_ref esr ON e.status_cd = esr.cd
        WHERE 
            esr.title = 'working' AND e.dept_id = d.parent_id
    )
    ОШИБКА: OperationalError: no such column: sub_dept.title

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: ссылка на несуществующую колонку sub_dept.title, запрос не выполнился

## 3. hr/hr2-046 en/0

ловушка: pay_hist joined twice to itself, once for the earliest row and once for the latest; the comparison ignores the currency, which is what the question asks and not what it should
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM pay_hist f JOIN pay_hist l ON l.emp_id = f.emp_id WHERE f.from_dt = (SELECT MIN(x.from_dt) FROM pay_hist x WHERE x.emp_id = f.emp_id) AND l.from_dt = (SELECT MAX(x.from_dt) FROM pay_hist x WHERE x.emp_id = f.emp_id) AND l.amount_minor < f.amount_minor
    (91,)

ответ модели:
    SELECT COUNT(*)
FROM (
    SELECT e.id AS emp_id, 
           MAX(ph.from_dt) AS current_salary_date, 
           MIN(ph.from_dt) AS first_salary_date
    FROM emp e
    JOIN pay_hist ph ON e.id = ph.emp_id
    GROUP BY e.id
    HAVING MAX(ph.amount_minor) / 100.0 < MIN(ph.amount_minor) / 100.0
)
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает максимум суммы с минимумом вместо последней с первой, всегда ложь

## 4. logistics/log2-018 en/0

ловушка: the dispatch date is split across the legacy pair dt_disp/dispatched_at; delivered is the status, not the presence of a delivery date; dates are text, so the difference needs julianday
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(julianday(delivered_at) - julianday(COALESCE(dt_disp, dispatched_at))), 1) AS days FROM shp WHERE status_cd = 2
    (20.0,)

ответ модели:
    SELECT AVG(julianday(shp.delivered_at) - julianday(COALESCE(shp.dt_disp, shp.dispatched_at))) AS avg_days
FROM shp
    (19.95551257253385,)

ошибка исполнения: нет

вердикт: evaluator
заметка: то же среднее без округления до одного знака, 19.956 против 20.0

## 5. logistics/log2-038 en/0

ловушка: how many countries exist is a fact of loc_ref, not a number to hard-code; the country is one step beyond the destination code; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT c.id FROM cust c JOIN shp s ON s.cust_id = c.id JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY c.id HAVING COUNT(DISTINCT d.country) = (SELECT COUNT(DISTINCT country) FROM loc_ref))
    (37,)

ответ модели:
    SELECT COUNT(DISTINCT cust_id) 
FROM (
    SELECT shp.cust_id, loc_ref.country
    FROM shp
    JOIN loc_ref ON shp.dst_cd = loc_ref.cd
    GROUP BY shp.cust_id, loc_ref.country
    HAVING COUNT(DISTINCT loc_ref.country) = (SELECT COUNT(DISTINCT country) FROM loc_ref)
) AS complete_countries
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: HAVING внутри группы по стране, distinct всегда 1, ответ 0

## 6. logistics/log2-045 en/1

ловушка: the country of arrival is two steps from the leg: shipment, then the destination code; the destination end, not the origin; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT l.carr_id FROM leg l JOIN shp s ON s.id = l.shp_id JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY l.carr_id HAVING COUNT(DISTINCT d.country) > 1)
    (45,)

ответ модели:
    SELECT COUNT(DISTINCT carr_id) 
FROM (
    SELECT carr_id, COUNT(DISTINCT country) AS country_count 
    FROM leg 
    JOIN loc_ref ON leg.shp_id = shp.id AND shp.dst_cd = loc_ref.cd 
    GROUP BY carr_id 
    HAVING country_count > 1
)
    ОШИБКА: OperationalError: no such column: shp.id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: ссылка на shp.id без присоединения shp, запрос не выполнился

## 7. manufacturing/mfg2-001 en/0

ловушка: the quantities are in three units, so the only honest total is one per unit; a single SUM adds tonnes to pieces
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT u.title AS unit, SUM(m.qty) AS total FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd GROUP BY u.title ORDER BY u.title
    ('kilogram', 66543.0)
    ('piece', 91727.0)
    ('tonne', 610.6)

ответ модели:
    SELECT 
    unit_ref.title AS unit_of_measure, 
    SUM(mov.qty * unit_ref.to_base) AS total_quantity
FROM 
    mov
JOIN 
    unit_ref ON mov.unit_cd = unit_ref.cd
GROUP BY 
    unit_ref.title
    ('kilogram', 66543.0)
    ('piece', 91727.0)
    ('tonne', 610600.0)

ошибка исполнения: нет

вердикт: model
заметка: переводит в базовые единицы там, где вопрос просил как записано

## 8. manufacturing/mfg2-004 en/1

ловушка: the direction is in kind_cd, not in the sign of qty; scrap is a third kind and belongs on neither side of the subtraction
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title, ROUND(SUM(CASE WHEN m.kind_cd = 2 THEN m.qty * u.to_base WHEN m.kind_cd = 1 THEN -m.qty * u.to_base ELSE 0 END), 2) AS net FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id GROUP BY p.title ORDER BY net DESC, p.title
    ('bracket', 35124.0)
    ('bushing', 16750.0)
    ('plate', 8170.0)
    ('spring', -7557.0)
    ('shaft', -16565.0)
    ('gearwheel', -23201.0)

ответ модели:
    SELECT 
    p.code AS part_code,
    p.title AS part_title,
    SUM(CASE WHEN m.kind_cd = 1 THEN m.qty * ur.to_base ELSE 0 END) AS issued,
    SUM(CASE WHEN m.kind_cd = 2 THEN m.qty * ur.to_base ELSE 0 END) AS received,
    SUM(CASE WHEN m.kind_cd = 2 THEN m.qty * ur.to_base ELSE 0 END) - 
    SUM(CASE WHEN m.kind_cd = 1 THEN m.qty * ur.to_base ELSE 0 END) AS net_received
FROM 
    mov m
JOIN 
    part p ON m.part_id = p.id
JOIN 
    unit_ref ur ON m.unit_cd = ur.cd
WHERE 
    m.kind_cd IN (1, 2)
GROUP BY 
    p.id, p.code, p.title
    ('BR-100', 'bracket', 105826.0, 140950.0, 35124.0)
    ('SH-210', 'shaft', 81063.0, 64498.0, -16565.0)
    ('PL-330', 'plate', 52376.0, 60546.0, 8170.0)
    ('GR-440', 'gearwheel', 61972.0, 38771.0, -23201.0)
    ('BU-550', 'bushing', 23275.0, 40025.0, 16750.0)
    ('SP-660', 'spring', 9048.0, 1491.0, -7557.0)

ошибка исполнения: нет

вердикт: evaluator
заметка: та же разность по каждой детали, но добавлены код и два промежуточных столбца

## 9. manufacturing/mfg2-017 en/1

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
    (SUM(CASE WHEN m.kind_cd = 3 THEN m.qty * ur.to_base ELSE 0 END) * 100.0 / SUM(m.qty * ur.to_base)) AS scrapped_percentage
FROM 
    mov m
JOIN 
    part p ON m.part_id = p.id
JOIN 
    unit_ref ur ON m.unit_cd = ur.cd
GROUP BY 
    p.title
    ('bracket', 15.186467007832611)
    ('bushing', 15.411649940534256)
    ('gearwheel', 3.445532787670839)
    ('plate', 7.32323854076901)
    ('shaft', 12.021154427319432)
    ('spring', 7.883926230224631)

ошибка исполнения: нет

вердикт: evaluator
заметка: доля посчитана верно, но без округления различается в пятнадцатом знаке

## 10. manufacturing/mfg2-018 en/1

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
    m.qty * ur.to_base AS converted_qty_kg
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

## 11. manufacturing/mfg2-024 en/0

ловушка: the range join; a join on part_id alone inflates the total about fourfold and the single number gives no hint of it; the conversion and the minor units both apply to every row
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(m.qty * u.to_base * pp.minor / 100.0), 2) AS total FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part_price pp ON pp.part_id = m.part_id AND COALESCE(m.dt_op, m.recorded_at) >= pp.valid_from AND (pp.valid_to IS NULL OR COALESCE(m.dt_op, m.recorded_at) < pp.valid_to)
    (28968594.26,)

ответ модели:
    SELECT 
    m.id AS mov_id,
    p.code AS part_code,
    p.title AS part_title,
    m.qty AS quantity,
    ur.title AS unit_title,
    ur.to_base AS unit_to_base,
    pp.minor AS price_per_unit,
    m.qty * pp.minor * ur.to_base AS total_value
FROM 
    mov m
JOIN 
    part p ON m.part_id = p.id
JOIN 
    unit_ref ur ON m.unit_cd = ur.cd
JOIN 
    part_price pp ON m.part_id = pp.part_id
WHERE 
    pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) 
    AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at))
    (1, 'SH-210', 'shaft', 291.0, 'piece', 1.0, 1132, 329412.0)
    (2, 'SH-210', 'shaft', 348.0, 'kilogram', 1.0, 1659, 577332.0)
    (3, 'BR-100', 'bracket', 64.0, 'piece', 1.0, 1486, 95104.0)
    (4, 'SH-210', 'shaft', 62.0, 'piece', 1.0, 1452, 90024.0)
    (5, 'SH-210', 'shaft', 8.64, 'tonne', 1000.0, 1452, 12545280.0)
    (6, 'BU-550', 'bushing', 215.0, 'piece', 1.0, 4922, 1058230.0)
    (7, 'PL-330', 'plate', 135.0, 'piece', 1.0, 9902, 1336770.0)
    (8, 'GR-440', 'gearwheel', 258.0, 'piece', 1.0, 4239, 1093662.0)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: вернул построчную детализацию вместо одной суммы

## 12. manufacturing/mfg2-037 en/0

ловушка: the threshold is a scalar subquery that has to convert the units as well; comparing the raw quantity adds pieces to tonnes and the answer looks plausible
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.qty * u.to_base > (SELECT AVG(m2.qty * u2.to_base) FROM mov m2 JOIN unit_ref u2 ON u2.cd = m2.unit_cd)
    (93,)

ответ модели:
    SELECT COUNT(*) 
FROM mov 
WHERE COALESCE(dt_op, recorded_at) > (
    SELECT AVG(qty * to_base) 
    FROM mov 
    JOIN unit_ref ON mov.unit_cd = unit_ref.cd
)
    (900,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает дату операции со средним количеством

## 13. medicine/med2-042 en/1

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
    r.title AS route,
    ROUND(SUM(CASE WHEN rx.days > (julianday(e.discharged) - julianday(e.dt_adm)) THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS percentage
FROM 
    rx
JOIN 
    enc e ON rx.enc_id = e.id
JOIN 
    route_ref r ON rx.route_cd = r.cd
GROUP BY 
    r.title
    ('inhalation', 12.5)
    ('intravenous', 15.53)
    ('oral', 12.03)
    ('topical', 12.53)

ошибка исполнения: нет

вердикт: model
заметка: потерян COALESCE на дату поступления и отбор по выписанным

## 14. medicine/med2-047 en/1

ловушка: the average is over encounters, so the counting has to happen before the grouping by state; an inner join drops the encounters with no diagnosis and raises the average; the state is a code, its name lives in status_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT st.title AS status, ROUND(AVG(k), 2) AS mean_dx FROM (SELECT e.id, e.status_cd, COUNT(d.id) AS k FROM enc e LEFT JOIN dx d ON d.enc_id = e.id GROUP BY e.id, e.status_cd) t JOIN status_ref st ON st.cd = t.status_cd GROUP BY st.title ORDER BY mean_dx DESC, st.title
    ('planned', 1.43)
    ('cancelled', 1.37)
    ('discharged', 1.33)
    ('active', 1.27)

ответ модели:
    SELECT 
    s.title AS encounter_state,
    ROUND(COUNT(d.enc_id) / COUNT(e.id), 2) AS mean_diagnoses
FROM 
    enc e
LEFT JOIN 
    dx d ON e.id = d.enc_id
JOIN 
    status_ref s ON e.status_cd = s.cd
GROUP BY 
    s.title
    ('active', 0.0)
    ('cancelled', 0.0)
    ('discharged', 0.0)
    ('planned', 0.0)

ошибка исполнения: нет

вердикт: model
заметка: целочисленное деление, все доли обнулились

## 15. public_services/gov2-016 en/0

ловушка: the maximum has to be taken per case before the NULL test, not after it
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM stage s WHERE s.result_cd IS NULL AND s.seq = (SELECT MAX(s2.seq) FROM stage s2 WHERE s2.case_id = s.case_id)
    (125,)

ответ модели:
    SELECT COUNT(*) 
FROM case_rec 
WHERE id NOT IN (
    SELECT case_id 
    FROM stage 
    ORDER BY seq DESC 
    GROUP BY case_id 
    HAVING MAX(result_cd) IN (1, 2, 3)
)
    ОШИБКА: OperationalError: near "GROUP": syntax error

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: GROUP BY после ORDER BY, синтаксическая ошибка

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
) AS undecided_stages
    (51,)

ошибка исполнения: нет

вердикт: model
заметка: считает не те пары стадий, 51 против 135

## 17. public_services/gov2-033 en/1

ловушка: the last stage is the largest seq of that case, which is a correlated subquery; approved is result_cd = 1, a code and not a word; the stage and the case disagree, and the question is exactly about that disagreement
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM stage s JOIN case_rec c ON c.id = s.case_id WHERE s.seq = (SELECT MAX(s2.seq) FROM stage s2 WHERE s2.case_id = s.case_id) AND s.result_cd = 1 AND c.closed_at IS NULL
    (40,)

ответ модели:
    SELECT COUNT(*)
FROM case_rec cr
JOIN stage s ON cr.id = s.case_id
JOIN result_ref rr ON s.result_cd = rr.cd
WHERE rr.title = 'approved'
AND cr.closed_at IS NULL
    (84,)

ошибка исполнения: нет

вердикт: model
заметка: не ограничивает последней стадией, считает все одобренные

## 18. public_services/gov2-034 en/1

ловушка: the last stage is the largest seq of that case, which is a correlated subquery; an undecided stage is NULL in result_cd, which no equality test matches; the stage and the case disagree in the direction opposite to the previous question
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM stage s JOIN case_rec c ON c.id = s.case_id WHERE s.seq = (SELECT MAX(s2.seq) FROM stage s2 WHERE s2.case_id = s.case_id) AND s.result_cd IS NULL AND c.closed_at IS NOT NULL
    (116,)

ответ модели:
    SELECT COUNT(*) 
FROM case_rec 
WHERE id NOT IN (
    SELECT case_id 
    FROM stage 
    WHERE result_cd IS NOT NULL
)
    (159,)

ошибка исполнения: нет

вердикт: model
заметка: берёт дела вовсе без решённых стадий вместо последней без результата

## 19. public_services/gov2-037 en/0

ловушка: an inner join drops the cases with no stage and raises the average; COUNT(*) counts the row the outer join produced, so the count has to be over the stage's own column
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(k), 2) AS mean_stages FROM (SELECT c.id, COUNT(s.id) AS k FROM case_rec c LEFT JOIN stage s ON s.case_id = c.id GROUP BY c.id)
    (1.97,)

ответ модели:
    SELECT AVG(CASE WHEN stage.case_id IS NULL THEN 0 ELSE COUNT(stage.case_id) END) AS average_stages
FROM case_rec
LEFT JOIN stage ON case_rec.id = stage.case_id
GROUP BY case_rec.id
    ОШИБКА: OperationalError: misuse of aggregate function COUNT()

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: COUNT внутри AVG, misuse of aggregate

## 20. public_services/gov2-039 en/0

ловушка: the share is of two aggregates over the same group, and the numerator carries two conditions at once; an integer division returns zero here, the ratio has to be taken in floating point; the question asks which, so the share is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT o.title FROM case_rec c JOIN office o ON o.id = c.office_id GROUP BY o.title ORDER BY SUM(CASE WHEN c.closed_at IS NULL AND c.due_dt < '2026-11-02' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) DESC, o.title LIMIT 1
    ('Northport east',)

ответ модели:
    SELECT o.title AS office_title
FROM office o
JOIN case_rec cr ON o.id = cr.office_id
LEFT JOIN stage s ON cr.id = s.case_id
WHERE s.result_cd IS NULL AND cr.due_dt < CURRENT_DATE
GROUP BY o.title
ORDER BY COUNT(*) DESC
LIMIT 1
    ('Eastvale office',)

ошибка исполнения: нет

вердикт: model
заметка: считает число дел вместо доли и берёт стадии вместо самих дел
