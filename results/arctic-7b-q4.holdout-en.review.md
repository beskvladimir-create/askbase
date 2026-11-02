# Ручной разбор провалов: arctic-7b-q4.holdout-en.jsonl

Провалов всего: 53 из 96.
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
    SELECT SUM(CASE WHEN dir_cd = 'D' THEN amt_cents ELSE -amt_cents END) / 100.0 AS net_movement
FROM txn
    (-567484.36,)

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
    SELECT AVG(rate_bp / 100.0) AS mean_rate_bp
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
    CASE 
        WHEN r.title = 'Resident' THEN 'Residents'
        ELSE 'Non-Residents'
    END AS customer_type,
    COUNT(DISTINCT c.id) AS customer_count
FROM 
    cust c
JOIN 
    acct a ON c.id = a.cust_id
JOIN 
    resid_ref r ON c.resid_cd = r.cd
WHERE 
    a.status_cd = 'A'
GROUP BY 
    customer_type
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 4. hr/hr-001 en/1

ловушка: status is a code, needs the lookup join
вопрос:  Break the staff list down by status and give me the counts.

эталон:
    SELECT s.title AS status, COUNT(*) AS n FROM emp e JOIN emp_status_ref s ON s.cd = e.status_cd GROUP BY s.title ORDER BY n DESC, s.title
    ('working', 186)
    ('left', 55)
    ('unpaid leave', 19)

ответ модели:
    SELECT status_cd, COUNT(*) AS employee_count
FROM emp
GROUP BY status_cd
    (1, 186)
    (2, 19)
    (3, 55)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 5. hr/hr-003 en/1

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
    SELECT 
    e.id AS employee_id,
    ROUND(ph.amount_minor) AS salary_minor_whole
FROM 
    pay_hist ph
JOIN 
    emp e ON ph.emp_id = e.id
WHERE 
    ph.from_dt = DATE('now')
ORDER BY 
    salary_minor_whole DESC
LIMIT 5
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 6. hr/hr-007 en/0

ловушка: kind is a code; SUM over days, not a row count
вопрос:  How many days were taken for each kind of absence?

эталон:
    SELECT k.title AS kind, SUM(a.days) AS days FROM absence a JOIN absence_kind_ref k ON k.cd = a.kind_cd GROUP BY k.title ORDER BY days DESC, k.title
    ('annual leave', 2697)
    ('sick', 1103)
    ('training', 706)

ответ модели:
    SELECT kind_cd, SUM(days) AS total_days
FROM absence
GROUP BY kind_cd
    (1, 2697)
    (2, 1103)
    (3, 706)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

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

## 8. logistics/log-005 en/0

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Which shipments had no incident at all?

эталон:
    SELECT s.id FROM shp s WHERE NOT EXISTS (SELECT 1 FROM inc i WHERE i.shp_id = s.id) ORDER BY s.id
    (2,)
    (7,)
    (8,)
    (19,)
    (22,)
    (23,)
    (26,)
    (33,)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT s.*
FROM shp s
LEFT JOIN inc i ON s.id = i.shp_id
WHERE i.id IS NULL
    (2, 25, 7, 3, None, '2026-01-13', None, 1, 4282)
    (7, 36, 4, 1, None, '2026-02-17', '2026-03-10', 2, 10349)
    (8, 17, 3, 2, None, '2026-09-18', '2026-10-19', 2, 2641)
    (19, 87, 7, 6, None, '2025-12-06', '2026-01-07', 2, 3588)
    (22, 29, 5, 4, None, '2026-01-19', '2026-02-13', 2, 703)
    (23, 32, 5, 1, '2025-05-14', None, '2025-05-23', 2, 13143)
    (26, 50, 6, 8, None, '2026-10-13', '2026-10-25', 2, 2667)
    (33, 22, 3, 8, None, '2026-08-11', None, 1, 21469)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен

## 9. logistics/log-006 en/1

ловушка: 'delivered' is status_cd = 2, not delivered_at IS NOT NULL; a lost shipment can carry a delivery attempt date, so the two disagree
вопрос:  Count the shipments whose current state is delivered.

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 2
    (503,)

ответ модели:
    SELECT COUNT(*) AS total_delivered_shipments
FROM shp
WHERE status_cd = 'delivered'
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
    SELECT 
    s.dst_cd AS destination,
    COUNT(DISTINCT l.carr_id) AS unique_carriers
FROM 
    leg l
JOIN 
    shp s ON l.shp_id = s.id
GROUP BY 
    s.dst_cd
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
    SELECT 
  s.id AS shipment_id
FROM 
  shp s
INNER JOIN 
  leg l ON s.id = l.shp_id
GROUP BY 
  s.id
HAVING 
  SUM(l.dist_km) > 3000
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

## 12. manufacturing/mfg-001 en/1

ловушка: kind is a code, needs the lookup join
вопрос:  Break the movements down by their type and give me the counts.

эталон:
    SELECT k.title AS kind, COUNT(*) AS n FROM mov m JOIN mov_kind_ref k ON k.cd = m.kind_cd GROUP BY k.title ORDER BY n DESC, k.title
    ('issue', 403)
    ('receipt', 380)
    ('scrap', 117)

ответ модели:
    SELECT kind_cd, COUNT(*) AS movement_count
FROM mov
GROUP BY kind_cd
    (1, 403)
    (2, 380)
    (3, 117)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 13. manufacturing/mfg-004 en/1

ловушка: the price is effective-dated; the join is on a range, not on equality; valid_to NULL means still in force; quantities need converting and the price is in minor units
вопрос:  For every part, value its movements at the price valid on the day it moved, and name the three largest.

эталон:
    SELECT p.title, SUM(m.qty * u.to_base * pp.minor / 100.0) AS cost FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id AND COALESCE(m.dt_op, m.recorded_at) >= pp.valid_from AND (pp.valid_to IS NULL OR COALESCE(m.dt_op, m.recorded_at) < pp.valid_to) GROUP BY p.title ORDER BY cost DESC, p.title LIMIT 3
    ('bracket', 9447027.370000001)
    ('shaft', 9250141.08)
    ('bushing', 5679813.23)

ответ модели:
    WITH PartValueCTE AS (
    SELECT
        p.title AS part_title,
        SUM(m.qty * pp.minor) AS total_value
    FROM
        part p
    JOIN
        mov m ON p.id = m.part_id
    JOIN
        part_price pp ON p.id = pp.part_id AND m.recorded_at BETWEEN pp.valid_from AND pp.valid_to
    GROUP BY
        p.title
),
RankedParts AS (
    SELECT
        part_title,
        total_value,
        ROW_NUMBER() OVER (ORDER BY total_value DESC) AS rank
    FROM
        PartValueCTE
)
SELECT
    part_title,
    total_value
FROM
    RankedParts
WHERE
    rank <= 3
    ('bracket', 7281702.12)
    ('shaft', 6819547.2)
    ('gearwheel', 4528854.0)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 14. manufacturing/mfg-005 en/0

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
    SELECT m.*
FROM mov m
LEFT JOIN defect d ON m.id = d.mov_id
WHERE d.id IS NULL
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

## 15. manufacturing/mfg-005 en/1

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  List the movements that never had a defect found.

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
    SELECT 
  m.id AS movement_id,
  m.part_id,
  m.line_id,
  m.dt_op,
  m.recorded_at,
  m.qty,
  m.unit_cd,
  m.kind_cd
FROM 
  mov m
  LEFT JOIN defect d ON m.id = d.mov_id
WHERE 
  d.id IS NULL
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

## 16. medicine/med-001 en/0

ловушка: sex is a code, needs the lookup join
вопрос:  How many patients are there of each sex?

эталон:
    SELECT r.title AS sex, COUNT(*) AS n FROM pat p JOIN sex_ref r ON r.cd = p.sex_cd GROUP BY r.title ORDER BY n DESC
    ('female', 201)
    ('male', 199)

ответ модели:
    SELECT sex_cd, COUNT(*) AS patient_count
FROM pat
GROUP BY sex_cd
    (1, 199)
    (2, 201)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 17. medicine/med-001 en/1

ловушка: sex is a code, needs the lookup join
вопрос:  Break the patient list down by sex and give me the counts.

эталон:
    SELECT r.title AS sex, COUNT(*) AS n FROM pat p JOIN sex_ref r ON r.cd = p.sex_cd GROUP BY r.title ORDER BY n DESC
    ('female', 201)
    ('male', 199)

ответ модели:
    SELECT sex_cd, COUNT(*) AS patient_count
FROM pat
GROUP BY sex_cd
    (1, 199)
    (2, 201)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 18. medicine/med-008 en/1

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
    SELECT p.full_name, COUNT(e.id) AS encounter_count
FROM pat p
INNER JOIN enc e ON p.id = e.pat_id
GROUP BY p.full_name
HAVING COUNT(e.id) >= 3
    ('Alina Almeida', 6)
    ('Alina Bauer', 3)
    ('Alina Benali', 6)
    ('Alina Kovach', 4)
    ('Alina Kristof', 4)
    ('Alina Linde', 3)
    ('Alina Marek', 8)
    ('Alina Novak', 4)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 19. public_services/gov-003 en/0

ловушка: people reapply, so a case count and a people count differ
вопрос:  How many different people have applied at all?

эталон:
    SELECT COUNT(DISTINCT applicant_id) AS people FROM case_rec
    (230,)

ответ модели:
    SELECT COUNT(DISTINCT id) AS total_applicants
FROM applicant
    (300,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 20. public_services/gov-006 en/0

ловушка: result_cd is NULL for a stage still open, and NULL is not a code; an inner join is correct here, which is the opposite of gov-005
вопрос:  How many decided stages ended in each result?

эталон:
    SELECT r.title AS result, COUNT(*) AS n FROM stage s JOIN result_ref r ON r.cd = s.result_cd GROUP BY r.title ORDER BY n DESC, r.title
    ('approved', 743)
    ('refused', 278)
    ('withdrawn', 122)

ответ модели:
    SELECT rr.title, COUNT(s.stage_id) AS decided_stages_count
FROM stage s
JOIN result_ref rr ON s.result_cd = rr.cd
WHERE s.result_cd IS NOT NULL
GROUP BY rr.title
    ОШИБКА: OperationalError: no such column: s.stage_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился
