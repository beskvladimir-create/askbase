# Ручной разбор провалов: arctic-7b-q8.set2-base-en.jsonl

Провалов всего: 390 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-017 en/1

ловушка: the operation date is split across the legacy pair dt_op/posted_at; dates are text, so the month is the first seven characters
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT substr(COALESCE(dt_op, posted_at), 1, 7) AS month, COUNT(*) AS n FROM txn WHERE COALESCE(dt_op, posted_at) >= '2026-01-01' GROUP BY month ORDER BY month
    ('2026-01', 152)
    ('2026-02', 120)
    ('2026-03', 127)
    ('2026-04', 148)
    ('2026-05', 157)
    ('2026-06', 117)
    ('2026-07', 118)
    ('2026-08', 141)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT 
  strftime('%m', dt_op) AS month, 
  COUNT(*) AS operation_count
FROM 
  txn
WHERE 
  dt_op BETWEEN '2026-01-01' AND '2026-12-31'
GROUP BY 
  strftime('%m', dt_op)
ORDER BY 
  month
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пусто: strftime по dt_op, в котором часть дат NULL, нет COALESCE с posted_at

## 2. banking/bank2-039 en/1

ловушка: the earliest date is a correlated subquery, one per account; the operation date is split across the legacy pair dt_op/posted_at; an account with no transaction yields NULL, which the comparison drops rather than counts
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM acct a WHERE (SELECT MIN(COALESCE(t.dt_op, t.posted_at)) FROM txn t WHERE t.acct_id = a.id) < a.opened_at
    (65,)

ответ модели:
    SELECT COUNT(*) AS num_accounts_with_early_transactions
FROM (
    SELECT a.id AS acct_id, MIN(t.dt_op) AS first_transaction_date
    FROM acct a
    JOIN txn t ON a.id = t.acct_id
    GROUP BY a.id
) AS early_transactions
JOIN acct a ON early_transactions.acct_id = a.id
WHERE early_transactions.first_transaction_date < a.opened_at
    (56,)

ошибка исполнения: нет

вердикт: model
заметка: 56 вместо 65: JOIN отбросил счёта без операций, нет COALESCE по паре дат

## 3. hr/hr2-005 en/1

ловушка: the status name comes from the lookup; two counts over one pass, not two queries
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT s.title AS status, SUM(CASE WHEN e.left_at IS NULL THEN 1 ELSE 0 END) AS without_date, SUM(CASE WHEN e.left_at IS NOT NULL THEN 1 ELSE 0 END) AS with_date FROM emp e JOIN emp_status_ref s ON s.cd = e.status_cd GROUP BY s.title ORDER BY s.title
    ('left', 0, 56)
    ('unpaid leave', 13, 0)
    ('working', 191, 0)

ответ модели:
    SELECT 
    esr.title AS status_name,
    SUM(CASE WHEN e.left_at IS NOT NULL THEN 1 ELSE 0 END) AS headcount_with_left_date,
    SUM(CASE WHEN e.left_at IS NULL THEN 1 ELSE 0 END) AS headcount_without_left_date
FROM 
    emp e
JOIN 
    emp_status_ref esr ON e.status_cd = esr.cd
GROUP BY 
    esr.title
    ('left', 56, 0)
    ('unpaid leave', 0, 13)
    ('working', 0, 191)

ошибка исполнения: нет

вердикт: evaluator
заметка: те же два числа, но колонки 'с датой' и 'без даты' в обратном порядке; вопрос порядок не задаёт, эталон его навязывает. Единственный такой случай на 300 разобранных

## 4. hr/hr2-038 en/0

ловушка: dept joined twice to itself, and COALESCE on the parent is what rolls a sub-department up to its top; the salary in force is the latest from_dt per person, so a plain join multiplies the total by the number of revisions; the currencies must not be added together, so the euro rows are the only ones that count
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT top.title, SUM(p.amount_minor) / 100.0 AS payroll FROM emp e JOIN dept d ON d.id = e.dept_id JOIN dept top ON top.id = COALESCE(d.parent_id, d.id) JOIN pay_hist p ON p.emp_id = e.id WHERE e.status_cd = 1 AND p.cur_cd = 1 AND p.from_dt = (SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id) GROUP BY top.title ORDER BY payroll DESC, top.title
    ('Engineering', 357940.0)
    ('Operations', 254790.0)
    ('Finance', 181600.0)

ответ модели:
    WITH RECURSIVE DepartmentHierarchy AS (
    SELECT id, title, parent_id
    FROM dept
    WHERE parent_id IS NULL
    UNION ALL
    SELECT d.id, d.title, d.parent_id
    FROM dept d
    JOIN DepartmentHierarchy dh ON d.parent_id = dh.id
)
SELECT dh.title AS department_title, SUM(ph.amount_minor) AS total_payment_minor
FROM DepartmentHierarchy dh
JOIN emp e ON dh.id = e.dept_id
JOIN pay_hist ph ON e.id = ph.emp_id
WHERE ph.cur_cd = 'EUR'
GROUP BY dh.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пусто: cur_cd='EUR' вместо кода 1, нет отбора действующей ставки

## 5. logistics/log2-002 en/0

ловушка: loc_ref is joined twice under two aliases, once per end of the route
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT o.title AS origin, d.title AS destination, COUNT(*) AS n FROM shp s JOIN loc_ref o ON o.cd = s.org_cd JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY o.title, d.title ORDER BY n DESC, o.title, d.title
    ('Avelin', 'Harrow', 18)
    ('Eastvale', 'Avelin', 18)
    ('Thorne', 'Kesling', 17)
    ('Eastvale', 'Kesling', 16)
    ('Harrow', 'Lowick', 16)
    ('Kesling', 'Thorne', 16)
    ('Northport', 'Avelin', 16)
    ('Thorne', 'Eastvale', 16)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT 
  c1.title AS origin_city, 
  c2.title AS destination_city, 
  COUNT(s.id) AS total_shipments
FROM 
  shp s
  INNER JOIN cust c1 ON s.org_cd = c1.id
  INNER JOIN cust c2 ON s.dst_cd = c2.id
GROUP BY 
  c1.title, c2.title
    ('Alder Freight', 'Brackwater Transit', 27)
    ('Alder Freight', 'Castwell Freight', 8)
    ('Alder Freight', 'Kestrel Transit', 12)
    ('Alder Freight', 'Solvay Freight', 5)
    ('Alder Freight', 'Solvay Haulage', 16)
    ('Alder Freight', 'Solvay Logistics', 10)
    ('Brackwater Transit', 'Alder Freight', 29)
    ('Brackwater Transit', 'Brackwater Transit', 30)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: соединение с cust вместо loc_ref: в ответе названия перевозчиков, а не городов

## 6. logistics/log2-004 en/0

ловушка: the status and the delivery date disagree by design, and the question is about exactly that disagreement
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 3 AND delivered_at IS NOT NULL
    (15,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
JOIN status_ref ON shp.status_cd = status_ref.cd 
WHERE status_ref.title = 'Lost' AND shp.dt_disp IS NOT NULL
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: 0 вместо 15: взята dt_disp вместо delivered_at и название статуса вместо кода 3

## 7. logistics/log2-017 en/0

ловушка: in transit is status_cd = 1, a code and not a word; the destination is a code, its name lives in loc_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title AS destination, COUNT(*) AS n FROM shp s JOIN loc_ref d ON d.cd = s.dst_cd WHERE s.status_cd = 1 GROUP BY d.title ORDER BY n DESC, d.title
    ('Harrow', 19)
    ('Marden', 16)
    ('Avelin', 13)
    ('Eastvale', 13)
    ('Lowick', 12)
    ('Kesling', 10)
    ('Northport', 10)
    ('Thorne', 10)

ответ модели:
    SELECT c.city, COUNT(s.id) AS total_shipments
FROM shp s
JOIN cust c ON s.dst_cd = c.id
JOIN status_ref sr ON s.status_cd = sr.cd
WHERE sr.title = 'In Transit'
GROUP BY c.city
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пусто: соединение с cust по dst_cd и фильтр по названию статуса

## 8. logistics/log2-025 en/0

ловушка: the dispatch date is split across the legacy pair dt_disp/dispatched_at; the comparison is between two columns of two tables, not against a literal
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM inc i JOIN shp s ON s.id = i.shp_id WHERE i.at < COALESCE(s.dt_disp, s.dispatched_at)
    (136,)

ответ модели:
    SELECT COUNT(*) AS total_incidents
FROM inc i
JOIN shp s ON i.shp_id = s.id
WHERE i.at < s.dt_disp
    (17,)

ошибка исполнения: нет

вердикт: model
заметка: 17 вместо 136: нет COALESCE по паре дат отправки

## 9. logistics/log2-044 en/0

ловушка: the cost is a sum over legs while the weight is a single column of the shipment; an integer division returns zero here, the ratio has to be taken in floating point; the question asks which, so the ratio is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT s.id FROM shp s JOIN leg l ON l.shp_id = s.id GROUP BY s.id, s.weight_kg ORDER BY SUM(l.cost_cents) * 1.0 / s.weight_kg DESC, s.id LIMIT 1
    (271,)

ответ модели:
    SELECT 
  shp.id AS shipment_id,
  (leg.cost_cents / shp.weight_kg) AS cost_per_kg
FROM 
  shp
JOIN 
  leg ON shp.id = leg.shp_id
ORDER BY 
  cost_per_kg DESC
LIMIT 1
    (271, 17885)

ошибка исполнения: нет

вердикт: evaluator
заметка: перевозка та же, 271, но в ответе лишняя колонка с отношением; по правилу лишние колонки это ложное срабатывание. Логика ранжирования у модели другая, совпадение сущности проверено

## 10. manufacturing/mfg2-003 en/0

ловушка: 'scrap' is kind_cd = 3, a code with no word in the table; the conversion factor comes from unit_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title, ROUND(SUM(m.qty * u.to_base), 2) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id WHERE m.kind_cd = 3 GROUP BY p.title ORDER BY base_qty DESC, p.title
    ('bracket', 44187.0)
    ('shaft', 19889.0)
    ('bushing', 11533.0)
    ('plate', 8923.0)
    ('gearwheel', 3595.0)
    ('spring', 902.0)

ответ модели:
    SELECT 
    m.part_id,
    SUM(m.qty * u.to_base) AS total_scrapped_quantity
FROM 
    mov m
INNER JOIN 
    mov_kind_ref mk ON m.kind_cd = mk.cd
INNER JOIN 
    unit_ref u ON m.unit_cd = u.cd
WHERE 
    mk.title = 'SCRAP'
GROUP BY 
    m.part_id
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пусто: фильтр mov_kind_ref.title='SCRAP' вместо кода 3

## 11. manufacturing/mfg2-008 en/1

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
    m.part_id, 
    SUM(m.qty * p.minor) AS total_value
FROM 
    mov m
JOIN 
    part_price p ON m.part_id = p.part_id 
    AND m.dt_op BETWEEN p.valid_from AND p.valid_to
GROUP BY 
    m.part_id
    (1, 64333787.77)
    (2, 36634321.6)
    (3, 183894490.24)
    (4, 52714222.28)
    (5, 29024281.45)
    (6, 6141555.0)

ошибка исполнения: нет

вердикт: model
заметка: значения другие и part_id вместо названия: BETWEEN не находит открытое окно с valid_to IS NULL

## 12. manufacturing/mfg2-013 en/1

ловушка: the comparison has a direction, and getting it backwards returns the complement without any sign of error; the movement date comes from the legacy pair
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM defect d JOIN mov m ON m.id = d.mov_id WHERE d.found_at < COALESCE(m.dt_op, m.recorded_at)
    (137,)

ответ модели:
    SELECT COUNT(*) AS defect_count
FROM defect d
INNER JOIN mov m ON d.mov_id = m.id
WHERE d.found_at < m.recorded_at
    (86,)

ошибка исполнения: нет

вердикт: model
заметка: 86 вместо 137: нет COALESCE по паре дат движения

## 13. manufacturing/mfg2-031 en/0

ловушка: the price is joined on a range, and a plain join on part_id multiplies every movement by its number of price windows; the quantity has to be converted before it is multiplied by the price; the question asks which, so the value is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT m.id FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part_price pp ON pp.part_id = m.part_id AND pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at)) ORDER BY m.qty * u.to_base * pp.minor DESC, m.id LIMIT 1
    (209,)

ответ модели:
    SELECT 
  m.id AS movement_id,
  m.dt_op AS movement_date,
  m.qty AS quantity,
  pp.minor AS price_minor,
  (m.qty * pp.minor) AS total_value
FROM 
  mov m
INNER JOIN 
  part_price pp ON m.part_id = pp.part_id
WHERE 
  pp.valid_from <= m.dt_op AND pp.valid_to >= m.dt_op
ORDER BY 
  (m.qty * pp.minor) DESC
LIMIT 1
    (155, '2025-07-13', 395.0, 11648, 4600960.0)

ошибка исполнения: нет

вердикт: model
заметка: движение 155 вместо 209: нет перевода в базовую единицу и открытое окно не найдено

## 14. manufacturing/mfg2-033 en/0

ловушка: part_price joined twice to itself, once for the open window and once for the earliest; the open window is the one with no valid_to, which no date comparison finds; the question asks which, so the difference is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code FROM part p JOIN part_price a ON a.part_id = p.id AND a.valid_to IS NULL JOIN part_price b ON b.part_id = p.id AND b.valid_from = (SELECT MIN(x.valid_from) FROM part_price x WHERE x.part_id = p.id) ORDER BY a.minor - b.minor DESC, p.code LIMIT 1
    ('PL-330',)

ответ модели:
    WITH FirstPrice AS (
    SELECT 
        part_id,
        MIN(valid_from) AS first_valid_from
    FROM part_price
    GROUP BY part_id
),
LatestPrice AS (
    SELECT 
        part_id,
        MAX(valid_from) AS latest_valid_from
    FROM part_price
    GROUP BY part_id
),
PriceChange AS (
    SELECT 
        pp.part_id,
        pp.minor - fp.minor AS price_change
    FROM part_price pp
    JOIN FirstPrice fp ON pp.part_id = fp.part_id AND pp.valid_from = fp.first_valid_from
    JOIN LatestPrice lp ON pp.part_id = lp.part_id AND pp.valid_from = lp.latest_valid_from
)
SELECT 
    part_id,
    price_change
FROM PriceChange
ORDER BY ABS(price_change) DESC
LIMIT 1
    ОШИБКА: OperationalError: no such column: fp.minor

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: SQL не исполняется: нет колонки fp.minor

## 15. manufacturing/mfg2-040 en/0

ловушка: the same quantity has to be priced two different ways in one row of output; the open window is the one with no valid_to, while the other price is joined on a range; scrap is kind_cd = 3, a code and not a word
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(m.qty * u.to_base * pp.minor / 100.0), 2) AS at_the_time, ROUND(SUM(m.qty * u.to_base * (SELECT cur.minor FROM part_price cur WHERE cur.part_id = m.part_id AND cur.valid_to IS NULL) / 100.0), 2) AS at_today FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part_price pp ON pp.part_id = m.part_id AND pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at)) WHERE m.kind_cd = 3
    (2556728.75, 3222914.55)

ответ модели:
    SELECT 
    d.found_at,
    pp.valid_from,
    pp.valid_to,
    pp.minor * m.qty AS cost_at_defect_date,
    pp.minor * m.qty AS cost_at_today
FROM 
    defect d
JOIN 
    mov m ON d.mov_id = m.id
JOIN 
    part_price pp ON m.part_id = pp.part_id
WHERE 
    d.grade_cd = 'S'
    AND pp.valid_from <= d.found_at
    AND pp.valid_to >= d.found_at
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пусто: взяты defect и grade_cd='S' вместо движений брака

## 16. manufacturing/mfg2-041 en/1

ловушка: mov joined twice to itself, with the pair taken once by comparing ids; the movement date is split across the legacy pair, so the equality is between two coalesced expressions
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM mov a JOIN mov b ON b.part_id = a.part_id AND b.id > a.id AND COALESCE(a.dt_op, a.recorded_at) = COALESCE(b.dt_op, b.recorded_at) WHERE a.line_id <> b.line_id
    (64,)

ответ модели:
    SELECT COUNT(*) AS pair_count
FROM mov m1
JOIN mov m2 ON m1.part_id = m2.part_id AND m1.dt_op = m2.dt_op AND m1.line_id != m2.line_id
    (88,)

ошибка исполнения: нет

вердикт: model
заметка: 88 вместо 64: пара считается дважды, нет условия b.id > a.id

## 17. medicine/med2-020 en/1

ловушка: the admission date is split across the legacy pair; an empty discharge column is a NULL test, not a comparison with a date
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM enc WHERE COALESCE(dt_adm, admitted_at) >= '2026-01-01' AND discharged IS NULL
    (149,)

ответ модели:
    SELECT COUNT(*) 
FROM enc 
WHERE dt_adm LIKE '2026%' AND discharged IS NULL
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: 0 вместо 149: LIKE по dt_op, где часть дат NULL

## 18. medicine/med2-034 en/0

ловушка: the age is counted at the admission date, not at today's date; the admission date is split across the legacy pair dt_adm/admitted_at; dt_b is a text date, so the age needs julianday and a division by 365.25
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM enc e JOIN pat p ON p.id = e.pat_id WHERE (julianday(COALESCE(e.dt_adm, e.admitted_at)) - julianday(p.dt_b)) / 365.25 > 80
    (81,)

ответ модели:
    SELECT COUNT(*) AS encounter_count
FROM pat
INNER JOIN enc ON pat.id = enc.pat_id
WHERE (strftime('%Y', 'now') - strftime('%Y', pat.dt_b) - (strftime('%m-%d', 'now') < strftime('%m-%d', pat.dt_b))) > 80
    (77,)

ошибка исполнения: нет

вердикт: model
заметка: 77 вместо 81: возраст считается на сегодня, а не на дату поступления

## 19. public_services/gov2-046 en/1

ловушка: the allowance is a column of the service, so the threshold differs from row to row; the subtraction runs in the opposite direction from the usual lateness question; a case with no closing date cannot qualify and must be excluded
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL AND julianday(c.due_dt) - julianday(c.closed_at) > sv.sla_days * 1.0 / 2
    (206,)

ответ модели:
    SELECT COUNT(*) AS cases_closed_early
FROM case_rec cr
JOIN service s ON cr.service_id = s.id
WHERE (julianday(cr.closed_at) - julianday(cr.due_dt)) > (s.sla_days * 0.5)
    (147,)

ошибка исполнения: нет

вердикт: model
заметка: 147 вместо 206: вычитание в обратную сторону и нет отбора закрытых дел

## 20. public_services/gov2-048 en/0

ловушка: two conditions of opposite sign on the same table, and dropping either one changes the set; a registered person with no case at all must not be counted among them
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM applicant a WHERE EXISTS (SELECT 1 FROM case_rec c WHERE c.applicant_id = a.id) AND NOT EXISTS (SELECT 1 FROM case_rec c WHERE c.applicant_id = a.id AND c.closed_at IS NOT NULL)
    (4,)

ответ модели:
    SELECT COUNT(DISTINCT a.id) AS total_applicants_with_cases
FROM applicant a
JOIN case_rec c ON a.id = c.applicant_id
WHERE c.closed_at IS NULL
    (62,)

ошибка исполнения: нет

вердикт: model
заметка: 62 вместо 4: условие на одно дело вместо отсутствия закрытых у заявителя
