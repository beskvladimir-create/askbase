# Ручной разбор провалов: arctic-7b-q4.holdout-ru.jsonl

Провалов всего: 58 из 96.
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
    SELECT SUM(CASE WHEN dir_cd = 'Debit' THEN -amt_cents ELSE amt_cents END) AS net_total_cents
FROM txn
    (56748436,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 2. banking/bank-004 ru/0

ловушка: the category name lives in mcc_ref, the code alone is not an answer
вопрос:  Какие три категории торговых точек встречаются чаще всего, по названию?

эталон:
    SELECT m.title, COUNT(*) AS n FROM txn t JOIN mcc_ref m ON m.code = t.mcc GROUP BY m.title ORDER BY n DESC, m.title LIMIT 3
    ('cash withdrawal', 340)
    ('electronics stores', 312)
    ('restaurants', 302)

ответ модели:
    SELECT title, COUNT(*) as count
FROM mcc_ref
GROUP BY title
ORDER BY count DESC
LIMIT 3
    ('telecoms', 1)
    ('restaurants', 1)
    ('pharmacies', 1)

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
    SELECT AVG(rate_bp) AS average_interest_rate
FROM loan
WHERE closed_at IS NULL
    (1148.7196261682243,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 4. hr/hr-001 ru/1

ловушка: status is a code, needs the lookup join
вопрос:  Разбей сотрудников по статусу и покажи количество в каждой группе.

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
        ph.amount_minor AS current_salary,
        ROW_NUMBER() OVER (PARTITION BY e.id ORDER BY ph.from_dt DESC) AS rn
    FROM 
        emp e
    INNER JOIN 
        pay_hist ph ON e.id = ph.emp_id
)
SELECT 
    full_name,
    current_salary
FROM 
    CurrentSalaries
WHERE 
    rn = 1
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

## 8. hr/hr-008 ru/0

ловушка: DISTINCT person, not a count of pay rows; HAVING on the distinct count, which RedSQL found models get wrong most often
вопрос:  В каких валютах платят больше чем двум людям?

эталон:
    SELECT c.title AS title, COUNT(DISTINCT p.emp_id) AS people FROM pay_hist p JOIN cur_ref c ON c.cd = p.cur_cd GROUP BY c.title HAVING COUNT(DISTINCT p.emp_id) > 2 ORDER BY people DESC, c.title
    ('EUR', 206)
    ('USD', 115)

ответ модели:
    SELECT ph.cur_cd
FROM pay_hist ph
GROUP BY ph.cur_cd
HAVING COUNT(ph.emp_id) > 2
    (1,)
    (2,)

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

## 10. logistics/log-004 ru/1

ловушка: cost is stored in minor units and must be divided by 100
вопрос:  Сложи стоимость всех плеч и дай ответ в основных единицах, а не в копейках.

эталон:
    SELECT SUM(cost_cents) / 100.0 AS total_cost FROM leg
    (8579947.13,)

ответ модели:
    To translate the given natural language question into an executable SQLite query, we need to follow these steps:

1. **Understand the Question**: The question asks for the total cost of all legs, but the result should be in the main units (grams or kilograms), not in the sub-unit used in the database (cents).

2. **Identify Relevant Tables and Columns**: From the schema, the `leg` table contains the `cost_cents` column, which holds the cost of each leg in cents. This is the only table we need for this query.

3. **Formulate the SQL Query**:
   - Use the `SUM` function to aggregate the `cost_cents` column.
   - Convert the sum from cents to the main unit (grams or kilograms). Since the question specifies "main units" and the cost is in cents, we assume it's asking for the sum in the same unit but in a more readable format. However, since the question asks for the sum in "main units" and the cost is in cents, we will convert it to dollars for better readability, but the question specifically asks for the sum in the main units, which in this context means converting cents to the main unit (grams or kilograms). Given the context, it seems the question is asking for the sum in the same unit but in a more understandable format, so we will convert it to dollars for better readability, but since the question asks for the sum in the main units, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks for the sum in the main units and the cost is in cents, we will assume it means converting cents to the main unit, which in this context is grams or kilograms. However, since the question asks
    ОШИБКА: OperationalError: near "To": syntax error

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 11. logistics/log-005 ru/1

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
WHERE i.shp_id IS NULL
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

## 12. logistics/log-007 ru/1

ловушка: DISTINCT carrier, not leg count; the destination end of the route, not the origin
вопрос:  По каждому месту назначения посчитай число уникальных перевозчиков.

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
    shp.dst_cd, 
    COUNT(DISTINCT leg.carr_id) AS unique_carriers
FROM 
    shp
INNER JOIN 
    leg ON shp.id = leg.shp_id
GROUP BY 
    shp.dst_cd
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

## 13. manufacturing/mfg-002 ru/0

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Сколько всего ушло в брак в пересчёте на базовую единицу?

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(m.qty * ur.to_base) AS total_defects_in_base_units
FROM mov m
INNER JOIN defect d ON m.id = d.mov_id
INNER JOIN unit_ref ur ON m.unit_cd = ur.cd
    (154137.0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 14. manufacturing/mfg-002 ru/1

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Сложи забракованное количество, приведя все строки к одной единице.

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(m.qty * ur.to_base) AS total_defective_quantity
FROM mov m
INNER JOIN defect d ON m.id = d.mov_id
INNER JOIN unit_ref ur ON m.unit_cd = ur.cd
    (154137.0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 15. manufacturing/mfg-007 ru/0

ловушка: DISTINCT part, not a movement count
вопрос:  Сколько разных деталей измеряется в каждой единице?

эталон:
    SELECT u.title AS unit, COUNT(DISTINCT m.part_id) AS parts FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd GROUP BY u.title ORDER BY parts DESC, u.title
    ('kilogram', 6)
    ('piece', 6)
    ('tonne', 6)

ответ модели:
    SELECT 
    m.unit_cd AS unit_code,
    COUNT(DISTINCT p.id) AS distinct_parts_count
FROM 
    mov m
JOIN 
    part p ON m.part_id = p.id
GROUP BY 
    m.unit_cd
    (1, 6)
    (2, 6)
    (3, 6)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 16. medicine/med-002 ru/0

ловушка: 'discharged' is status_cd = 2, not the discharged column
вопрос:  Какие пять врачей выписали больше всего пациентов?

эталон:
    SELECT d.full_name, COUNT(*) AS n FROM enc e JOIN doc d ON d.id = e.doc_id WHERE e.status_cd = 2 GROUP BY d.full_name ORDER BY n DESC, d.full_name LIMIT 5
    ('Artem Petran', 35)
    ('Olga Almeida', 23)
    ('Anna Varga', 21)
    ('Artem Kristof', 21)
    ('Irina Varga', 21)

ответ модели:
    SELECT d.full_name, COUNT(e.pat_id) AS discharged_patients
FROM doc d
JOIN enc e ON d.id = e.doc_id
WHERE e.status_cd = 'discharged'
GROUP BY d.id
ORDER BY discharged_patients DESC
LIMIT 5
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

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
    SELECT *
FROM pat
WHERE id NOT IN (SELECT pat_id FROM enc)
    (4, 'Olga Novak', '1975-11-23', 1, 'Marden')
    (13, 'Irina Kristof', '1961-08-22', 1, 'Thorne')
    (14, 'Olga Novak', '1958-09-19', 1, 'Avelin')
    (15, 'Elena Benali', '1956-12-19', 2, 'Marden')
    (20, 'Vera Almeida', '1990-08-22', 1, 'Eastvale')
    (41, 'Igor Petran', '1994-01-27', 1, 'Northport')
    (62, 'Boris Reiner', '1999-07-15', 1, 'Lowick')
    (68, 'Daniel Hale', '1949-06-08', 1, 'Northport')
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

## 19. public_services/gov-003 ru/0

ловушка: people reapply, so a case count and a people count differ
вопрос:  Сколько разных людей вообще подавало заявления?

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

## 20. public_services/gov-004 ru/1

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
