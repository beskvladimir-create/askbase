# Ручной разбор провалов: arctic-7b-q4.set2-base-en.jsonl

Провалов всего: 382 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-018 en/0

ловушка: rate is in basis points and must be divided by 100
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT MAX(rate_bp) / 100.0 AS top_rate FROM loan
    (19.18,)

ответ модели:
    SELECT MAX(rate_bp) / 100 AS highest_loan_rate_percentage
FROM loan
    (19,)

ошибка исполнения: нет

вердикт: model
заметка: целочисленное деление базисных пунктов, 19 вместо 19.18, потеряны значащие знаки ставки

## 2. banking/bank2-041 en/0

ловушка: residency is a code on cust, reached through the loan's owner; the principal is stored in minor units although its name does not say so
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS residency, ROUND(AVG(l.principal) / 100.0, 2) AS mean_principal FROM loan l JOIN cust c ON c.id = l.cust_id JOIN resid_ref r ON r.cd = c.resid_cd GROUP BY r.title ORDER BY r.title
    ('non-resident', 50398.08)
    ('resident', 45947.19)

ответ модели:
    SELECT 
    CASE 
        WHEN c.resid_cd = 'RESIDENT' THEN 'Resident'
        ELSE 'Non-Resident'
    END AS resident_status,
    AVG(l.principal / 100.0) AS average_loan_size
FROM 
    loan l
JOIN 
    cust c ON l.cust_id = c.id
JOIN 
    acct a ON l.cust_id = a.cust_id
GROUP BY 
    resident_status
    ('Non-Resident', 47049.812010443864)

ошибка исполнения: нет

вердикт: model
заметка: резидентство сравнивается со словом RESIDENT, осталась одна строка

## 3. hr/hr2-006 en/1

ловушка: the department table joined to itself under two aliases; a department with no parent is its own top level, which COALESCE handles
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT top.title, COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id JOIN dept top ON top.id = COALESCE(d.parent_id, d.id) WHERE e.status_cd = 1 GROUP BY top.title ORDER BY n DESC, top.title
    ('Engineering', 95)
    ('Operations', 62)
    ('Finance', 34)

ответ модели:
    WITH RECURSIVE DepartmentHierarchy AS (
    SELECT id, title, parent_id, id AS top_id
    FROM dept
    WHERE parent_id IS NULL
    UNION ALL
    SELECT d.id, d.title, d.parent_id, dh.top_id
    FROM dept d
    JOIN DepartmentHierarchy dh ON d.parent_id = dh.id
),
EmployeeCounts AS (
    SELECT dh.top_id, COUNT(e.id) AS employee_count
    FROM DepartmentHierarchy dh
    JOIN emp e ON dh.id = e.dept_id
    GROUP BY dh.top_id
)
SELECT dh.title, COALESCE(ec.employee_count, 0) AS total_employees
FROM DepartmentHierarchy dh
LEFT JOIN EmployeeCounts ec ON dh.top_id = ec.top_id
GROUP BY dh.top_id, dh.title
ORDER BY dh.top_id
    ('Operations', 82)
    ('Support', 82)
    ('Data', 131)
    ('Engineering', 131)
    ('Platform', 131)
    ('Finance', 47)

ошибка исполнения: нет

вердикт: model
заметка: рекурсия выдаёт по строке на каждый отдел ветки, шесть строк вместо трёх

## 4. hr/hr2-040 en/0

ловушка: an inner join drops the people with no absence and raises the average; SUM over no rows is NULL rather than zero, so it has to be replaced before the averaging
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(k), 2) AS mean_days FROM (SELECT e.id, COALESCE(SUM(a.days), 0) AS k FROM emp e LEFT JOIN absence a ON a.emp_id = e.id GROUP BY e.id)
    (18.15,)

ответ модели:
    SELECT AVG(COALESCE(a.days, 0)) AS average_absence_days
FROM emp e
LEFT JOIN absence a ON e.id = a.emp_id
    (10.128755364806867,)

ошибка исполнения: нет

вердикт: model
заметка: усредняет строки отсутствий, а не людей, 10.1 против 18.15

## 5. logistics/log2-004 en/0

ловушка: the status and the delivery date disagree by design, and the question is about exactly that disagreement
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 3 AND delivered_at IS NOT NULL
    (15,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
WHERE status_cd = 'LOST' AND delivered_at IS NOT NULL
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: статус сравнивается со словом LOST, ответ 0

## 6. logistics/log2-006 en/1

ловушка: distance per shipment means summing its legs first and averaging after, not averaging the legs
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(total), 1) AS mean_km FROM (SELECT SUM(dist_km) AS total FROM leg GROUP BY shp_id)
    (3668.7,)

ответ модели:
    SELECT ROUND(AVG(dist_km), 1) AS mean_distance_per_shipment
FROM leg
    (1328.9,)

ошибка исполнения: нет

вердикт: model
заметка: усредняет плечи вместо суммы по перевозке, 1328.9 против 3668.7

## 7. logistics/log2-018 en/1

ловушка: the dispatch date is split across the legacy pair dt_disp/dispatched_at; delivered is the status, not the presence of a delivery date; dates are text, so the difference needs julianday
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(julianday(delivered_at) - julianday(COALESCE(dt_disp, dispatched_at))), 1) AS days FROM shp WHERE status_cd = 2
    (20.0,)

ответ модели:
    SELECT AVG(julianday(delivered_at) - julianday(dispatched_at)) AS avg_delivery_time
FROM shp
WHERE status_cd = 'D'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: статус сравнивается с буквой D, результат None

## 8. logistics/log2-026 en/1

ловушка: a shipment with no delivery date cannot qualify and must be excluded; the date of the incident has nothing to do with the dates of the shipment, so this is a comparison and not a filter
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM inc i JOIN shp s ON s.id = i.shp_id WHERE s.delivered_at IS NOT NULL AND i.at > s.delivered_at
    (80,)

ответ модели:
    SELECT COUNT(*)
FROM inc
INNER JOIN shp ON inc.shp_id = shp.id
WHERE inc.at > shp.dt_disp
    (65,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает с датой отправки вместо даты сдачи, 65 против 80

## 9. logistics/log2-048 en/0

ловушка: three tables in one comparison: the leg carries neither of the two dates; the dispatch date is split across the legacy pair dt_disp/dispatched_at
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(DISTINCT l.id) AS n FROM leg l JOIN carr c ON c.id = l.carr_id JOIN shp s ON s.id = l.shp_id WHERE c.since > COALESCE(s.dt_disp, s.dispatched_at)
    (11,)

ответ модели:
    SELECT COUNT(*) AS total_legs
FROM leg l
JOIN carr c ON l.carr_id = c.id
JOIN shp s ON l.shp_id = s.id
WHERE c.since > s.dispatched_at
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: без COALESCE на дату отправки, ответ 0

## 10. manufacturing/mfg2-008 en/0

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
    SUM(m.qty * pp.minor) AS total_scrap_cost
FROM 
    mov m
INNER JOIN 
    part p ON m.part_id = p.id
INNER JOIN 
    part_price pp ON m.part_id = pp.part_id
INNER JOIN 
    mov_kind_ref mk ON m.kind_cd = mk.cd
WHERE 
    mk.title = 'Scrap' AND
    m.dt_op BETWEEN pp.valid_from AND pp.valid_to
GROUP BY 
    p.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: вид движения ищется как Scrap и BETWEEN не находит открытое окно, выдача пустая

## 11. manufacturing/mfg2-014 en/0

ловушка: a difference between two text dates needs julianday; the movement date comes from the legacy pair
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM defect d JOIN mov m ON m.id = d.mov_id WHERE julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at)) > 90
    (155,)

ответ модели:
    SELECT COUNT(*) AS defect_count
FROM defect d
JOIN mov m ON d.mov_id = m.id
WHERE julianday(d.found_at) - julianday(m.recorded_at) > 90
    (5,)

ошибка исполнения: нет

вердикт: model
заметка: берёт recorded_at без COALESCE, 5 против 155

## 12. manufacturing/mfg2-018 en/0

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
    SELECT m.id, p.title AS part_title, l.title AS line_title
FROM mov m
INNER JOIN part p ON m.part_id = p.id
INNER JOIN line l ON m.line_id = l.id
WHERE m.qty > 1000
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает количество без перевода единиц, выдача пустая

## 13. manufacturing/mfg2-036 en/1

ловушка: a defect found before its movement would drag the average down and the question excludes it; the movement date is split across the legacy pair dt_op/recorded_at; the grade is a code, its name lives in grade_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT g.title AS grade, ROUND(AVG(julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at))), 2) AS days FROM defect d JOIN mov m ON m.id = d.mov_id JOIN grade_ref g ON g.cd = d.grade_cd WHERE d.found_at >= COALESCE(m.dt_op, m.recorded_at) GROUP BY g.title ORDER BY days DESC, g.title
    ('major', 479.17)
    ('minor', 385.42)
    ('critical', 324.8)

ответ модели:
    SELECT 
    gr.title AS grade_title,
    AVG(julianday(d.found_at) - julianday(m.recorded_at)) AS avg_days_to_defect
FROM 
    defect d
INNER JOIN 
    mov m ON d.mov_id = m.id
INNER JOIN 
    grade_ref gr ON d.grade_cd = gr.cd
WHERE 
    julianday(d.found_at) > julianday(m.recorded_at)
GROUP BY 
    gr.title
    ('critical', 104.0)
    ('major', 70.66666666666667)
    ('minor', 103.0)

ошибка исполнения: нет

вердикт: model
заметка: берёт recorded_at без COALESCE, средние втрое меньше

## 14. manufacturing/mfg2-039 en/1

ловушка: two conditions that have to hold on different rows, which one join cannot express; critical is grade_cd = 3 and the shift is a code on the line, two codes in one question
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title FROM part p WHERE EXISTS (SELECT 1 FROM defect d JOIN mov m ON m.id = d.mov_id JOIN line l ON l.id = m.line_id WHERE m.part_id = p.id AND d.grade_cd = 3 AND l.shift_cd = 1) AND EXISTS (SELECT 1 FROM defect d JOIN mov m ON m.id = d.mov_id JOIN line l ON l.id = m.line_id WHERE m.part_id = p.id AND d.grade_cd = 3 AND l.shift_cd = 2) ORDER BY p.title
    ('bracket',)
    ('plate',)
    ('shaft',)

ответ модели:
    SELECT p.title AS part_title
FROM part p
JOIN mov m ON p.id = m.part_id
JOIN defect d ON m.id = d.mov_id
JOIN shift_ref s ON m.shift_cd = s.cd
WHERE s.title IN ('Day Shift', 'Night Shift')
GROUP BY p.title
HAVING COUNT(DISTINCT s.title) = 2
    ОШИБКА: OperationalError: no such column: m.shift_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к mov.shift_cd, смена задана на линии

## 15. manufacturing/mfg2-044 en/1

ловушка: two defects on one movement must not count it twice; the unit is a code, its name lives in unit_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT u.title AS unit, COUNT(DISTINCT m.id) AS movements FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN defect d ON d.mov_id = m.id GROUP BY u.title ORDER BY movements DESC, u.title
    ('piece', 100)
    ('kilogram', 76)
    ('tonne', 22)

ответ модели:
    SELECT 
    m.unit_cd,
    COUNT(DISTINCT m.id) AS distinct_movements_with_defects
FROM 
    mov m
JOIN 
    defect d ON m.id = d.mov_id
GROUP BY 
    m.unit_cd
    (1, 100)
    (2, 76)
    (3, 22)

ошибка исполнения: нет

вердикт: model
заметка: вернул коды единиц вместо названий

## 16. manufacturing/mfg2-046 en/0

ловушка: the sign of a movement lives in kind_cd, and scrap is a third kind that belongs to neither side; the price is joined on a range, and a plain join on part_id multiplies every movement; the quantity has to be converted before it is multiplied by the price
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(CASE WHEN m.kind_cd = 2 THEN m.qty * u.to_base * pp.minor / 100.0 WHEN m.kind_cd = 1 THEN -m.qty * u.to_base * pp.minor / 100.0 ELSE 0 END), 2) AS net FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part_price pp ON pp.part_id = m.part_id AND pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at))
    (359323.93,)

ответ модели:
    WITH MovementsCTE AS (
    SELECT 
        m.kind_cd,
        m.qty,
        p.minor AS price_minor,
        CASE 
            WHEN mk.title LIKE '%receipt%' THEN m.qty * p.minor
            ELSE 0
        END AS receipt_value,
        CASE 
            WHEN mk.title LIKE '%issue%' THEN m.qty * p.minor
            ELSE 0
        END AS issue_value
    FROM mov m
    INNER JOIN part_price p ON m.part_id = p.part_id
    INNER JOIN mov_kind_ref mk ON m.kind_cd = mk.cd
    WHERE m.recorded_at BETWEEN p.valid_from AND p.valid_to
)
SELECT 
    SUM(receipt_value) - SUM(issue_value) AS net_value
FROM MovementsCTE
    (-6780801.339999999,)

ошибка исполнения: нет

вердикт: model
заметка: нет перевода единиц и копеек, и BETWEEN теряет открытое окно

## 17. medicine/med2-006 en/0

ловушка: the admission date has to be assembled from the legacy pair dt_adm/admitted_at; discharged means status_cd = 2, not that the discharge column is filled
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(julianday(e.discharged) - julianday(COALESCE(e.dt_adm, e.admitted_at))), 2) AS avg_days FROM enc e WHERE e.status_cd = 2
    (11.05,)

ответ модели:
    SELECT ROUND(AVG(julianday(e.discharged) - julianday(e.admitted_at)), 2) AS average_length_of_stay
FROM enc e
JOIN status_ref sr ON e.status_cd = sr.cd
WHERE sr.title = 'Discharged'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: статус ищется как Discharged и нет COALESCE, результат None

## 18. medicine/med2-026 en/0

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
INNER JOIN enc e ON p.id = e.pat_id
GROUP BY p.id
HAVING COUNT(e.id) = COUNT(CASE WHEN e.status_cd = 'cancelled' THEN 1 END)
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: статус сравнивается со словом cancelled, выдача пустая

## 19. medicine/med2-036 en/1

ловушка: two correlated subqueries compared with each other, which no single join gives; an encounter with neither is not greater than itself and must not be counted
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM enc e WHERE (SELECT COUNT(*) FROM rx x WHERE x.enc_id = e.id) > (SELECT COUNT(*) FROM dx d WHERE d.enc_id = e.id)
    (413,)

ответ модели:
    SELECT COUNT(*) AS encounter_count
FROM (
    SELECT e.enc_id
    FROM enc e
    LEFT JOIN dx d ON e.enc_id = d.enc_id
    LEFT JOIN rx r ON e.enc_id = r.enc_id
    GROUP BY e.enc_id
    HAVING COUNT(r.enc_id) > COUNT(d.enc_id)
) AS filtered_encounters
    ОШИБКА: OperationalError: no such column: e.enc_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к enc.enc_id, такой колонки нет

## 20. public_services/gov2-030 en/1

ловушка: how many regions exist is a fact of region_ref, not a number to hard-code; the region is one step beyond the office, which is itself one step beyond the case
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT c.applicant_id FROM case_rec c JOIN office o ON o.id = c.office_id GROUP BY c.applicant_id HAVING COUNT(DISTINCT o.region_cd) = (SELECT COUNT(*) FROM region_ref))
    (21,)

ответ модели:
    SELECT r.title AS region_title, COUNT(c.id) AS case_count
FROM case_rec c
JOIN office o ON c.office_id = o.id
JOIN region_ref r ON o.region_cd = r.cd
GROUP BY r.title
    ('Eastvale', 164)
    ('Marden', 148)
    ('Northport', 307)
    ('Thorne', 141)

ошибка исполнения: нет

вердикт: model
заметка: вернул число дел по регионам вместо числа людей, подавших во всех
