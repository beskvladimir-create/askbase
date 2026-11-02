# Ручной разбор провалов: qwen25-coder-14b.holdout-en.jsonl

Провалов всего: 49 из 96.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank-002 en/0

ловушка: direction lives in dir_cd, not in the sign of amt_cents; amounts are minor units and must be divided by 100
вопрос:  What is the net movement across all transactions, in currency units?

эталон:
    SELECT SUM(CASE WHEN dir_cd = 2 THEN amt_cents ELSE -amt_cents END) / 100.0 AS net FROM txn
    (-189905.58,)

ответ модели:
    SELECT SUM(amt_cents / 100.0) AS net_movement
FROM txn
    (567484.36,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 2. banking/bank-006 en/1

ловушка: rate_bp is basis points, so the answer is a hundredth of the stored number; an open loan is closed_at IS NULL, there is no status column here
вопрос:  For loans that have not been closed yet, give the mean rate in per cent.

эталон:
    SELECT AVG(rate_bp) / 100.0 AS avg_rate_pct FROM loan WHERE closed_at IS NULL
    (11.487196261682243,)

ответ модели:
    SELECT AVG(rate_bp / 100.0) AS mean_rate_percent
FROM loan
WHERE closed_at IS NULL
    (11.487196261682245,)

ошибка исполнения: нет

вердикт: evaluator
заметка: расхождение в последнем бите после AVG, ответ по сути верен

## 3. banking/bank-007 en/1

ловушка: DISTINCT customer, not account count; 'active' is status_cd = 1, and residency is a second coded column
вопрос:  Split holders of active accounts into residents and non-residents, counting each customer once.

эталон:
    SELECT r.title AS residency, COUNT(DISTINCT a.cust_id) AS customers FROM acct a JOIN cust c ON c.id = a.cust_id JOIN resid_ref r ON r.cd = c.resid_cd WHERE a.status_cd = 1 GROUP BY r.title ORDER BY customers DESC, r.title
    ('resident', 189)
    ('non-resident', 34)

ответ модели:
    SELECT 
    r.title AS residency,
    COUNT(DISTINCT a.cust_id) AS customer_count
FROM 
    acct a
JOIN 
    cust c ON a.cust_id = c.id
JOIN 
    resid_ref r ON c.resid_cd = r.cd
JOIN 
    acct_status_ref s ON a.status_cd = s.cd
WHERE 
    s.title = 'Active'
GROUP BY 
    r.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 4. hr/hr-003 en/1

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
    SELECT e.full_name, p.amount_minor / 100 AS salary
FROM emp e
JOIN pay_hist p ON e.id = p.emp_id
WHERE p.from_dt = (
    SELECT MAX(ph.from_dt)
    FROM pay_hist ph
    WHERE ph.emp_id = e.id
)
ORDER BY salary DESC
LIMIT 5
    ('Irina Oduya', 10996)
    ('Victor Kristof', 10988)
    ('Artem Oduya', 10948)
    ('Daniel Almeida', 10890)
    ('Victor Marek', 10856)

ошибка исполнения: нет

вердикт: evaluator
заметка: сравнение по repr: 10996 против 10996.0, ответ по сути верен

## 5. hr/hr-006 en/1

ловушка: the same table joined twice under two aliases, through mgr_id
вопрос:  Name the top five people by how many staff report straight to them.

эталон:
    SELECT m.full_name AS manager, COUNT(*) AS reports FROM emp e JOIN emp m ON m.id = e.mgr_id GROUP BY m.id, m.full_name ORDER BY reports DESC, m.full_name LIMIT 5
    ('Artem Oduya', 11)
    ('Irina Bauer', 10)
    ('Sofia Linde', 10)
    ('Alina Linde', 9)
    ('Daniel Kovach', 9)

ответ модели:
    SELECT e.full_name, COUNT(emp.id) AS direct_reports
FROM emp e
LEFT JOIN emp sub ON e.id = sub.mgr_id
GROUP BY e.id
ORDER BY direct_reports DESC
LIMIT 5
    ОШИБКА: OperationalError: no such column: emp.id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 6. hr/hr-008 en/0

ловушка: DISTINCT person, not a count of pay rows; HAVING on the distinct count, which RedSQL found models get wrong most often
вопрос:  Which currencies are more than two people paid in?

эталон:
    SELECT c.title AS title, COUNT(DISTINCT p.emp_id) AS people FROM pay_hist p JOIN cur_ref c ON c.cd = p.cur_cd GROUP BY c.title HAVING COUNT(DISTINCT p.emp_id) > 2 ORDER BY people DESC, c.title
    ('EUR', 206)
    ('USD', 115)

ответ модели:
    SELECT cur_ref.title
FROM pay_hist
JOIN cur_ref ON pay_hist.cur_cd = cur_ref.cd
GROUP BY pay_hist.cur_cd
HAVING COUNT(DISTINCT pay_hist.emp_id) > 2
    ('EUR',)
    ('USD',)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 7. hr/hr-008 en/1

ловушка: DISTINCT person, not a count of pay rows; HAVING on the distinct count, which RedSQL found models get wrong most often
вопрос:  Per currency, count the distinct people paid in it, keeping only those above two.

эталон:
    SELECT c.title AS title, COUNT(DISTINCT p.emp_id) AS people FROM pay_hist p JOIN cur_ref c ON c.cd = p.cur_cd GROUP BY c.title HAVING COUNT(DISTINCT p.emp_id) > 2 ORDER BY people DESC, c.title
    ('EUR', 206)
    ('USD', 115)

ответ модели:
    SELECT cur_cd, COUNT(DISTINCT emp_id) AS distinct_people_count
FROM pay_hist
GROUP BY cur_cd
HAVING COUNT(DISTINCT emp_id) > 2
    (1, 206)
    (2, 115)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 8. logistics/log-002 en/1

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
    l1.title AS origin, 
    l2.title AS destination
FROM 
    shp s
JOIN 
    loc_ref l1 ON s.org_cd = l1.cd
JOIN 
    loc_ref l2 ON s.dst_cd = l2.cd
GROUP BY 
    s.org_cd, s.dst_cd
ORDER BY 
    COUNT(s.id) DESC
LIMIT 5
    ('Kesling', 'Thorne')
    ('Northport', 'Harrow')
    ('Eastvale', 'Lowick')
    ('Marden', 'Lowick')
    ('Harrow', 'Lowick')

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 9. logistics/log-006 en/0

ловушка: 'delivered' is status_cd = 2, not delivered_at IS NOT NULL; a lost shipment can carry a delivery attempt date, so the two disagree
вопрос:  How many shipments are delivered?

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 2
    (503,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
WHERE status_cd = (SELECT cd FROM status_ref WHERE title = 'Delivered')
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 10. logistics/log-007 en/1

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

## 11. logistics/log-008 en/0

ловушка: HAVING on an aggregate, which RedSQL found models get wrong most often
вопрос:  Which shipments travelled more than three thousand kilometres in total?

эталон:
    SELECT g.shp_id, SUM(g.dist_km) AS km FROM leg g GROUP BY g.shp_id HAVING SUM(g.dist_km) > 3000 ORDER BY km DESC, g.shp_id
    (234, 12097)
    (552, 11822)
    (545, 11459)
    (659, 11313)
    (391, 11159)
    (278, 11090)
    (606, 10943)
    (558, 10837)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT shp.id
FROM shp
JOIN (
    SELECT shp_id, SUM(dist_km) AS total_dist_km
    FROM leg
    GROUP BY shp_id
    HAVING total_dist_km > 3000
) AS long_legs ON shp.id = long_legs.shp_id
    (5,)
    (7,)
    (8,)
    (9,)
    (10,)
    (12,)
    (14,)
    (16,)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 12. manufacturing/mfg-002 en/0

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  How much was scrapped in total, converted to the base unit?

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(qty * to_base) AS total_scrapped
FROM mov
JOIN unit_ref ON mov.unit_cd = unit_ref.cd
JOIN defect ON mov.id = defect.mov_id
WHERE kind_cd = 'scrap'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 13. manufacturing/mfg-003 en/1

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

## 14. manufacturing/mfg-004 en/0

ловушка: the price is effective-dated; the join is on a range, not on equality; valid_to NULL means still in force; quantities need converting and the price is in minor units
вопрос:  Which three parts cost the most in total, at the price in force on each movement?

эталон:
    SELECT p.title, SUM(m.qty * u.to_base * pp.minor / 100.0) AS cost FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id AND COALESCE(m.dt_op, m.recorded_at) >= pp.valid_from AND (pp.valid_to IS NULL OR COALESCE(m.dt_op, m.recorded_at) < pp.valid_to) GROUP BY p.title ORDER BY cost DESC, p.title LIMIT 3
    ('bracket', 9447027.370000001)
    ('shaft', 9250141.08)
    ('bushing', 5679813.23)

ответ модели:
    SELECT p.title, SUM(pp.minor * m.qty) AS total_cost
FROM part p
JOIN mov m ON p.id = m.part_id
JOIN part_price pp ON p.id = pp.part_id
WHERE pp.valid_from <= m.dt_op AND (pp.valid_to IS NULL OR pp.valid_to > m.dt_op)
GROUP BY p.id
ORDER BY total_cost DESC
LIMIT 3
    ('shaft', 114459129.25)
    ('bracket', 108580759.49)
    ('bushing', 54691038.88)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 15. manufacturing/mfg-004 en/1

ловушка: the price is effective-dated; the join is on a range, not on equality; valid_to NULL means still in force; quantities need converting and the price is in minor units
вопрос:  For every part, value its movements at the price valid on the day it moved, and name the three largest.

эталон:
    SELECT p.title, SUM(m.qty * u.to_base * pp.minor / 100.0) AS cost FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id AND COALESCE(m.dt_op, m.recorded_at) >= pp.valid_from AND (pp.valid_to IS NULL OR COALESCE(m.dt_op, m.recorded_at) < pp.valid_to) GROUP BY p.title ORDER BY cost DESC, p.title LIMIT 3
    ('bracket', 9447027.370000001)
    ('shaft', 9250141.08)
    ('bushing', 5679813.23)

ответ модели:
    WITH PartMovements AS (
    SELECT 
        m.id AS mov_id,
        m.part_id,
        m.dt_op,
        p.minor AS price,
        m.qty,
        m.qty * p.minor AS value
    FROM 
        mov m
    JOIN 
        part_price p ON m.part_id = p.part_id
    WHERE 
        m.dt_op BETWEEN p.valid_from AND p.valid_to
),
RankedPartMovements AS (
    SELECT 
        pm.part_id,
        pm.value,
        ROW_NUMBER() OVER (ORDER BY pm.value DESC) AS rank
    FROM 
        PartMovements pm
)
SELECT 
    part_id,
    value
FROM 
    RankedPartMovements
WHERE 
    rank <= 3
    (5, 3020240.0)
    (5, 2996396.0)
    (5, 2760810.0)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 16. manufacturing/mfg-005 en/0

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Which movements had no defect recorded against them?

эталон:
    SELECT m.id FROM mov m WHERE NOT EXISTS (SELECT 1 FROM defect d WHERE d.mov_id = m.id) ORDER BY m.id
    (3,)
    (14,)
    (16,)
    (17,)
    (18,)
    (19,)
    (22,)
    (23,)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT mov.*
FROM mov
LEFT JOIN defect ON mov.id = defect.mov_id
WHERE defect.mov_id IS NULL
    (3, 4, 3, '2024-08-31', None, 9.06, 3, 1)
    (14, 3, 3, '2023-11-11', None, 377.0, 2, 1)
    (16, 1, 4, '2023-12-19', None, 1.73, 3, 1)
    (17, 4, 3, '2023-12-12', None, 107.0, 2, 1)
    (18, 5, 1, '2024-07-04', None, 267.0, 2, 1)
    (19, 4, 4, None, '2026-03-16', 345.0, 2, 1)
    (22, 1, 4, None, '2025-12-14', 65.0, 1, 1)
    (23, 2, 3, None, '2026-04-19', 4.75, 3, 1)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен

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
    SELECT p.title
FROM part p
JOIN mov m ON p.id = m.part_id
JOIN defect d ON m.id = d.mov_id
GROUP BY p.id
HAVING COUNT(d.id) > 10
    ('bracket',)
    ('shaft',)
    ('plate',)
    ('gearwheel',)
    ('bushing',)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 18. medicine/med-001 en/1

ловушка: sex is a code, needs the lookup join
вопрос:  Break the patient list down by sex and give me the counts.

эталон:
    SELECT r.title AS sex, COUNT(*) AS n FROM pat p JOIN sex_ref r ON r.cd = p.sex_cd GROUP BY r.title ORDER BY n DESC
    ('female', 201)
    ('male', 199)

ответ модели:
    SELECT sex_cd, COUNT(*) as count
FROM pat
GROUP BY sex_cd
    (1, 199)
    (2, 201)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 19. medicine/med-008 en/0

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
    SELECT p.full_name
FROM pat p
JOIN enc e ON p.id = e.pat_id
GROUP BY p.id
HAVING COUNT(e.id) > 2
    ('Mark Reiner',)
    ('Timur Varga',)
    ('Pavel Marek',)
    ('Igor Marek',)
    ('Mark Bauer',)
    ('Pavel Marek',)
    ('Artem Kovach',)
    ('Timur Almeida',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 20. medicine/med-008 en/1

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
