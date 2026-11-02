# Ручной разбор провалов: qwen25-coder-14b.holdout-ru.jsonl

Провалов всего: 48 из 96.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank-003 ru/0

ловушка: operation date is split across the legacy pair dt_op/posted_at
вопрос:  Сколько операций приходится на второй квартал 2026 года?

эталон:
    SELECT COUNT(*) AS n FROM txn WHERE COALESCE(dt_op, posted_at) >= '2026-04-01' AND COALESCE(dt_op, posted_at) < '2026-07-01'
    (410,)

ответ модели:
    SELECT COUNT(*) 
FROM txn 
WHERE strftime('%Y-%m', posted_at) = '2026-04'
    (134,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 2. banking/bank-007 ru/0

ловушка: DISTINCT customer, not account count; 'active' is status_cd = 1, and residency is a second coded column
вопрос:  Сколько разных клиентов держат действующий счёт, в разрезе резидентства?

эталон:
    SELECT r.title AS residency, COUNT(DISTINCT a.cust_id) AS customers FROM acct a JOIN cust c ON c.id = a.cust_id JOIN resid_ref r ON r.cd = c.resid_cd WHERE a.status_cd = 1 GROUP BY r.title ORDER BY customers DESC, r.title
    ('resident', 189)
    ('non-resident', 34)

ответ модели:
    SELECT 
    r.title AS residency,
    COUNT(DISTINCT a.cust_id) AS active_customers
FROM 
    acct a
JOIN 
    cust c ON a.cust_id = c.id
JOIN 
    resid_ref r ON c.resid_cd = r.cd
JOIN 
    acct_status_ref asr ON a.status_cd = asr.cd
WHERE 
    asr.title = 'Active'
GROUP BY 
    r.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 3. banking/bank-008 ru/0

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  У каких клиентов больше двух счетов?

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
    SELECT c.full_name
FROM cust c
JOIN acct a ON c.id = a.cust_id
GROUP BY c.id
HAVING COUNT(a.id) > 2
    ('Irina Kovach',)
    ('Daniel Kovach',)
    ('Elena Oduya',)
    ('Boris Almeida',)
    ('Irina Hale',)
    ('Pavel Marek',)
    ('Vera Kristof',)
    ('Mark Bauer',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 4. hr/hr-004 ru/0

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
    SELECT d.title AS department_title, COUNT(e.id) AS number_of_employees
FROM dept d
JOIN emp e ON d.id = e.dept_id
GROUP BY d.title
    ('Data', 39)
    ('Engineering', 51)
    ('Finance', 36)
    ('Operations', 50)
    ('Platform', 37)
    ('Support', 47)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 5. hr/hr-008 ru/0

ловушка: DISTINCT person, not a count of pay rows; HAVING on the distinct count, which RedSQL found models get wrong most often
вопрос:  В каких валютах платят больше чем двум людям?

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

## 6. logistics/log-003 ru/0

ловушка: dispatch date is split across the legacy pair dt_disp/dispatched_at
вопрос:  Сколько отправок ушло в третьем квартале 2026 года?

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE COALESCE(dt_disp, dispatched_at) >= '2026-07-01' AND COALESCE(dt_disp, dispatched_at) < '2026-10-01'
    (121,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
WHERE dt_disp BETWEEN '2026-07-01' AND '2026-09-30'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 7. logistics/log-004 ru/0

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

## 8. logistics/log-006 ru/1

ловушка: 'delivered' is status_cd = 2, not delivered_at IS NOT NULL; a lost shipment can carry a delivery attempt date, so the two disagree
вопрос:  Посчитай отправки, которые сейчас находятся в состоянии «доставлено».

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 2
    (503,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
JOIN status_ref ON shp.status_cd = status_ref.cd 
WHERE status_ref.title = 'доставлено'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 9. logistics/log-007 ru/1

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
    SELECT dst_cd, COUNT(DISTINCT carr_id) AS unique_carriers_count
FROM shp
GROUP BY dst_cd
    ОШИБКА: OperationalError: no such column: carr_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 10. manufacturing/mfg-002 ru/0

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Сколько всего ушло в брак в пересчёте на базовую единицу?

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(d.qty * ur.to_base) AS total_defective_in_base_unit
FROM defect d
JOIN mov m ON d.mov_id = m.id
JOIN unit_ref ur ON m.unit_cd = ur.cd
    ОШИБКА: OperationalError: no such column: d.qty

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 11. manufacturing/mfg-002 ru/1

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Сложи забракованное количество, приведя все строки к одной единице.

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(mov.qty * unit_ref.to_base) AS total_defective_quantity
FROM defect
JOIN mov ON defect.mov_id = mov.id
JOIN unit_ref ON mov.unit_cd = unit_ref.cd
    (154137.0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 12. manufacturing/mfg-005 ru/1

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Перечисли движения, по которым дефектов не находили.

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

## 13. manufacturing/mfg-006 ru/1

ловушка: the shift belongs to the line, not to the defect; two joins to reach it
вопрос:  Раздели дефекты по тому, дневная смена на линии или ночная.

эталон:
    SELECT s.title AS shift, COUNT(*) AS defects FROM defect d JOIN mov m ON m.id = d.mov_id JOIN line l ON l.id = m.line_id JOIN shift_ref s ON s.cd = l.shift_cd GROUP BY s.title ORDER BY defects DESC, s.title
    ('night', 185)
    ('day', 135)

ответ модели:
    SELECT 
    CASE 
        WHEN sr.title = 'Дневная смена' THEN 'Дневная смена'
        ELSE 'Ночная смена'
    END AS shift,
    COUNT(*) AS defect_count
FROM 
    defect d
JOIN 
    mov m ON d.mov_id = m.id
JOIN 
    line l ON m.line_id = l.id
JOIN 
    shift_ref sr ON l.shift_cd = sr.cd
GROUP BY 
    shift
    ('Ночная смена', 320)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 14. manufacturing/mfg-007 ru/1

ловушка: DISTINCT part, not a movement count
вопрос:  По каждой единице измерения посчитай число различных деталей.

эталон:
    SELECT u.title AS unit, COUNT(DISTINCT m.part_id) AS parts FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd GROUP BY u.title ORDER BY parts DESC, u.title
    ('kilogram', 6)
    ('piece', 6)
    ('tonne', 6)

ответ модели:
    SELECT unit_ref.cd, COUNT(DISTINCT mov.part_id) AS distinct_part_count
FROM mov
JOIN unit_ref ON mov.unit_cd = unit_ref.cd
GROUP BY unit_ref.cd
    (1, 6)
    (2, 6)
    (3, 6)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 15. manufacturing/mfg-008 ru/1

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Покажи детали с одиннадцатью и более дефектами и число дефектов у каждой.

эталон:
    SELECT p.title, COUNT(*) AS defects FROM defect d JOIN mov m ON m.id = d.mov_id JOIN part p ON p.id = m.part_id GROUP BY p.id, p.title HAVING COUNT(*) > 10 ORDER BY defects DESC, p.title
    ('bracket', 128)
    ('shaft', 83)
    ('gearwheel', 41)
    ('plate', 39)
    ('bushing', 22)

ответ модели:
    SELECT mov.part_id, COUNT(defect.id) AS defect_count
FROM mov
JOIN defect ON mov.id = defect.mov_id
GROUP BY mov.part_id
HAVING defect_count >= 11
    (1, 128)
    (2, 83)
    (3, 39)
    (4, 41)
    (5, 22)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 16. medicine/med-001 ru/0

ловушка: sex is a code, needs the lookup join
вопрос:  Сколько пациентов каждого пола?

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

## 17. medicine/med-002 ru/1

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
    SELECT d.full_name, COUNT(e.id) AS discharge_count
FROM doc d
JOIN enc e ON d.id = e.doc_id
WHERE e.discharged = 1
GROUP BY d.id
ORDER BY discharge_count DESC
LIMIT 5
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 18. medicine/med-004 ru/0

ловушка: diagnosis name lives in dx_ref, the code alone is not an answer
вопрос:  Какие три основных диагноза встречаются чаще всего, по названию?

эталон:
    SELECT x.title, COUNT(*) AS n FROM dx JOIN dx_ref x ON x.code = dx.code WHERE dx.primary_flag = 1 GROUP BY x.title ORDER BY n DESC, x.title LIMIT 3
    ('essential hypertension', 104)
    ('epilepsy', 98)
    ('chronic kidney disease', 96)

ответ модели:
    SELECT dx_ref.title, COUNT(*) AS count
FROM dx
JOIN dx_ref ON dx.code = dx_ref.code
WHERE dx.primary_flag = 'Y'
GROUP BY dx_ref.title
ORDER BY count DESC
LIMIT 3
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 19. medicine/med-004 ru/1

ловушка: diagnosis name lives in dx_ref, the code alone is not an answer
вопрос:  Назови тройку самых частых основных диагнозов и сколько раз каждый встретился.

эталон:
    SELECT x.title, COUNT(*) AS n FROM dx JOIN dx_ref x ON x.code = dx.code WHERE dx.primary_flag = 1 GROUP BY x.title ORDER BY n DESC, x.title LIMIT 3
    ('essential hypertension', 104)
    ('epilepsy', 98)
    ('chronic kidney disease', 96)

ответ модели:
    SELECT dx_ref.title, COUNT(dx.enc_id) AS count
FROM dx
JOIN dx_ref ON dx.code = dx_ref.code
WHERE dx.primary_flag = 'Y'
GROUP BY dx_ref.title
ORDER BY count DESC
LIMIT 3
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 20. medicine/med-008 ru/1

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
    SELECT p.id, p.full_name, COUNT(e.id) AS num_encounters
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
