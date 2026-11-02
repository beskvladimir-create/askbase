# Ручной разбор провалов: qwen25-coder-7b.holdout-en.jsonl

Провалов всего: 51 из 96.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank-002 en/1

ловушка: direction lives in dir_cd, not in the sign of amt_cents; amounts are minor units and must be divided by 100
вопрос:  Add up the credits, take away the debits, and give the result in whole units rather than minor units.

эталон:
    SELECT SUM(CASE WHEN dir_cd = 2 THEN amt_cents ELSE -amt_cents END) / 100.0 AS net FROM txn
    (-189905.58,)

ответ модели:
    SELECT SUM(CASE WHEN dir_cd = 'C' THEN amt_cents ELSE -amt_cents END) / 100 AS net_amount
FROM txn
    (-567484,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 2. banking/bank-005 en/0

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Which customers hold no account at all?

эталон:
    SELECT c.full_name FROM cust c WHERE NOT EXISTS (SELECT 1 FROM acct a WHERE a.cust_id = c.id) ORDER BY c.full_name
    ('Alina Bauer',)
    ('Alina Benali',)
    ('Alina Kovach',)
    ('Alina Marek',)
    ('Alina Oduya',)
    ('Alina Oduya',)
    ('Alina Reiner',)
    ('Alina Varga',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT id, full_name 
FROM cust 
WHERE id NOT IN (SELECT cust_id FROM acct)
    (28, 'Mark Novak')
    (39, 'Mark Marek')
    (41, 'Victor Oduya')
    (51, 'Daniel Almeida')
    (54, 'Pavel Oduya')
    (58, 'Mark Marek')
    (59, 'Sofia Varga')
    (60, 'Victor Reiner')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен

## 3. banking/bank-006 en/1

ловушка: rate_bp is basis points, so the answer is a hundredth of the stored number; an open loan is closed_at IS NULL, there is no status column here
вопрос:  For loans that have not been closed yet, give the mean rate in per cent.

эталон:
    SELECT AVG(rate_bp) / 100.0 AS avg_rate_pct FROM loan WHERE closed_at IS NULL
    (11.487196261682243,)

ответ модели:
    SELECT AVG(rate_bp) AS mean_rate_bp
FROM loan
WHERE closed_at IS NULL
    (1148.7196261682243,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 4. banking/bank-007 en/0

ловушка: DISTINCT customer, not account count; 'active' is status_cd = 1, and residency is a second coded column
вопрос:  How many distinct customers hold an active account, by residency?

эталон:
    SELECT r.title AS residency, COUNT(DISTINCT a.cust_id) AS customers FROM acct a JOIN cust c ON c.id = a.cust_id JOIN resid_ref r ON r.cd = c.resid_cd WHERE a.status_cd = 1 GROUP BY r.title ORDER BY customers DESC, r.title
    ('resident', 189)
    ('non-resident', 34)

ответ модели:
    SELECT r.title AS residency, COUNT(DISTINCT c.id) AS distinct_customers
FROM cust c
JOIN resid_ref r ON c.resid_cd = r.cd
JOIN acct a ON c.id = a.cust_id
JOIN acct_status_ref asr ON a.status_cd = asr.cd
WHERE asr.title = 'Active'
GROUP BY r.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 5. hr/hr-002 en/0

ловушка: 'working' is status_cd = 1, not left_at IS NULL; somebody on unpaid leave has no leaving date and is not working
вопрос:  How many people work here right now?

эталон:
    SELECT COUNT(*) AS n FROM emp WHERE status_cd = 1
    (186,)

ответ модели:
    SELECT COUNT(*) 
FROM emp 
WHERE status_cd = 'Active'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 6. hr/hr-003 en/1

ловушка: salary is effective-dated; the current one is the latest from_dt per person; amounts are minor units and must be divided by 100
вопрос:  Give me the top five by the salary in force today, in whole units.

эталон:
    SELECT e.full_name, p.amount_minor / 100.0 AS pay FROM emp e JOIN pay_hist p ON p.emp_id = e.id WHERE p.from_dt = ( SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id ) ORDER BY pay DESC, e.full_name LIMIT 5
    ('Irina Oduya', 10996.0)
    ('Victor Kristof', 10988.0)
    ('Artem Oduya', 10948.0)
    ('Daniel Almeida', 10890.0)
    ('Victor Marek', 10856.0)

ответ модели:
    SELECT e.full_name, p.amount_minor AS salary
FROM emp e
JOIN pay_hist p ON e.id = p.emp_id
WHERE p.from_dt = (SELECT MAX(from_dt) FROM pay_hist WHERE emp_id = e.id)
AND p.amount_minor = (p.amount_minor / 1) * 1
ORDER BY p.amount_minor DESC
LIMIT 5
    ('Irina Oduya', 1099600)
    ('Victor Kristof', 1098800)
    ('Artem Oduya', 1094800)
    ('Daniel Almeida', 1089000)
    ('Victor Marek', 1085600)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 7. hr/hr-004 en/1

ловушка: department name lives in dept; status is a code
вопрос:  Per department, count the staff currently working there.

эталон:
    SELECT d.title, COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 GROUP BY d.title ORDER BY n DESC, d.title
    ('Support', 35)
    ('Operations', 34)
    ('Engineering', 32)
    ('Data', 31)
    ('Finance', 28)
    ('Platform', 26)

ответ модели:
    SELECT d.title AS department_title, COUNT(e.id) AS staff_count
FROM dept d
JOIN emp e ON d.id = e.dept_id
WHERE e.status_cd = 'A'
GROUP BY d.id, d.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 8. hr/hr-005 en/0

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Which employees have no salary record at all?

эталон:
    SELECT e.full_name FROM emp e WHERE NOT EXISTS (SELECT 1 FROM pay_hist p WHERE p.emp_id = e.id) ORDER BY e.full_name
    ('Alina Novak',)
    ('Anna Almeida',)
    ('Anna Hale',)
    ('Anna Petran',)
    ('Artem Almeida',)
    ('Artem Linde',)
    ('Artem Marek',)
    ('Artem Reiner',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT e.id, e.full_name
FROM emp e
LEFT JOIN pay_hist p ON e.id = p.emp_id
WHERE p.id IS NULL
    (60, 'Igor Benali')
    (77, 'Anna Almeida')
    (147, 'Irina Linde')
    (184, 'Artem Marek')
    (221, 'Igor Kovach')
    (222, 'Artem Soto')
    (223, 'Irina Benali')
    (224, 'Victor Benali')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен

## 9. logistics/log-002 en/1

ловушка: one lookup table joined twice under two aliases; a single join answers about one end of the route and looks correct
вопрос:  Name the top five routes, giving the place each shipment left from and the place it was going to.

эталон:
    SELECT o.title AS origin, d.title AS destination, COUNT(*) AS n FROM shp s JOIN loc_ref o ON o.cd = s.org_cd JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY o.title, d.title ORDER BY n DESC, o.title, d.title LIMIT 5
    ('Kesling', 'Thorne', 21)
    ('Eastvale', 'Lowick', 20)
    ('Northport', 'Harrow', 20)
    ('Harrow', 'Lowick', 18)
    ('Marden', 'Lowick', 18)

ответ модели:
    SELECT 
    org_cd AS origin, 
    dst_cd AS destination, 
    COUNT(*) AS shipment_count
FROM 
    shp
GROUP BY 
    org_cd, 
    dst_cd
ORDER BY 
    shipment_count DESC
LIMIT 5
    (7, 5, 21)
    (1, 8, 20)
    (2, 4, 20)
    (3, 4, 18)
    (8, 4, 18)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 10. logistics/log-006 en/0

ловушка: 'delivered' is status_cd = 2, not delivered_at IS NOT NULL; a lost shipment can carry a delivery attempt date, so the two disagree
вопрос:  How many shipments are delivered?

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 2
    (503,)

ответ модели:
    SELECT COUNT(*) FROM shp WHERE status_cd = (SELECT cd FROM status_ref WHERE title = 'Delivered')
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 11. logistics/log-007 en/0

ловушка: DISTINCT carrier, not leg count; the destination end of the route, not the origin
вопрос:  How many distinct carriers serve each destination?

эталон:
    SELECT l.title AS destination, COUNT(DISTINCT g.carr_id) AS carriers FROM leg g JOIN shp s ON s.id = g.shp_id JOIN loc_ref l ON l.cd = s.dst_cd GROUP BY l.title ORDER BY carriers DESC, l.title
    ('Avelin', 45)
    ('Eastvale', 45)
    ('Kesling', 45)
    ('Lowick', 45)
    ('Marden', 45)
    ('Northport', 45)
    ('Thorne', 45)
    ('Harrow', 43)

ответ модели:
    SELECT dst_cd, COUNT(DISTINCT carr_id) AS distinct_carriers
FROM shp
JOIN leg ON shp.id = leg.shp_id
GROUP BY dst_cd
    (1, 45)
    (2, 45)
    (3, 45)
    (4, 45)
    (5, 45)
    (6, 45)
    (7, 45)
    (8, 43)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 12. logistics/log-007 en/1

ловушка: DISTINCT carrier, not leg count; the destination end of the route, not the origin
вопрос:  Per destination, count the unique carriers that have carried a leg there.

эталон:
    SELECT l.title AS destination, COUNT(DISTINCT g.carr_id) AS carriers FROM leg g JOIN shp s ON s.id = g.shp_id JOIN loc_ref l ON l.cd = s.dst_cd GROUP BY l.title ORDER BY carriers DESC, l.title
    ('Avelin', 45)
    ('Eastvale', 45)
    ('Kesling', 45)
    ('Lowick', 45)
    ('Marden', 45)
    ('Northport', 45)
    ('Thorne', 45)
    ('Harrow', 43)

ответ модели:
    SELECT dst_cd, COUNT(DISTINCT carr_id) AS unique_carriers
FROM leg
GROUP BY dst_cd
    ОШИБКА: OperationalError: no such column: dst_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 13. manufacturing/mfg-003 en/0

ловушка: the date is split across the legacy pair dt_op/recorded_at
вопрос:  How many movements fall in the first quarter of 2026?

эталон:
    SELECT COUNT(*) AS n FROM mov WHERE COALESCE(dt_op, recorded_at) >= '2026-01-01' AND COALESCE(dt_op, recorded_at) < '2026-04-01'
    (85,)

ответ модели:
    SELECT COUNT(*) 
FROM mov 
WHERE dt_op BETWEEN '2026-01-01' AND '2026-03-31'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 14. manufacturing/mfg-003 en/1

ловушка: the date is split across the legacy pair dt_op/recorded_at
вопрос:  Count the movements dated between January and March 2026 inclusive.

эталон:
    SELECT COUNT(*) AS n FROM mov WHERE COALESCE(dt_op, recorded_at) >= '2026-01-01' AND COALESCE(dt_op, recorded_at) < '2026-04-01'
    (85,)

ответ модели:
    SELECT COUNT(*) 
FROM mov 
WHERE dt_op BETWEEN '2026-01-01' AND '2026-03-31'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 15. manufacturing/mfg-004 en/0

ловушка: the price is effective-dated; the join is on a range, not on equality; valid_to NULL means still in force; quantities need converting and the price is in minor units
вопрос:  Which three parts cost the most in total, at the price in force on each movement?

эталон:
    SELECT p.title, SUM(m.qty * u.to_base * pp.minor / 100.0) AS cost FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id AND COALESCE(m.dt_op, m.recorded_at) >= pp.valid_from AND (pp.valid_to IS NULL OR COALESCE(m.dt_op, m.recorded_at) < pp.valid_to) GROUP BY p.title ORDER BY cost DESC, p.title LIMIT 3
    ('bracket', 9447027.370000001)
    ('shaft', 9250141.08)
    ('bushing', 5679813.23)

ответ модели:
    SELECT p.id, p.title, SUM(pp.minor * m.qty) AS total_cost
FROM part p
JOIN mov m ON p.id = m.part_id
JOIN part_price pp ON p.id = pp.part_id AND pp.valid_from <= m.dt_op AND (pp.valid_to IS NULL OR pp.valid_to >= m.dt_op)
GROUP BY p.id, p.title
ORDER BY total_cost DESC
LIMIT 3
    (2, 'shaft', 114747809.25)
    (1, 'bracket', 108580759.49)
    (5, 'bushing', 54691038.88)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 16. manufacturing/mfg-007 en/0

ловушка: DISTINCT part, not a movement count
вопрос:  How many distinct parts are measured in each unit?

эталон:
    SELECT u.title AS unit, COUNT(DISTINCT m.part_id) AS parts FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd GROUP BY u.title ORDER BY parts DESC, u.title
    ('kilogram', 6)
    ('piece', 6)
    ('tonne', 6)

ответ модели:
    SELECT ur.title AS unit_title, COUNT(DISTINCT p.id) AS distinct_parts_count
FROM unit_ref ur
JOIN line l ON ur.cd = l.shift_cd
JOIN mov m ON l.id = m.line_id
JOIN part p ON m.part_id = p.id
GROUP BY ur.title
    ('kilogram', 6)
    ('piece', 6)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 17. manufacturing/mfg-008 en/0

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Which parts have more than ten defects?

эталон:
    SELECT p.title, COUNT(*) AS defects FROM defect d JOIN mov m ON m.id = d.mov_id JOIN part p ON p.id = m.part_id GROUP BY p.id, p.title HAVING COUNT(*) > 10 ORDER BY defects DESC, p.title
    ('bracket', 128)
    ('shaft', 83)
    ('gearwheel', 41)
    ('plate', 39)
    ('bushing', 22)

ответ модели:
    SELECT p.id, p.title
FROM part p
JOIN mov m ON p.id = m.part_id
JOIN defect d ON m.id = d.mov_id
GROUP BY p.id, p.title
HAVING COUNT(d.id) > 10
    (1, 'bracket')
    (2, 'shaft')
    (3, 'plate')
    (4, 'gearwheel')
    (5, 'bushing')

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 18. medicine/med-008 en/0

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Which patients were admitted more than twice?

эталон:
    SELECT p.full_name, COUNT(*) AS encounters FROM enc e JOIN pat p ON p.id = e.pat_id GROUP BY p.id, p.full_name HAVING COUNT(*) > 2 ORDER BY encounters DESC, p.full_name
    ('Nina Soto', 8)
    ('Vera Hale', 8)
    ('Daniel Linde', 7)
    ('Daniel Oduya', 7)
    ('Igor Kristof', 7)
    ('Victor Marek', 7)
    ('Anna Varga', 6)
    ('Artem Bauer', 6)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT p.id, p.full_name
FROM pat p
JOIN enc e ON p.id = e.pat_id
GROUP BY p.id, p.full_name
HAVING COUNT(e.id) > 2
    (3, 'Mark Reiner')
    (7, 'Timur Varga')
    (9, 'Pavel Marek')
    (10, 'Igor Marek')
    (11, 'Mark Bauer')
    (17, 'Pavel Marek')
    (19, 'Artem Kovach')
    (22, 'Timur Almeida')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 19. medicine/med-008 en/1

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Show patients with three or more encounters, and how many each had.

эталон:
    SELECT p.full_name, COUNT(*) AS encounters FROM enc e JOIN pat p ON p.id = e.pat_id GROUP BY p.id, p.full_name HAVING COUNT(*) > 2 ORDER BY encounters DESC, p.full_name
    ('Nina Soto', 8)
    ('Vera Hale', 8)
    ('Daniel Linde', 7)
    ('Daniel Oduya', 7)
    ('Igor Kristof', 7)
    ('Victor Marek', 7)
    ('Anna Varga', 6)
    ('Artem Bauer', 6)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT p.id, p.full_name, COUNT(e.id) AS encounter_count
FROM pat p
JOIN enc e ON p.id = e.pat_id
GROUP BY p.id, p.full_name
HAVING COUNT(e.id) >= 3
    (3, 'Mark Reiner', 3)
    (7, 'Timur Varga', 3)
    (9, 'Pavel Marek', 3)
    (10, 'Igor Marek', 3)
    (11, 'Mark Bauer', 3)
    (17, 'Pavel Marek', 5)
    (19, 'Artem Kovach', 3)
    (22, 'Timur Almeida', 3)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен

## 20. public_services/gov-004 en/1

ловушка: the submission date is split across the legacy pair dt_sub/submitted_at
вопрос:  Count the cases lodged between April and June 2026 inclusive.

эталон:
    SELECT COUNT(*) AS n FROM case_rec WHERE COALESCE(dt_sub, submitted_at) >= '2026-04-01' AND COALESCE(dt_sub, submitted_at) < '2026-07-01'
    (124,)

ответ модели:
    SELECT COUNT(*) 
FROM case_rec 
WHERE dt_sub BETWEEN '2026-04-01' AND '2026-06-30'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям
