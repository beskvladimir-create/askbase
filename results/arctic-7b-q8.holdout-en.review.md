# Ручной разбор провалов: arctic-7b-q8.holdout-en.jsonl

Провалов всего: 55 из 96.
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
    SELECT 
    SUM(CASE WHEN dir_cd = 'C' THEN amt_cents ELSE -amt_cents END) / 100.0 AS net_movement
FROM 
    txn
    (-567484.36,)

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
    SELECT *
FROM cust
WHERE id NOT IN (SELECT cust_id FROM acct)
    (28, 'Mark Novak', '2020-05-18', 1, 'Lowick')
    (39, 'Mark Marek', '2023-11-14', 1, 'Marden')
    (41, 'Victor Oduya', '2014-02-17', 1, 'Thorne')
    (51, 'Daniel Almeida', '2015-04-18', 2, 'Lowick')
    (54, 'Pavel Oduya', '2026-09-12', 1, 'Thorne')
    (58, 'Mark Marek', '2024-09-04', 1, 'Lowick')
    (59, 'Sofia Varga', '2014-04-06', 1, 'Avelin')
    (60, 'Victor Reiner', '2020-02-06', 1, 'Thorne')
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
    SELECT AVG(rate_bp / 100.0) AS mean_rate_bp
FROM loan
WHERE closed_at IS NULL
    (11.487196261682245,)

ошибка исполнения: нет

вердикт: evaluator
заметка: расхождение в последнем бите после AVG, ответ по сути верен

## 4. hr/hr-002 en/1

ловушка: 'working' is status_cd = 1, not left_at IS NULL; somebody on unpaid leave has no leaving date and is not working
вопрос:  Count the employees whose current status is working.

эталон:
    SELECT COUNT(*) AS n FROM emp WHERE status_cd = 1
    (186,)

ответ модели:
    SELECT COUNT(*) AS working_count
FROM emp
WHERE status_cd = 'WORKING'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 5. hr/hr-004 en/0

ловушка: department name lives in dept; status is a code
вопрос:  How many working people are in each department, by department name?

эталон:
    SELECT d.title, COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 GROUP BY d.title ORDER BY n DESC, d.title
    ('Support', 35)
    ('Operations', 34)
    ('Engineering', 32)
    ('Data', 31)
    ('Finance', 28)
    ('Platform', 26)

ответ модели:
    SELECT 
  d.title AS department_name,
  COUNT(e.id) AS total_working_people
FROM 
  emp e
INNER JOIN 
  dept d ON e.dept_id = d.id
WHERE 
  e.status_cd = 'WORKING'
GROUP BY 
  d.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 6. hr/hr-008 en/0

ловушка: DISTINCT person, not a count of pay rows; HAVING on the distinct count, which RedSQL found models get wrong most often
вопрос:  Which currencies are more than two people paid in?

эталон:
    SELECT c.title AS title, COUNT(DISTINCT p.emp_id) AS people FROM pay_hist p JOIN cur_ref c ON c.cd = p.cur_cd GROUP BY c.title HAVING COUNT(DISTINCT p.emp_id) > 2 ORDER BY people DESC, c.title
    ('EUR', 206)
    ('USD', 115)

ответ модели:
    SELECT cur_cd
FROM pay_hist
GROUP BY cur_cd
HAVING COUNT(emp_id) > 2
    (1,)
    (2,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 7. logistics/log-005 en/1

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  List the shipments that never had an incident recorded against them.

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

## 8. logistics/log-007 en/1

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
  sh.dst_cd AS destination_code,
  COUNT(DISTINCT l.carr_id) AS unique_carriers
FROM 
  leg l
JOIN 
  shp sh ON l.shp_id = sh.id
GROUP BY 
  sh.dst_cd
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

## 9. manufacturing/mfg-001 en/1

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

## 10. manufacturing/mfg-002 en/0

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  How much was scrapped in total, converted to the base unit?

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(m.qty * ur.to_base) AS total_quantity
FROM mov m
JOIN mov_kind_ref mk ON m.kind_cd = mk.cd
JOIN unit_ref ur ON m.unit_cd = ur.cd
WHERE mk.title = 'SCRAP'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 11. manufacturing/mfg-002 en/1

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Add up the scrapped quantity, bringing every row to the same unit first.

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(m.qty * u.to_base) AS total_scrapped_quantity
FROM mov m
JOIN mov_kind_ref mk ON m.kind_cd = mk.cd
JOIN unit_ref u ON m.unit_cd = u.cd
WHERE mk.title = 'SCRAP'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 12. manufacturing/mfg-005 en/0

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
    SELECT m.id, m.part_id, m.line_id, m.dt_op, m.recorded_at, m.qty, m.unit_cd, m.kind_cd
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

## 13. manufacturing/mfg-005 en/1

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
    SELECT m.*
FROM mov m
LEFT JOIN defect d ON m.id = d.mov_id
WHERE d.mov_id IS NULL
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

## 14. manufacturing/mfg-006 en/0

ловушка: the shift belongs to the line, not to the defect; two joins to reach it
вопрос:  How many defects were found on each shift?

эталон:
    SELECT s.title AS shift, COUNT(*) AS defects FROM defect d JOIN mov m ON m.id = d.mov_id JOIN line l ON l.id = m.line_id JOIN shift_ref s ON s.cd = l.shift_cd GROUP BY s.title ORDER BY defects DESC, s.title
    ('night', 185)
    ('day', 135)

ответ модели:
    SELECT 
  s.title AS shift_title,
  COUNT(d.id) AS defect_count
FROM 
  defect d
  INNER JOIN shift_ref s ON strftime('%H', d.found_at) = strftime('%H', s.cd)
GROUP BY 
  s.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 15. medicine/med-001 en/0

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

## 16. medicine/med-002 en/0

ловушка: 'discharged' is status_cd = 2, not the discharged column
вопрос:  Which five doctors discharged the most patients?

эталон:
    SELECT d.full_name, COUNT(*) AS n FROM enc e JOIN doc d ON d.id = e.doc_id WHERE e.status_cd = 2 GROUP BY d.full_name ORDER BY n DESC, d.full_name LIMIT 5
    ('Artem Petran', 35)
    ('Olga Almeida', 23)
    ('Anna Varga', 21)
    ('Artem Kristof', 21)
    ('Irina Varga', 21)

ответ модели:
    SELECT d.full_name, COUNT(e.discharged) AS discharged_count
FROM doc d
JOIN enc e ON d.id = e.doc_id
WHERE e.discharged IS NOT NULL
GROUP BY d.full_name
ORDER BY discharged_count DESC
LIMIT 5
    ('Artem Petran', 36)
    ('Olga Almeida', 24)
    ('Sofia Kristof', 22)
    ('Irina Varga', 22)
    ('Anna Varga', 22)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 17. public_services/gov-004 en/0

ловушка: the submission date is split across the legacy pair dt_sub/submitted_at
вопрос:  How many cases were submitted in the second quarter of 2026?

эталон:
    SELECT COUNT(*) AS n FROM case_rec WHERE COALESCE(dt_sub, submitted_at) >= '2026-04-01' AND COALESCE(dt_sub, submitted_at) < '2026-07-01'
    (124,)

ответ модели:
    SELECT COUNT(*) AS total_cases
FROM case_rec
WHERE dt_sub BETWEEN '2026-04-01' AND '2026-06-30'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 18. public_services/gov-004 en/1

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

## 19. public_services/gov-006 en/0

ловушка: result_cd is NULL for a stage still open, and NULL is not a code; an inner join is correct here, which is the opposite of gov-005
вопрос:  How many decided stages ended in each result?

эталон:
    SELECT r.title AS result, COUNT(*) AS n FROM stage s JOIN result_ref r ON r.cd = s.result_cd GROUP BY r.title ORDER BY n DESC, r.title
    ('approved', 743)
    ('refused', 278)
    ('withdrawn', 122)

ответ модели:
    SELECT 
    rr.title AS result_title,
    COUNT(s.stage_id) AS decided_stages_count
FROM 
    stage s
JOIN 
    result_ref rr ON s.result_cd = rr.cd
WHERE 
    s.result_cd IS NOT NULL
GROUP BY 
    rr.title
    ОШИБКА: OperationalError: no such column: s.stage_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 20. public_services/gov-008 en/1

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Show the applicants with three or more cases, and how many each has.

эталон:
    SELECT a.full_name, COUNT(*) AS cases FROM case_rec c JOIN applicant a ON a.id = c.applicant_id GROUP BY a.id, a.full_name HAVING COUNT(*) > 2 ORDER BY cases DESC, a.full_name
    ('Alina Oduya', 9)
    ('Anna Soto', 9)
    ('Anna Almeida', 8)
    ('Elena Oduya', 8)
    ('Elena Varga', 8)
    ('Mark Kristof', 8)
    ('Timur Linde', 8)
    ('Victor Linde', 8)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT a.full_name, COUNT(c.id) AS case_count
FROM applicant a
JOIN case_rec c ON a.id = c.applicant_id
GROUP BY a.full_name
HAVING COUNT(c.id) >= 3
    ('Alina Bauer', 9)
    ('Alina Benali', 6)
    ('Alina Linde', 10)
    ('Alina Novak', 12)
    ('Alina Oduya', 14)
    ('Alina Reiner', 10)
    ('Alina Soto', 7)
    ('Alina Varga', 10)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям
