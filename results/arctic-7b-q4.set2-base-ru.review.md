# Ручной разбор провалов: arctic-7b-q4.set2-base-ru.jsonl

Провалов всего: 411 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-012 ru/1

ловушка: principal is stored in minor units although its name does not say so; a loan is open when closed_at IS NULL
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT SUM(principal) / 100.0 AS outstanding FROM loan WHERE closed_at IS NULL
    (4193712.0,)

ответ модели:
    SELECT SUM(principal) AS total_unreturned_amount
FROM loan
WHERE closed_at IS NULL
    (419371200,)

ошибка исполнения: нет

вердикт: model
заметка: минорные единицы не переведены: 419371200 вместо 4193712.0

## 2. banking/bank2-036 ru/0

ловушка: the difference between two text dates needs julianday, subtraction returns nonsense; a loan with no closing date has no span and must be left out of the average
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(julianday(closed_at) - julianday(opened_at)), 2) AS mean_days FROM loan WHERE closed_at IS NOT NULL
    (819.62,)

ответ модели:
    SELECT AVG(julianday(closed_at) - julianday(opened_at)) AS average_days_opened_to_closed
FROM acct
WHERE closed_at IS NOT NULL
    (461.505376344086,)

ошибка исполнения: нет

вердикт: model
заметка: взята таблица acct вместо loan, нет округления

## 3. hr/hr2-002 ru/0

ловушка: the latest pay row per person, then the currency filter on it; minor units divided by 100.0, and an average rather than a sum
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title, ROUND(AVG(p.amount_minor / 100.0), 2) AS avg_pay FROM emp e JOIN dept d ON d.id = e.dept_id JOIN pay_hist p ON p.emp_id = e.id WHERE p.cur_cd = 1 AND p.from_dt = ( SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id ) GROUP BY d.title ORDER BY avg_pay DESC, d.title
    ('Engineering', 7422.55)
    ('Finance', 6835.82)
    ('Support', 6800.46)
    ('Data', 6696.65)
    ('Operations', 6330.31)
    ('Platform', 6217.13)

ответ модели:
    SELECT 
  e.dept_id,
  ROUND(AVG(ph.amount_minor), 2) AS average_salary
FROM 
  pay_hist ph
INNER JOIN 
  cur_ref cr ON ph.cur_cd = cr.cd
INNER JOIN 
  emp e ON ph.emp_id = e.id
WHERE 
  cr.title = 'Euro' AND e.status_cd = 'A'
GROUP BY 
  e.dept_id
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пусто: фильтр по cur_ref.title и status_cd, группировка по dept_id, нет деления на 100

## 4. hr/hr2-033 ru/1

ловушка: unpaid leave is status_cd = 2, a code and not a word; the question counts people, so several absences must not multiply the count
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(DISTINCT e.id) AS n FROM emp e JOIN absence a ON a.emp_id = e.id WHERE e.status_cd = 2
    (11,)

ответ модели:
    SELECT COUNT(e.id) AS total_employees
FROM emp e
JOIN absence a ON e.id = a.emp_id
JOIN emp_status_ref esr ON e.status_cd = esr.cd
WHERE esr.title = 'неоплачиваемый отпуск'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: пусто: искала русское название статуса вместо кода 2

## 5. hr/hr2-047 ru/1

ловушка: the salary in force is the latest from_dt per person, so the history would widen every spread; the ordering key is a difference of two aggregates, and it is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title FROM emp e JOIN dept d ON d.id = e.dept_id JOIN pay_hist p ON p.emp_id = e.id WHERE e.status_cd = 1 AND p.cur_cd = 1 AND p.from_dt = (SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id) GROUP BY d.title ORDER BY MAX(p.amount_minor) - MIN(p.amount_minor) DESC, d.title LIMIT 1
    ('Operations',)

ответ модели:
    SELECT 
    d.title AS department_title,
    MAX(ph.amount_minor) - MIN(ph.amount_minor) AS salary_range
FROM 
    dept d
JOIN 
    emp e ON d.id = e.dept_id
JOIN 
    pay_hist ph ON e.id = ph.emp_id
JOIN 
    cur_ref cr ON ph.cur_cd = cr.cd
WHERE 
    e.status_cd = 'active' AND cr.cd = 'EUR'
GROUP BY 
    d.title
ORDER BY 
    salary_range DESC
LIMIT 1
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пусто: status_cd='active' и cr.cd='EUR', типы не те, плюс лишняя колонка

## 6. logistics/log2-007 ru/1

ловушка: the mode is a code, its name lives in mode_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT m.title AS mode, COUNT(*) AS n FROM carr c JOIN mode_ref m ON m.cd = c.mode_cd GROUP BY m.title ORDER BY n DESC, m.title
    ('road', 23)
    ('rail', 11)
    ('sea', 8)
    ('air', 3)

ответ модели:
    SELECT 
    id,
    title,
    CASE 
        WHEN mode_cd = 'road' THEN 'Road'
        WHEN mode_cd = 'rail' THEN 'Rail'
        WHEN mode_cd = 'sea' THEN 'Sea'
        WHEN mode_cd = 'air' THEN 'Air'
        ELSE 'Unknown'
    END AS mode
FROM 
    carr
    (1, 'Almeida Transit', 'Unknown')
    (2, 'Petran Freight', 'Unknown')
    (3, 'Marek Freight', 'Unknown')
    (4, 'Bauer Haulage', 'Unknown')
    (5, 'Petran Logistics', 'Unknown')
    (6, 'Petran Freight', 'Unknown')
    (7, 'Reiner Transit', 'Unknown')
    (8, 'Novak Haulage', 'Unknown')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: форма ответа другая: строки перевозчиков вместо группировки по виду, все виды 'Unknown'

## 7. logistics/log2-018 ru/0

ловушка: the dispatch date is split across the legacy pair dt_disp/dispatched_at; delivered is the status, not the presence of a delivery date; dates are text, so the difference needs julianday
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(julianday(delivered_at) - julianday(COALESCE(dt_disp, dispatched_at))), 1) AS days FROM shp WHERE status_cd = 2
    (20.0,)

ответ модели:
    SELECT ROUND(AVG(julianday(delivered_at) - julianday(dispatched_at)), 1) AS average_delivery_days
FROM shp
    (20.5,)

ошибка исполнения: нет

вердикт: model
заметка: 20.5 вместо 20.0: нет COALESCE по паре дат и нет фильтра по статусу

## 8. logistics/log2-036 ru/0

ловушка: the customer's city is text while the destination is a code, so the join has to resolve the code first; the destination end, not the origin; a customer with no city recorded matches nothing, because NULL is not equal to anything
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM shp s JOIN cust c ON c.id = s.cust_id JOIN loc_ref d ON d.cd = s.dst_cd WHERE c.city = d.title
    (80,)

ответ модели:
    SELECT COUNT(*) AS total_shipments
FROM cust c
JOIN shp s ON c.city = (SELECT l.title FROM loc_ref l WHERE l.cd = s.dst_cd)
WHERE c.city = (SELECT l.title FROM loc_ref l WHERE l.cd = s.dst_cd)
    (9766,)

ошибка исполнения: нет

вердикт: model
заметка: 9766 вместо 80: коррелированный подзапрос в ON дал декартово соединение

## 9. logistics/log2-047 ru/0

ловушка: the difference between two text dates needs julianday, subtraction returns nonsense; the dispatch date is split across the legacy pair dt_disp/dispatched_at; only delivered shipments have both dates, and a lost one with a date would spoil the average
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.country, ROUND(AVG(julianday(s.delivered_at) - julianday(COALESCE(s.dt_disp, s.dispatched_at))), 2) AS days FROM shp s JOIN loc_ref d ON d.cd = s.dst_cd WHERE s.status_cd = 2 GROUP BY d.country ORDER BY days DESC, d.country
    ('Breland', 20.95)
    ('Dornia', 20.14)
    ('Cavira', 19.43)
    ('Aldoria', 19.37)

ответ модели:
    SELECT 
    l.country, 
    AVG(julianday(s.delivered_at) - julianday(s.dispatched_at)) AS avg_delivery_days
FROM 
    shp s
JOIN 
    loc_ref l ON s.dst_cd = l.cd
GROUP BY 
    l.country
    ('Aldoria', 19.97752808988764)
    ('Breland', 21.40909090909091)
    ('Cavira', 20.012345679012345)
    ('Dornia', 20.63917525773196)

ошибка исполнения: нет

вердикт: model
заметка: значения другие: нет фильтра по статусу, нет COALESCE, нет округления

## 10. manufacturing/mfg2-005 ru/0

ловушка: a window still in force is the one whose valid_to is NULL; the price is in minor units and must be divided by 100.0
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, p.title, pp.minor / 100.0 AS price FROM part p JOIN part_price pp ON pp.part_id = p.id WHERE pp.valid_to IS NULL ORDER BY p.code
    ('BR-100', 'bracket', 21.2)
    ('BU-550', 'bushing', 49.22)
    ('GR-440', 'gearwheel', 48.65)
    ('PL-330', 'plate', 133.63)
    ('SH-210', 'shaft', 16.59)
    ('SP-660', 'spring', 23.57)

ответ модели:
    SELECT 
    pp.part_id,
    (pp.minor * ur.to_base) AS price_in_base_unit
FROM 
    part_price pp
JOIN 
    unit_ref ur ON ur.cd = (SELECT unit_cd FROM mov WHERE part_id = pp.part_id LIMIT 1)
WHERE 
    pp.valid_from <= CURRENT_DATE AND pp.valid_to >= CURRENT_DATE
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пусто: сравнение дат вместо valid_to IS NULL, умножение на to_base вместо деления на 100

## 11. manufacturing/mfg2-009 ru/1

ловушка: here the range join is wrong: the question names one price, the open one, and a join on part_id alone multiplies every movement by the four price rows it has
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title, ROUND(SUM(m.qty * u.to_base * pp.minor / 100.0), 2) AS cost FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id WHERE pp.valid_to IS NULL GROUP BY p.title ORDER BY cost DESC, p.title
    ('plate', 16282147.35)
    ('bracket', 6168415.6)
    ('gearwheel', 5076043.7)
    ('bushing', 3683280.26)
    ('shaft', 2744815.5)
    ('spring', 269664.37)

ответ модели:
    SELECT SUM(m.qty) AS total_quantity
FROM mov m
INNER JOIN part_price pp ON m.part_id = pp.part_id
WHERE pp.valid_to > CURRENT_DATE
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: (None,): суммировано qty вместо стоимости, valid_to > CURRENT_DATE не находит открытое окно

## 12. manufacturing/mfg2-027 ru/0

ловушка: the difference between two text dates needs julianday, subtraction returns nonsense; the movement date is split across the legacy pair dt_op/recorded_at; a defect found before its movement gives a negative number, which the maximum simply ignores
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title, CAST(MAX(julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at))) AS INTEGER) AS days FROM defect d JOIN mov m ON m.id = d.mov_id JOIN part p ON p.id = m.part_id GROUP BY p.title ORDER BY days DESC, p.title
    ('plate', 1065)
    ('bracket', 1044)
    ('bushing', 987)
    ('shaft', 931)
    ('gearwheel', 854)
    ('spring', 727)

ответ модели:
    SELECT 
    p.id AS part_id,
    MAX(julianday(d.found_at) - julianday(m.recorded_at)) AS longest_duration_days
FROM 
    mov m
JOIN 
    defect d ON m.id = d.mov_id
JOIN 
    part p ON m.part_id = p.id
GROUP BY 
    p.id
    (1, 314.0)
    (2, 213.0)
    (3, 36.0)
    (4, 49.0)
    (5, 143.0)
    (6, None)

ошибка исполнения: нет

вердикт: model
заметка: значения другие и part_id вместо title: нет COALESCE по паре дат, нет CAST

## 13. manufacturing/mfg2-029 ru/0

ловушка: the conversion factor lives in unit_ref and is the whole of the question; the unit is named in the lookup, so the filter cannot be written on the code alone
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(m.qty * u.to_base), 2) AS kg FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE u.title = 'tonne'
    (610600.0,)

ответ модели:
    SELECT SUM(m.qty) * 1000 AS total_quantity_kg
FROM mov m
INNER JOIN unit_ref u ON m.unit_cd = u.cd
WHERE u.title = 'тонна'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: (None,): фильтр u.title='тонна', в справочнике 'tonne'

## 14. manufacturing/mfg2-034 ru/1

ловушка: the open window is the one with no valid_to, which no date comparison finds; the movement date is split across the legacy pair dt_op/recorded_at
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, COUNT(*) AS n FROM mov m JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id AND pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) WHERE pp.valid_to IS NULL GROUP BY p.code ORDER BY n DESC, p.code
    ('BR-100', 86)
    ('SH-210', 63)
    ('PL-330', 42)
    ('GR-440', 36)
    ('BU-550', 14)
    ('SP-660', 5)

ответ модели:
    SELECT p.code, COUNT(m.id) AS movement_count
FROM mov m
JOIN part_price pp ON m.part_id = pp.part_id
JOIN part p ON m.part_id = p.id
WHERE m.recorded_at >= pp.valid_from
GROUP BY p.code
    ('BR-100', 383)
    ('BU-550', 62)
    ('GR-440', 153)
    ('PL-330', 189)
    ('SH-210', 294)
    ('SP-660', 20)

ошибка исполнения: нет

вердикт: model
заметка: счётчики другие: нет COALESCE и нет условия valid_to IS NULL

## 15. manufacturing/mfg2-036 ru/1

ловушка: a defect found before its movement would drag the average down and the question excludes it; the movement date is split across the legacy pair dt_op/recorded_at; the grade is a code, its name lives in grade_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT g.title AS grade, ROUND(AVG(julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at))), 2) AS days FROM defect d JOIN mov m ON m.id = d.mov_id JOIN grade_ref g ON g.cd = d.grade_cd WHERE d.found_at >= COALESCE(m.dt_op, m.recorded_at) GROUP BY g.title ORDER BY days DESC, g.title
    ('major', 479.17)
    ('minor', 385.42)
    ('critical', 324.8)

ответ модели:
    SELECT 
    d.grade_cd, 
    AVG(julianday(d.found_at) - julianday(m.recorded_at)) AS avg_days_to_defect
FROM 
    defect d
JOIN 
    mov m ON d.mov_id = m.id
WHERE 
    d.found_at > m.recorded_at
GROUP BY 
    d.grade_cd
    (1, 103.0)
    (2, 70.66666666666667)
    (3, 104.0)

ошибка исполнения: нет

вердикт: model
заметка: коды степени вместо названий и значения другие: нет COALESCE по паре дат

## 16. medicine/med2-013 ru/1

ловушка: anti-join through two tables; the answer includes patients who were admitted and still have no diagnosis
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.full_name FROM pat p WHERE NOT EXISTS ( SELECT 1 FROM enc e JOIN dx d ON d.enc_id = e.id WHERE e.pat_id = p.id ) ORDER BY p.full_name
    ('Alina Kovach',)
    ('Alina Linde',)
    ('Alina Petran',)
    ('Alina Petran',)
    ('Alina Soto',)
    ('Alina Varga',)
    ('Anna Marek',)
    ('Anna Reiner',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT p.full_name
FROM pat p
LEFT JOIN enc e ON p.id = e.pat_id
LEFT JOIN dx d ON e.id = d.enc_id
WHERE d.enc_id IS NULL
    ('Elena Marek',)
    ('Olga Kristof',)
    ('Elena Hale',)
    ('Igor Varga',)
    ('Pavel Petran',)
    ('Boris Kristof',)
    ('Anna Soto',)
    ('Irina Marek',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: LEFT JOIN с условием d.enc_id IS NULL включает пациентов, у которых есть диагноз в другом случае

## 17. medicine/med2-025 ru/1

ловушка: the admission date is split across the legacy pair dt_adm/admitted_at; the comparison is between two columns of two tables, not against a literal
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM enc e JOIN doc d ON d.id = e.doc_id WHERE d.hired_at > COALESCE(e.dt_adm, e.admitted_at)
    (9,)

ответ модели:
    with another date. Since the question does not specify another date, we assume it means comparing `dt_adm` with itself or another related date, but based on the schema, we can only compare `dt_adm` with itself or use another column in the same table if necessary. However, the question seems to imply a comparison with a different event, but since no such event is specified, we will assume it means counting cases where `dt_adm` is present and valid.

2. **Formulate the Condition:**
   - The question asks for cases where the date of admission (`dt_adm`) is later than the date of admission (`dt_adm`). This condition is logically incorrect as it will never be true. However, if we interpret it as counting all entries where `dt_adm` is present, we can simply count all rows in the `enc` table.
   - But since the question specifically asks for a comparison and the reference solution implies a comparison, we will assume the question intends to count cases where `dt_adm` is present and valid, which means counting all rows in the `enc` table.

3. **Construct the SQL Query:**
   - Given the above interpretation, the query should count all rows in the `enc` table. However, since the question asks for a specific comparison and the reference solution implies a comparison, we will assume the question intends to count cases where `dt_adm` is present and valid, which means counting all rows in the `enc` table.

However, since the question asks for a specific comparison and the reference solution implies a comparison, we will assume the question intends to count cases where `dt_adm` is present and valid, which means counting all rows in the `enc` table.

Given the schema and the question, the correct interpretation should be counting all rows in the `enc` table where `dt_adm` is present and valid, but since the question asks for a specific comparison, we will assume the question intends to count cases where `dt_adm` is present and valid, which means counting all rows in the `enc` table.

However, since the question asks for a specific comparison and the reference solution implies a comparison, we will assume the question intends to count cases where `dt_adm` is present and valid, which means counting all rows in the `enc` table.

Given the schema and the question, the correct interpretation should be counting all rows in the `enc` table where `dt_adm` is present and valid, but since the question asks for a specific comparison, we will assume the question intends to count cases where `dt_adm` is present and valid, which means counting all rows in the `enc` table.

However, since the question asks for a specific comparison and the reference solution implies a comparison, we will assume the question intends to count cases where `dt_adm` is present and valid, which means counting all rows in the `enc` table.

Given the schema and the question, the correct interpretation should be counting all rows in the `enc` table where `dt_adm` is present and valid, but since the question asks for a specific comparison, we will assume the question intends to count cases where `dt_adm` is present and valid, which means counting all rows in the `enc` table.

However, since the question asks for a specific comparison and the reference solution implies a comparison, we will assume the question intends to count cases where `dt_adm` is present and valid, which means counting all rows in the `enc` table.

Given the schema and the question, the correct interpretation should be counting all rows in the `enc` table where `dt_adm` is present and valid, but since the question asks for a specific comparison, we will assume the question intends to count cases where `dt_adm` is present and valid, which means counting all rows in the `enc` table.

However, since the question asks for a specific
    ОШИБКА: OperationalError: near "date": syntax error

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: модель выдала прозу вместо SQL, запрос не исполняется

## 18. public_services/gov2-031 ru/0

ловушка: how many services exist is a fact of the service table, not a number to hard-code; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT applicant_id FROM case_rec GROUP BY applicant_id HAVING COUNT(DISTINCT service_id) = (SELECT COUNT(*) FROM service))
    (4,)

ответ модели:
    SELECT 
  s.title AS service_title,
  COUNT(c.applicant_id) AS applicant_count
FROM 
  case_rec c
JOIN 
  service s ON c.service_id = s.id
GROUP BY 
  s.title
    ('building permit', 149)
    ('business registration', 144)
    ('land record extract', 183)
    ('residence certificate', 130)
    ('trading licence', 154)

ошибка исполнения: нет

вердикт: model
заметка: посчитаны заявители по каждой услуге вместо тех, кто воспользовался всеми

## 19. public_services/gov2-032 ru/0

ловушка: the last stage is the largest seq of that case, which is a correlated subquery; refused is result_cd = 2, a code and not a word; the question asks which, so the count is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title FROM stage s JOIN case_rec c ON c.id = s.case_id JOIN service sv ON sv.id = c.service_id WHERE s.seq = (SELECT MAX(s2.seq) FROM stage s2 WHERE s2.case_id = s.case_id) AND s.result_cd = 2 GROUP BY sv.title ORDER BY COUNT(*) DESC, sv.title LIMIT 1
    ('building permit',)

ответ модели:
    SELECT s.title AS service_title
FROM service s
JOIN case_rec c ON s.id = c.service_id
JOIN stage st ON c.id = st.case_id
WHERE st.seq = (
    SELECT MAX(seq)
    FROM stage
    WHERE case_id = c.id
)
AND st.result_cd = 'REJECT'
GROUP BY s.title
ORDER BY COUNT(*) DESC
LIMIT 1
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пусто: result_cd='REJECT' вместо кода 2

## 20. public_services/gov2-042 ru/0

ловушка: the applicant's city holds a region name, so the comparison is between a column of one table and a column of another; an applicant with no city recorded matches nothing, because NULL is not equal to anything, and still belongs in the denominator; three joins to reach the region from the case
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS region, ROUND(100.0 * SUM(CASE WHEN a.city = r.title THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct FROM case_rec c JOIN applicant a ON a.id = c.applicant_id JOIN office o ON o.id = c.office_id JOIN region_ref r ON r.cd = o.region_cd GROUP BY r.title ORDER BY pct DESC, r.title
    ('Thorne', 26.24)
    ('Eastvale', 21.95)
    ('Marden', 20.27)
    ('Northport', 17.59)

ответ модели:
    WITH RegionCases AS (
    SELECT 
        o.region_cd,
        COUNT(*) AS total_cases
    FROM case_rec cr
    JOIN office o ON cr.office_id = o.id
    GROUP BY o.region_cd
),
ApplicantCases AS (
    SELECT 
        o.region_cd,
        COUNT(*) AS applicant_cases
    FROM case_rec cr
    JOIN office o ON cr.office_id = o.id
    JOIN applicant a ON cr.applicant_id = a.id
    WHERE a.city = o.title
    GROUP BY o.region_cd
)
SELECT 
    rc.region_cd,
    (ac.applicant_cases * 100.0 / rc.total_cases) AS percentage
FROM RegionCases rc
JOIN ApplicantCases ac ON rc.region_cd = ac.region_cd
ORDER BY rc.region_cd
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пусто: сравнение a.city с o.title вместо названия региона
