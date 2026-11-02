# Ручной разбор провалов: arctic-7b-q8.holdout-ru.jsonl

Провалов всего: 60 из 96.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank-002 ru/0

ловушка: direction lives in dir_cd, not in the sign of amt_cents; amounts are minor units and must be divided by 100
вопрос:  Каков чистый оборот по всем операциям в денежных единицах?

эталон:
    SELECT SUM(CASE WHEN dir_cd = 2 THEN amt_cents ELSE -amt_cents END) / 100.0 AS net FROM txn
    (-189905.58,)

ответ модели:
    SELECT SUM(CASE WHEN dir_cd = 'credit' THEN amt_cents ELSE -amt_cents END) AS net_total_cents
FROM txn
    (-56748436,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 2. banking/bank-004 ru/1

ловушка: the category name lives in mcc_ref, the code alone is not an answer
вопрос:  Назови тройку самых частых категорий трат и число операций в каждой.

эталон:
    SELECT m.title, COUNT(*) AS n FROM txn t JOIN mcc_ref m ON m.code = t.mcc GROUP BY m.title ORDER BY n DESC, m.title LIMIT 3
    ('cash withdrawal', 340)
    ('electronics stores', 312)
    ('restaurants', 302)

ответ модели:
    SELECT dr.title AS category, COUNT(*) AS transaction_count
FROM txn t
JOIN dir_ref dr ON t.dir_cd = dr.cd
GROUP BY dr.title
ORDER BY transaction_count DESC
LIMIT 3
    ('debit', 1612)
    ('credit', 788)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 3. banking/bank-006 ru/0

ловушка: rate_bp is basis points, so the answer is a hundredth of the stored number; an open loan is closed_at IS NULL, there is no status column here
вопрос:  Какая средняя ставка по непогашенным кредитам в процентах?

эталон:
    SELECT AVG(rate_bp) / 100.0 AS avg_rate_pct FROM loan WHERE closed_at IS NULL
    (11.487196261682243,)

ответ модели:
    SELECT AVG(rate_bp / 100.0) AS average_interest_rate
FROM loan
WHERE closed_at IS NULL
    (11.487196261682245,)

ошибка исполнения: нет

вердикт: evaluator
заметка: расхождение в последнем бите после AVG, ответ по сути верен

## 4. banking/bank-008 ru/1

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Покажи клиентов с тремя и более счетами и число счетов у каждого.

эталон:
    SELECT c.full_name, COUNT(*) AS accounts FROM acct a JOIN cust c ON c.id = a.cust_id GROUP BY c.id, c.full_name HAVING COUNT(*) > 2 ORDER BY accounts DESC, c.full_name
    ('Daniel Soto', 7)
    ('Boris Almeida', 6)
    ('Daniel Novak', 6)
    ('Artem Soto', 5)
    ('Boris Marek', 5)
    ('Boris Novak', 5)
    ('Daniel Kovach', 5)
    ('Elena Novak', 5)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT cust.full_name, COUNT(acct.id) AS num_accounts
FROM cust
JOIN acct ON cust.id = acct.cust_id
GROUP BY cust.full_name
HAVING COUNT(acct.id) >= 3
    ('Alina Benali', 3)
    ('Alina Kovach', 3)
    ('Alina Kristof', 3)
    ('Alina Linde', 3)
    ('Alina Marek', 3)
    ('Alina Oduya', 6)
    ('Alina Petran', 3)
    ('Alina Soto', 7)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 5. hr/hr-003 ru/0

ловушка: salary is effective-dated; the current one is the latest from_dt per person; amounts are minor units and must be divided by 100
вопрос:  Кто пять самых высокооплачиваемых по действующей сейчас зарплате?

эталон:
    SELECT e.full_name, p.amount_minor / 100.0 AS pay FROM emp e JOIN pay_hist p ON p.emp_id = e.id WHERE p.from_dt = ( SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id ) ORDER BY pay DESC, e.full_name LIMIT 5
    ('Irina Oduya', 10996.0)
    ('Victor Kristof', 10988.0)
    ('Artem Oduya', 10948.0)
    ('Daniel Almeida', 10890.0)
    ('Victor Marek', 10856.0)

ответ модели:
    WITH CurrentSalaries AS (
    SELECT 
        e.id AS emp_id,
        e.full_name,
        ph.amount_minor AS current_salary
    FROM 
        emp e
    INNER JOIN 
        pay_hist ph ON e.id = ph.emp_id
    WHERE 
        ph.from_dt = (
            SELECT MAX(ph2.from_dt)
            FROM pay_hist ph2
            WHERE ph2.emp_id = e.id
        )
)
SELECT 
    full_name,
    current_salary
FROM 
    CurrentSalaries
ORDER BY 
    current_salary DESC
LIMIT 5
    ('Irina Oduya', 1099600)
    ('Victor Kristof', 1098800)
    ('Artem Oduya', 1094800)
    ('Daniel Almeida', 1089000)
    ('Victor Marek', 1085600)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 6. hr/hr-004 ru/0

ловушка: department name lives in dept; status is a code
вопрос:  Сколько работающих в каждом подразделении, по названию подразделения?

эталон:
    SELECT d.title, COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 GROUP BY d.title ORDER BY n DESC, d.title
    ('Support', 35)
    ('Operations', 34)
    ('Engineering', 32)
    ('Data', 31)
    ('Finance', 28)
    ('Platform', 26)

ответ модели:
    SELECT d.title, COUNT(e.id) AS employee_count
FROM emp e
INNER JOIN dept d ON e.dept_id = d.id
WHERE e.status_cd = 'active'
GROUP BY d.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 7. hr/hr-004 ru/1

ловушка: department name lives in dept; status is a code
вопрос:  По каждому подразделению посчитай сотрудников, которые сейчас работают.

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
  d.title AS department_title,
  COUNT(e.id) AS employee_count
FROM 
  emp e
INNER JOIN 
  dept d ON e.dept_id = d.id
WHERE 
  e.status_cd = 'active'
GROUP BY 
  d.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 8. logistics/log-002 ru/1

ловушка: one lookup table joined twice under two aliases; a single join answers about one end of the route and looks correct
вопрос:  Назови пятёрку самых частых маршрутов, указывая откуда ушла отправка и куда она шла.

эталон:
    SELECT o.title AS origin, d.title AS destination, COUNT(*) AS n FROM shp s JOIN loc_ref o ON o.cd = s.org_cd JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY o.title, d.title ORDER BY n DESC, o.title, d.title LIMIT 5
    ('Kesling', 'Thorne', 21)
    ('Eastvale', 'Lowick', 20)
    ('Northport', 'Harrow', 20)
    ('Harrow', 'Lowick', 18)
    ('Marden', 'Lowick', 18)

ответ модели:
    SELECT 
    c1.city AS origin_city, 
    c2.city AS destination_city, 
    COUNT(*) AS route_count
FROM 
    shp
JOIN 
    cust c1 ON shp.org_cd = c1.id
JOIN 
    cust c2 ON shp.dst_cd = c2.id
GROUP BY 
    c1.city, c2.city
ORDER BY 
    route_count DESC
LIMIT 5
    ('Lowick', 'Lowick', 143)
    ('Lowick', 'Kesling', 99)
    ('Kesling', 'Lowick', 94)
    ('Thorne', 'Lowick', 63)
    ('Lowick', None, 55)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 9. logistics/log-004 ru/0

ловушка: cost is stored in minor units and must be divided by 100
вопрос:  Сколько стоят все плечи маршрутов вместе, в денежных единицах?

эталон:
    SELECT SUM(cost_cents) / 100.0 AS total_cost FROM leg
    (8579947.13,)

ответ модели:
    SELECT SUM(cost_cents) AS total_cost_cents
FROM leg
    (857994713,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 10. logistics/log-005 ru/1

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Перечисли отправки, по которым не зафиксировано ни одного происшествия.

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

## 11. logistics/log-006 ru/0

ловушка: 'delivered' is status_cd = 2, not delivered_at IS NOT NULL; a lost shipment can carry a delivery attempt date, so the two disagree
вопрос:  Сколько отправок доставлено?

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 2
    (503,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
JOIN status_ref ON shp.status_cd = status_ref.cd 
WHERE status_ref.title = 'Delivered'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 12. manufacturing/mfg-002 ru/0

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Сколько всего ушло в брак в пересчёте на базовую единицу?

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(m.qty * ur.to_base) AS total_defect_quantity
FROM mov m
INNER JOIN defect d ON m.id = d.mov_id
INNER JOIN unit_ref ur ON m.unit_cd = ur.cd
    (154137.0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 13. manufacturing/mfg-002 ru/1

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Сложи забракованное количество, приведя все строки к одной единице.

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(mov.qty * unit_ref.to_base) AS total_defective_quantity
FROM mov
INNER JOIN defect ON mov.id = defect.mov_id
INNER JOIN unit_ref ON mov.unit_cd = unit_ref.cd
    (154137.0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 14. manufacturing/mfg-003 ru/1

ловушка: the date is split across the legacy pair dt_op/recorded_at
вопрос:  Посчитай движения, датированные с января по март 2026 года включительно.

эталон:
    SELECT COUNT(*) AS n FROM mov WHERE COALESCE(dt_op, recorded_at) >= '2026-01-01' AND COALESCE(dt_op, recorded_at) < '2026-04-01'
    (85,)

ответ модели:
    SELECT COUNT(*) AS total_movements
FROM mov
WHERE dt_op BETWEEN '2026-01-01' AND '2026-03-31'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 15. manufacturing/mfg-006 ru/1

ловушка: the shift belongs to the line, not to the defect; two joins to reach it
вопрос:  Раздели дефекты по тому, дневная смена на линии или ночная.

эталон:
    SELECT s.title AS shift, COUNT(*) AS defects FROM defect d JOIN mov m ON m.id = d.mov_id JOIN line l ON l.id = m.line_id JOIN shift_ref s ON s.cd = l.shift_cd GROUP BY s.title ORDER BY defects DESC, s.title
    ('night', 185)
    ('day', 135)

ответ модели:
    SELECT 
    CASE 
        WHEN sr.title LIKE '%Day%' THEN 'Day Shift'
        WHEN sr.title LIKE '%Night%' THEN 'Night Shift'
        ELSE 'Unknown Shift'
    END AS Shift,
    COUNT(d.id) AS DefectCount
FROM 
    defect d
INNER JOIN 
    mov m ON d.mov_id = m.id
INNER JOIN 
    line l ON m.line_id = l.id
INNER JOIN 
    shift_ref sr ON l.shift_cd = sr.cd
GROUP BY 
    Shift
    ('Day Shift', 135)
    ('Night Shift', 185)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 16. medicine/med-002 ru/1

ловушка: 'discharged' is status_cd = 2, not the discharged column
вопрос:  Покажи пятёрку врачей с наибольшим числом выписанных случаев.

эталон:
    SELECT d.full_name, COUNT(*) AS n FROM enc e JOIN doc d ON d.id = e.doc_id WHERE e.status_cd = 2 GROUP BY d.full_name ORDER BY n DESC, d.full_name LIMIT 5
    ('Artem Petran', 35)
    ('Olga Almeida', 23)
    ('Anna Varga', 21)
    ('Artem Kristof', 21)
    ('Irina Varga', 21)

ответ модели:
    SELECT d.full_name, COUNT(e.enc_id) AS discharge_count
FROM doc d
JOIN enc e ON d.id = e.doc_id
WHERE e.status_cd = 'discharged'
GROUP BY d.id
ORDER BY discharge_count DESC
LIMIT 5
    ОШИБКА: OperationalError: no such column: e.enc_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 17. medicine/med-005 ru/1

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Перечисли пациентов, которые ни разу не поступали.

эталон:
    SELECT p.full_name FROM pat p WHERE NOT EXISTS (SELECT 1 FROM enc e WHERE e.pat_id = p.id) ORDER BY p.full_name
    ('Alina Marek',)
    ('Anna Almeida',)
    ('Anna Bauer',)
    ('Anna Hale',)
    ('Anna Reiner',)
    ('Anna Reiner',)
    ('Artem Almeida',)
    ('Artem Novak',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT p.id, p.full_name
FROM pat p
WHERE p.id NOT IN (SELECT e.pat_id FROM enc e)
    (4, 'Olga Novak')
    (13, 'Irina Kristof')
    (14, 'Olga Novak')
    (15, 'Elena Benali')
    (20, 'Vera Almeida')
    (41, 'Igor Petran')
    (62, 'Boris Reiner')
    (68, 'Daniel Hale')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен

## 18. medicine/med-008 ru/1

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Покажи пациентов с тремя и более обращениями и число обращений у каждого.

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
JOIN enc e ON p.id = e.pat_id
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

## 19. public_services/gov-004 ru/1

ловушка: the submission date is split across the legacy pair dt_sub/submitted_at
вопрос:  Посчитай дела, поданные с апреля по июнь 2026 года включительно.

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

## 20. public_services/gov-006 ru/1

ловушка: result_cd is NULL for a stage still open, and NULL is not a code; an inner join is correct here, which is the opposite of gov-005
вопрос:  Для этапов, у которых есть результат, разбей их по тому, какой он.

эталон:
    SELECT r.title AS result, COUNT(*) AS n FROM stage s JOIN result_ref r ON r.cd = s.result_cd GROUP BY r.title ORDER BY n DESC, r.title
    ('approved', 743)
    ('refused', 278)
    ('withdrawn', 122)

ответ модели:
    SELECT result_cd, COUNT(*) AS stage_count
FROM stage
GROUP BY result_cd
    (None, 357)
    (1, 743)
    (2, 278)
    (3, 122)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям
