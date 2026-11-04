# Ручной разбор провалов: qwen25-coder-7b.set2-base-ru.jsonl

Провалов всего: 448 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-013 ru/1

ловушка: residency is a code, needs the lookup join
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS residency, COUNT(*) AS n FROM cust c JOIN resid_ref r ON r.cd = c.resid_cd GROUP BY r.title ORDER BY n DESC, r.title
    ('resident', 284)
    ('non-resident', 66)

ответ модели:
    SELECT 
    CASE 
        WHEN resid_cd IS NOT NULL THEN 'Resident'
        ELSE 'Non-Resident'
    END AS residency_status,
    COUNT(*) AS customer_count
FROM 
    cust
GROUP BY 
    residency_status
    ('Resident', 350)

ошибка исполнения: нет

вердикт: model
заметка: резидентство определяет по непустоте кода, одна строка вместо двух

## 2. banking/bank2-048 ru/0

ловушка: two joins to reach it: customer to account to transaction; holding accounts in two currencies is not the same as having moved money in both; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT c.id FROM cust c JOIN acct a ON a.cust_id = c.id JOIN txn t ON t.acct_id = a.id GROUP BY c.id HAVING COUNT(DISTINCT a.cur_cd) > 1)
    (139,)

ответ модели:
    SELECT COUNT(DISTINCT cust_id) 
FROM acct 
WHERE cust_id IN (
    SELECT cust_id 
    FROM txn 
    GROUP BY cust_id 
    HAVING COUNT(DISTINCT cur_cd) > 1
)
    ОШИБКА: OperationalError: no such column: cust_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к txn.cust_id, которого нет

## 3. hr/hr2-022 ru/0

ловушка: the currency is a code and its name is in the lookup; an earlier row in another currency does not make the person an answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT e.full_name FROM emp e JOIN pay_hist p ON p.emp_id = e.id JOIN cur_ref c ON c.cd = p.cur_cd WHERE c.title = 'USD' AND p.from_dt = ( SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id ) ORDER BY e.full_name
    ('Alina Almeida',)
    ('Alina Kovach',)
    ('Alina Oduya',)
    ('Alina Petran',)
    ('Anna Reiner',)
    ('Anna Varga',)
    ('Artem Marek',)
    ('Artem Marek',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT e.full_name
FROM emp e
JOIN pay_hist ph ON e.id = ph.emp_id
JOIN cur_ref cr ON ph.cur_cd = cr.cd
WHERE cr.title = 'US Dollar'
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: валюта ищется как US Dollar вместо USD, выдача пустая

## 4. hr/hr2-035 ru/1

ловушка: emp joined to itself twice over, three aliases of one table in one query; a chain that breaks at the first level must not be counted
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM emp e JOIN emp m ON m.id = e.mgr_id JOIN emp g ON g.id = m.mgr_id
    (110,)

ответ модели:
    SELECT COUNT(*)
FROM emp e1
WHERE EXISTS (
    SELECT 1
    FROM emp e2
    WHERE e2.mgr_id = e1.id
    AND EXISTS (
        SELECT 1
        FROM emp e3
        WHERE e3.mgr_id = e2.id
    )
)
    (13,)

ошибка исполнения: нет

вердикт: model
заметка: считает руководителей сверху вниз вместо подчинённых, 13 против 110

## 5. hr/hr2-042 ru/0

ловушка: the row in force is the latest one not after the leaving date, not the latest one overall; the cut-off date is a column of the other table, so the subquery is correlated on two things at once; amounts are minor units and must be divided by 100
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT e.full_name, p.amount_minor / 100.0 AS pay FROM emp e JOIN pay_hist p ON p.emp_id = e.id WHERE e.left_at IS NOT NULL AND p.from_dt = (SELECT MAX(x.from_dt) FROM pay_hist x WHERE x.emp_id = e.id AND x.from_dt <= e.left_at) ORDER BY e.full_name, pay
    ('Alina Marek', 5679.0)
    ('Anna Almeida', 3553.0)
    ('Anna Hale', 10315.0)
    ('Anna Kovach', 2311.0)
    ('Anna Varga', 7897.0)
    ('Artem Benali', 2330.0)
    ('Boris Kovach', 6411.0)
    ('Boris Linde', 10467.0)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT 
    e.full_name,
    p.amount_minor AS salary_on_leave_day
FROM 
    emp e
JOIN 
    pay_hist p ON e.id = p.emp_id
WHERE 
    e.left_at = p.from_dt
    AND e.status_cd = 'LEFT'
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: статус сравнивается со строкой LEFT и дата ухода с началом строки зарплаты

## 6. hr/hr2-048 ru/1

ловушка: dept checked against itself under another alias, by the parent reference and not by a join to the employee; working is status_cd = 1, and the leaving date does not decide it
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 AND EXISTS (SELECT 1 FROM dept c WHERE c.parent_id = d.id)
    (65,)

ответ модели:
    SELECT COUNT(e.id)
FROM emp e
JOIN dept d ON e.dept_id = d.id
WHERE d.parent_id IS NOT NULL
    (126,)

ошибка исполнения: нет

вердикт: model
заметка: считает сотрудников дочерних отделов вместо родительских, 126 против 65

## 7. logistics/log2-023 ru/1

ловушка: loc_ref is joined twice under two aliases; the country is a second hop from the city code; domestic shipments must be left out
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT o.country AS from_country, d.country AS to_country, SUM(s.weight_kg) AS kg FROM shp s JOIN loc_ref o ON o.cd = s.org_cd JOIN loc_ref d ON d.cd = s.dst_cd WHERE o.country <> d.country GROUP BY o.country, d.country ORDER BY kg DESC, o.country, d.country
    ('Aldoria', 'Cavira', 853980)
    ('Cavira', 'Dornia', 768032)
    ('Dornia', 'Breland', 652546)
    ('Aldoria', 'Dornia', 645359)
    ('Dornia', 'Cavira', 619521)
    ('Cavira', 'Aldoria', 605945)
    ('Cavira', 'Breland', 579089)
    ('Aldoria', 'Breland', 576170)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT 
    l1.title AS country1, 
    l2.title AS country2, 
    SUM(s.weight_kg) AS total_weight_kg
FROM 
    shp s
JOIN 
    loc_ref l1 ON s.org_cd = l1.cd
JOIN 
    loc_ref l2 ON s.dst_cd = l2.cd
WHERE 
    s.status_cd = 'dispatched'
GROUP BY 
    l1.title, 
    l2.title
ORDER BY 
    l1.title, 
    l2.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: статус сравнивается со словом dispatched, выдача пустая

## 8. logistics/log2-032 ru/0

ловушка: the mode belongs to the carrier, not to the leg, so the join goes through carr; costs are minor units and must be divided by 100
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT m.title AS mode, SUM(l.cost_cents) / 100.0 AS cost FROM leg l JOIN carr c ON c.id = l.carr_id JOIN mode_ref m ON m.cd = c.mode_cd GROUP BY m.title ORDER BY cost DESC, m.title
    ('road', 4171492.1)
    ('rail', 2335255.97)
    ('sea', 1566985.53)
    ('air', 659359.57)

ответ модели:
    SELECT 
    m.title AS mode_title,
    SUM(l.cost_cents) / 100 AS total_cost
FROM 
    leg l
JOIN 
    carr c ON l.carr_id = c.id
JOIN 
    mode_ref m ON c.mode_cd = m.cd
GROUP BY 
    m.title
    ('air', 659359)
    ('rail', 2335255)
    ('road', 4171492)
    ('sea', 1566985)

ошибка исполнения: нет

вердикт: evaluator
заметка: те же четыре суммы, целочисленное деление срезало копейки, расхождение меньше денежной единицы на четыре миллиона

## 9. logistics/log2-038 ru/1

ловушка: how many countries exist is a fact of loc_ref, not a number to hard-code; the country is one step beyond the destination code; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT c.id FROM cust c JOIN shp s ON s.cust_id = c.id JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY c.id HAVING COUNT(DISTINCT d.country) = (SELECT COUNT(DISTINCT country) FROM loc_ref))
    (37,)

ответ модели:
    SELECT COUNT(DISTINCT cust_id) AS customer_count
FROM shp
JOIN loc_ref ON shp.dst_cd = loc_ref.cd
GROUP BY cust_id
HAVING COUNT(DISTINCT loc_ref.country) = (SELECT COUNT(*) FROM loc_ref)
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает с числом строк справочника, а не стран, выдача пустая

## 10. logistics/log2-045 ru/0

ловушка: the country of arrival is two steps from the leg: shipment, then the destination code; the destination end, not the origin; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT l.carr_id FROM leg l JOIN shp s ON s.id = l.shp_id JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY l.carr_id HAVING COUNT(DISTINCT d.country) > 1)
    (45,)

ответ модели:
    SELECT carr.id, carr.title
FROM carr
JOIN leg ON carr.id = leg.carr_id
JOIN loc_ref org ON leg.org_cd = org.cd
JOIN loc_ref dst ON leg.dst_cd = dst.cd
GROUP BY carr.id, carr.title
HAVING COUNT(DISTINCT dst.country) > 1
    ОШИБКА: OperationalError: no such column: leg.org_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к leg.org_cd, которого нет

## 11. manufacturing/mfg2-013 ru/1

ловушка: the comparison has a direction, and getting it backwards returns the complement without any sign of error; the movement date comes from the legacy pair
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM defect d JOIN mov m ON m.id = d.mov_id WHERE d.found_at < COALESCE(m.dt_op, m.recorded_at)
    (137,)

ответ модели:
    SELECT COUNT(*)
FROM defect d
JOIN mov m ON d.mov_id = m.id
WHERE d.found_at < m.dt_op
    (51,)

ошибка исполнения: нет

вердикт: model
заметка: без COALESCE на дату движения, 51 против 137

## 12. manufacturing/mfg2-015 ru/1

ловушка: the rows whose dates run the wrong way have to be excluded or the average mixes negative gaps into it
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at))), 1) AS days FROM defect d JOIN mov m ON m.id = d.mov_id WHERE d.found_at >= COALESCE(m.dt_op, m.recorded_at)
    (404.3,)

ответ модели:
    SELECT AVG(julianday(d2.found_at) - julianday(d1.dt_op)) AS avg_gap
FROM mov m1
JOIN defect d1 ON m1.id = d1.mov_id
JOIN defect d2 ON m1.id = d2.mov_id AND d1.found_at < d2.found_at
WHERE d1.found_at >= m1.dt_op
    ОШИБКА: OperationalError: no such column: d1.dt_op

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к d1.dt_op, такой колонки у дефекта нет

## 13. manufacturing/mfg2-022 ru/0

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
    SELECT p.title AS part_title, pp.minor AS price
FROM part p
JOIN part_price pp ON p.id = pp.part_id
WHERE pp.valid_from <= '2026-03-01' AND pp.valid_to >= '2026-03-01'
AND pp.minor = (
    SELECT MINOR
    FROM part_price
    WHERE part_id = p.id
    AND valid_from <= '2026-03-01' AND valid_to >= '2026-03-01'
    ORDER BY valid_to DESC
    LIMIT 1
)
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: сравнение с valid_to не находит открытое окно с NULL, выдача пустая

## 14. manufacturing/mfg2-023 ru/1

ловушка: two counts over one pass, each on a different code
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT l.title, SUM(CASE WHEN m.kind_cd = 2 THEN 1 ELSE 0 END) AS receipts, SUM(CASE WHEN m.kind_cd = 1 THEN 1 ELSE 0 END) AS issues FROM mov m JOIN line l ON l.id = m.line_id GROUP BY l.title ORDER BY l.title
    ('Assembly A', 95, 96)
    ('Assembly B', 95, 105)
    ('Finishing', 88, 99)
    ('Machining', 108, 94)

ответ модели:
    SELECT 
    l.title AS line_title,
    SUM(CASE WHEN m.kind_cd = 'IN' THEN 1 ELSE 0 END) AS incoming_moves,
    SUM(CASE WHEN m.kind_cd = 'OUT' THEN 1 ELSE 0 END) AS outgoing_moves
FROM 
    line l
LEFT JOIN 
    mov m ON l.id = m.line_id
GROUP BY 
    l.title
    ('Assembly A', 0, 0)
    ('Assembly B', 0, 0)
    ('Finishing', 0, 0)
    ('Machining', 0, 0)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает код вида движения со словами IN и OUT, все нули

## 15. manufacturing/mfg2-043 ru/0

ловушка: the quantities have to be converted before they are compared, or pieces are added to tonnes; the share is of two sums over the same group, which the condition inside the aggregate expresses; the question asks which, so the share is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id GROUP BY p.title ORDER BY SUM(CASE WHEN m.kind_cd = 3 THEN m.qty * u.to_base ELSE 0 END) / SUM(m.qty * u.to_base) DESC, p.title LIMIT 1
    ('bushing',)

ответ модели:
    SELECT p.title AS part_title, SUM(m.qty) AS total_quantity
FROM part p
JOIN mov m ON p.id = m.part_id
JOIN defect d ON m.id = d.mov_id
GROUP BY p.title
ORDER BY total_quantity DESC
LIMIT 1
    ('bracket', 20911.91)

ошибка исполнения: нет

вердикт: model
заметка: ищет деталь с наибольшим количеством дефектов вместо наибольшей доли брака

## 16. public_services/gov2-004 ru/0

ловушка: the filter has to be strict here, because a case closed on the due date is not late and would pull the average towards zero
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(julianday(closed_at) - julianday(due_dt)), 1) AS days FROM case_rec WHERE closed_at > due_dt
    (21.0,)

ответ модели:
    SELECT AVG(CAST((julianday(closed_at) - julianday(due_dt)) AS REAL)) AS avg_delay
FROM case_rec
JOIN stage ON case_rec.id = stage.case_id
JOIN result_ref ON stage.result_cd = result_ref.cd
WHERE result_ref.title LIKE '%один знак%'
AND closed_at > due_dt
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: выдумал фильтр по названию результата из слов вопроса, результат None

## 17. public_services/gov2-005 ru/0

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
    SELECT s.title, AVG(julianday(cr.closed_at) - julianday(cr.dt_sub)) AS avg_days
FROM service s
JOIN case_rec cr ON s.id = cr.service_id
JOIN stage st ON cr.id = st.case_id
WHERE st.result_cd = 'closed'
GROUP BY s.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: фильтрует этапы по слову closed, выдача пустая

## 18. public_services/gov2-020 ru/0

ловушка: two levels in the grouping, and the region comes from the lookup through the office
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS region, o.title AS office, COUNT(*) AS n FROM case_rec c JOIN office o ON o.id = c.office_id JOIN region_ref r ON r.cd = o.region_cd GROUP BY r.title, o.title ORDER BY r.title, o.title
    ('Eastvale', 'Eastvale office', 164)
    ('Marden', 'Marden office', 148)
    ('Northport', 'Northport central', 154)
    ('Northport', 'Northport east', 153)
    ('Thorne', 'Thorne office', 141)

ответ модели:
    SELECT r.title AS region, o.title AS office, COUNT(cr.id) AS cases_accepted
FROM region_ref r
JOIN office o ON r.cd = o.region_cd
JOIN case_rec cr ON o.id = cr.office_id
JOIN stage s ON cr.id = s.case_id
WHERE s.result_cd = 'accepted'
GROUP BY r.title, o.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: фильтрует этапы по слову accepted, выдача пустая

## 19. public_services/gov2-035 ru/1

ловушка: the deadline is inclusive, so a case closed on the due date belongs to the second group; a case with no closing date belongs to neither and must be excluded
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT o.title, SUM(CASE WHEN c.closed_at > c.due_dt THEN 1 ELSE 0 END) AS late, SUM(CASE WHEN c.closed_at <= c.due_dt THEN 1 ELSE 0 END) AS on_time FROM case_rec c JOIN office o ON o.id = c.office_id WHERE c.closed_at IS NOT NULL GROUP BY o.title ORDER BY late DESC, o.title
    ('Marden office', 44, 94)
    ('Eastvale office', 35, 115)
    ('Thorne office', 35, 93)
    ('Northport east', 34, 96)
    ('Northport central', 29, 108)

ответ модели:
    SELECT 
    o.title AS office_title,
    SUM(CASE WHEN s.result_cd = 'COMPLETED_LATE' THEN 1 ELSE 0 END) AS completed_late,
    SUM(CASE WHEN s.result_cd = 'COMPLETED_ON_TIME' THEN 1 ELSE 0 END) AS completed_on_time
FROM 
    office o
JOIN 
    case_rec cr ON o.id = cr.office_id
JOIN 
    stage s ON cr.id = s.case_id
WHERE 
    s.result_cd IN ('COMPLETED_LATE', 'COMPLETED_ON_TIME')
GROUP BY 
    o.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: ищет результаты COMPLETED_LATE и COMPLETED_ON_TIME, которых нет

## 20. public_services/gov2-039 ru/1

ловушка: the share is of two aggregates over the same group, and the numerator carries two conditions at once; an integer division returns zero here, the ratio has to be taken in floating point; the question asks which, so the share is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT o.title FROM case_rec c JOIN office o ON o.id = c.office_id GROUP BY o.title ORDER BY SUM(CASE WHEN c.closed_at IS NULL AND c.due_dt < '2026-11-02' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) DESC, o.title LIMIT 1
    ('Northport east',)

ответ модели:
    SELECT o.title
FROM office o
JOIN case_rec c ON o.id = c.office_id
WHERE c.dt_sub = '2026-11-02'
GROUP BY o.id
ORDER BY COUNT(c.id) DESC
LIMIT 1
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: фильтрует по дате подачи вместо просрочки, выдача пустая
