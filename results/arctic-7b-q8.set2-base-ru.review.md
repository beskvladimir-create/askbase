# Ручной разбор провалов: arctic-7b-q8.set2-base-ru.jsonl

Провалов всего: 413 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-015 ru/1

ловушка: the merchant category is a code, its name lives in mcc_ref; spending is dir_cd = 1, a code and not a sign; amounts are minor units and must be divided by 100
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT SUM(t.amt_cents) / 100.0 AS spent FROM txn t JOIN mcc_ref m ON m.code = t.mcc WHERE m.title = 'grocery stores' AND t.dir_cd = 1
    (49332.21,)

ответ модели:
    SELECT SUM(txn.amt_cents / 100.0) AS total_expenses
FROM txn
INNER JOIN mcc_ref ON txn.mcc = mcc_ref.code
WHERE txn.dir_cd = 'D' AND mcc_ref.title LIKE '%Product%'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: dir_cd сравнивается со строкой 'D' вместо кода 1, категория ищется по LIKE '%Product%', сумма вышла пустой

## 2. banking/bank2-037 ru/0

ловушка: two conditions of opposite sign on the same table, and dropping either one changes the set; a customer with no account at all must not be counted among them
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT c.full_name FROM cust c WHERE EXISTS (SELECT 1 FROM acct a WHERE a.cust_id = c.id) AND NOT EXISTS (SELECT 1 FROM acct a WHERE a.cust_id = c.id AND a.closed_at IS NULL) ORDER BY c.full_name
    ('Alina Almeida',)
    ('Alina Petran',)
    ('Anna Bauer',)
    ('Boris Kovach',)
    ('Daniel Oduya',)
    ('Elena Kristof',)
    ('Elena Reiner',)
    ('Igor Linde',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT c.full_name
FROM cust c
INNER JOIN acct a ON c.id = a.cust_id
WHERE a.closed_at IS NOT NULL
    ('Vera Almeida',)
    ('Vera Linde',)
    ('Irina Oduya',)
    ('Pavel Petran',)
    ('Anna Petran',)
    ('Igor Linde',)
    ('Anna Bauer',)
    ('Alina Almeida',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: выбраны клиенты, у которых есть хоть один закрытый счёт, а спрошены те, у кого закрыты все; множества разные

## 3. hr/hr2-002 ru/1

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
  d.title AS department_title,
  ROUND(AVG(ph.amount_minor), 2) AS average_salary
FROM 
  dept d
INNER JOIN 
  emp e ON d.id = e.dept_id
INNER JOIN 
  pay_hist ph ON e.id = ph.emp_id
INNER JOIN 
  cur_ref cr ON ph.cur_cd = cr.cd
WHERE 
  cr.title = 'Euro'
GROUP BY 
  d.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: нет деления на 100 и нет отбора последней строки истории, результат пуст

## 4. hr/hr2-033 ru/1

ловушка: unpaid leave is status_cd = 2, a code and not a word; the question counts people, so several absences must not multiply the count
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(DISTINCT e.id) AS n FROM emp e JOIN absence a ON a.emp_id = e.id WHERE e.status_cd = 2
    (11,)

ответ модели:
    SELECT COUNT(e.id) AS total_employees
FROM emp e
INNER JOIN absence a ON e.id = a.emp_id
INNER JOIN emp_status_ref esr ON e.status_cd = esr.cd
WHERE esr.title = 'неоплачиваемый отпуск'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: статус ищется по русскому слову в справочнике, которого там нет, и без DISTINCT; 0 против 11

## 5. hr/hr2-047 ru/0

ловушка: the salary in force is the latest from_dt per person, so the history would widen every spread; the ordering key is a difference of two aggregates, and it is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title FROM emp e JOIN dept d ON d.id = e.dept_id JOIN pay_hist p ON p.emp_id = e.id WHERE e.status_cd = 1 AND p.cur_cd = 1 AND p.from_dt = (SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id) GROUP BY d.title ORDER BY MAX(p.amount_minor) - MIN(p.amount_minor) DESC, d.title LIMIT 1
    ('Operations',)

ответ модели:
    WITH SalaryInEuro AS (
    SELECT 
        p.emp_id,
        p.amount_minor,
        e.dept_id
    FROM pay_hist p
    JOIN cur_ref c ON p.cur_cd = c.cd
    JOIN emp e ON p.emp_id = e.id
    WHERE c.title = 'Euro'
),
DepartmentSalaries AS (
    SELECT 
        dept_id,
        MAX(amount_minor) AS max_salary,
        MIN(amount_minor) AS min_salary
    FROM SalaryInEuro
    GROUP BY dept_id
)
SELECT 
    d.title AS department_title,
    ds.max_salary - ds.min_salary AS salary_gap
FROM DepartmentSalaries ds
JOIN dept d ON ds.dept_id = d.id
ORDER BY salary_gap DESC
LIMIT 1
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: нет отбора действующей ставки и работающих сотрудников, лишняя колонка, результат пуст

## 6. logistics/log2-006 ru/1

ловушка: distance per shipment means summing its legs first and averaging after, not averaging the legs
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(total), 1) AS mean_km FROM (SELECT SUM(dist_km) AS total FROM leg GROUP BY shp_id)
    (3668.7,)

ответ модели:
    SELECT ROUND(AVG(dist_km), 2) AS average_distance
FROM leg
    (1328.89,)

ошибка исполнения: нет

вердикт: model
заметка: усреднены плечи, а не отправления: 1328.89 против 3668.7

## 7. logistics/log2-016 ru/1

ловушка: the question asks who, so the distance is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT c.title FROM carr c JOIN leg l ON l.carr_id = c.id GROUP BY c.id, c.title ORDER BY SUM(l.dist_km) DESC, c.title LIMIT 1
    ('Petran Freight',)

ответ модели:
    SELECT 
    carr.title AS carrier_title,
    SUM(leg.dist_km) AS total_distance
FROM 
    carr
JOIN 
    leg ON carr.id = leg.carr_id
GROUP BY 
    carr.title
ORDER BY 
    total_distance DESC
LIMIT 1
    ('Petran Freight', 172478)

ошибка исполнения: нет

вердикт: evaluator
заметка: перевозчик тот же, Petran Freight, рядом выведен сам пробег, которого вопрос не просил; по правилу лишние колонки это ложное срабатывание

## 8. logistics/log2-034 ru/0

ловушка: the status says delivered while the date says the delivery has not happened yet; today is a literal in the question, there is no current date in the data
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE delivered_at > '2026-11-02'
    (19,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
WHERE dt_disp > '2026-11-02'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: взята дата отправки dt_disp вместо даты сдачи delivered_at, 0 против 19

## 9. logistics/log2-045 ru/0

ловушка: the country of arrival is two steps from the leg: shipment, then the destination code; the destination end, not the origin; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT l.carr_id FROM leg l JOIN shp s ON s.id = l.shp_id JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY l.carr_id HAVING COUNT(DISTINCT d.country) > 1)
    (45,)

ответ модели:
    SELECT COUNT(*) AS num_carriers
FROM (
  SELECT c.id AS carrier_id
  FROM carr c
  JOIN shp s ON c.id = s.carr_id
  JOIN loc_ref l ON s.dst_cd = l.cd
  GROUP BY c.id
  HAVING COUNT(DISTINCT l.country) > 1
) AS carriers_with_multiple_countries
    ОШИБКА: OperationalError: no such column: s.carr_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполняется: в shp нет колонки carr_id

## 10. manufacturing/mfg2-003 ru/0

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
    p.code AS part_code,
    SUM(m.qty * ur.to_base) AS total_defect_quantity
FROM 
    mov m
INNER JOIN 
    defect d ON m.id = d.mov_id
INNER JOIN 
    unit_ref ur ON m.unit_cd = ur.cd
INNER JOIN 
    part p ON m.part_id = p.id
GROUP BY 
    p.code
    ('BR-100', 106736.0)
    ('BU-550', 18796.0)
    ('GR-440', 34527.0)
    ('PL-330', 20999.0)
    ('SH-210', 50023.0)
    ('SP-660', 1676.0)

ошибка исполнения: нет

вердикт: model
заметка: лишнее соединение с defect размножило строки, все шесть чисел другие

## 11. manufacturing/mfg2-007 ru/1

ловушка: the price table joined to itself under two aliases, each picked by a different rule; a percentage needs 100.0, because integer division returns zero
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, ROUND(100.0 * (last.minor - first.minor) / first.minor, 1) AS pct FROM part p JOIN part_price last ON last.part_id = p.id AND last.valid_to IS NULL JOIN part_price first ON first.part_id = p.id AND first.valid_from = ( SELECT MIN(p2.valid_from) FROM part_price p2 WHERE p2.part_id = p.id ) ORDER BY pct DESC, p.code
    ('PL-330', 51.0)
    ('SP-660', 46.7)
    ('SH-210', 46.6)
    ('BR-100', 42.7)
    ('GR-440', 41.0)
    ('BU-550', 34.3)

ответ модели:
    WITH FirstPrice AS (
    SELECT 
        part_id,
        MIN(valid_from) AS first_valid_from
    FROM 
        part_price
    GROUP BY 
        part_id
)
SELECT 
    pp.part_id,
    ((pp.minor - fp_first.minor) * 100.0 / fp_first.minor) AS price_difference_percentage
FROM 
    part_price pp
JOIN 
    FirstPrice fp ON pp.part_id = fp.part_id AND pp.valid_from = fp.first_valid_from
JOIN 
    part_price fp_first ON pp.part_id = fp_first.part_id AND fp_first.valid_from = fp.first_valid_from
WHERE 
    pp.valid_to IS NULL
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: первое окно соединено само с собой вместо открытого, результат пуст

## 12. manufacturing/mfg2-024 ru/0

ловушка: the range join; a join on part_id alone inflates the total about fourfold and the single number gives no hint of it; the conversion and the minor units both apply to every row
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(m.qty * u.to_base * pp.minor / 100.0), 2) AS total FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part_price pp ON pp.part_id = m.part_id AND COALESCE(m.dt_op, m.recorded_at) >= pp.valid_from AND (pp.valid_to IS NULL OR COALESCE(m.dt_op, m.recorded_at) < pp.valid_to)
    (28968594.26,)

ответ модели:
    SELECT SUM(m.qty * pp.minor) AS total_cost
FROM mov m
INNER JOIN part_price pp ON m.part_id = pp.part_id
WHERE m.dt_op BETWEEN pp.valid_from AND pp.valid_to
    (372742658.34,)

ошибка исполнения: нет

вердикт: model
заметка: соединение по part_id без диапазона дат раздуло сумму в тринадцать раз, 372742658 против 28968594

## 13. manufacturing/mfg2-027 ru/1

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
    p.code AS part_code,
    MAX(julianday(d.found_at) - julianday(m.recorded_at)) AS max_days_to_defect
FROM 
    mov m
INNER JOIN 
    defect d ON m.id = d.mov_id
INNER JOIN 
    part p ON m.part_id = p.id
GROUP BY 
    p.code
    ('BR-100', 314.0)
    ('BU-550', 143.0)
    ('GR-440', 49.0)
    ('PL-330', 36.0)
    ('SH-210', 213.0)
    ('SP-660', None)

ошибка исполнения: нет

вердикт: model
заметка: дата движения взята только из recorded_at без COALESCE с dt_op, все шесть чисел другие

## 14. manufacturing/mfg2-033 ru/0

ловушка: part_price joined twice to itself, once for the open window and once for the earliest; the open window is the one with no valid_to, which no date comparison finds; the question asks which, so the difference is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code FROM part p JOIN part_price a ON a.part_id = p.id AND a.valid_to IS NULL JOIN part_price b ON b.part_id = p.id AND b.valid_from = (SELECT MIN(x.valid_from) FROM part_price x WHERE x.part_id = p.id) ORDER BY a.minor - b.minor DESC, p.code LIMIT 1
    ('PL-330',)

ответ модели:
    WITH PartPriceCTE AS (
    SELECT 
        pp.part_id,
        pp.valid_from,
        pp.minor,
        ROW_NUMBER() OVER (PARTITION BY pp.part_id ORDER BY pp.valid_from) AS price_rank,
        LEAD(pp.minor) OVER (PARTITION BY pp.part_id ORDER BY pp.valid_from) AS next_minor
    FROM part_price pp
),
PriceIncreaseCTE AS (
    SELECT 
        ppc.part_id,
        p.title AS part_title,
        ppc.valid_from,
        ppc.minor AS current_minor,
        ppc.next_minor,
        (ppc.next_minor - ppc.minor) AS price_increase
    FROM PartPriceCTE ppc
    INNER JOIN part p ON ppc.part_id = p.id
    WHERE ppc.price_rank = 1 AND ppc.next_minor IS NOT NULL
)
SELECT 
    pic.part_title,
    ABS(pic.price_increase) AS absolute_price_increase
FROM PriceIncreaseCTE pic
ORDER BY absolute_price_increase DESC
LIMIT 1
    ('plate', 1050)

ошибка исполнения: нет

вердикт: evaluator
заметка: деталь та же, plate это PL-330, проверил по справочнику part; отличия только в названии вместо кода и в лишней колонке с приростом. Логика у модели другая, второе окно вместо открытого, но сущность совпала

## 15. manufacturing/mfg2-035 ru/0

ловушка: the question is about the columns themselves, so coalescing them destroys the answer; exactly one of the two is populated per row, which the two sums together have to show
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT l.title, SUM(CASE WHEN m.dt_op IS NOT NULL THEN 1 ELSE 0 END) AS legacy_column, SUM(CASE WHEN m.recorded_at IS NOT NULL THEN 1 ELSE 0 END) AS new_column FROM mov m JOIN line l ON l.id = m.line_id GROUP BY l.title ORDER BY l.title
    ('Assembly A', 155, 75)
    ('Assembly B', 164, 62)
    ('Finishing', 137, 71)
    ('Machining', 159, 77)

ответ модели:
    SELECT 
  line_id,
  SUM(CASE WHEN dt_op IS NOT NULL THEN 1 ELSE 0 END) AS old_date_count,
  SUM(CASE WHEN recorded_at IS NOT NULL THEN 1 ELSE 0 END) AS new_date_count
FROM 
  mov
GROUP BY 
  line_id
    (1, 155, 75)
    (2, 164, 62)
    (3, 159, 77)
    (4, 137, 71)

ошибка исполнения: нет

вердикт: evaluator
заметка: те же четыре пары чисел, линия названа идентификатором вместо названия: 1 это Assembly A, 2 Assembly B, 3 Machining, 4 Finishing, проверил по таблице line

## 16. medicine/med2-012 ru/0

ловушка: HAVING on a filtered count, not WHERE; the filter on primary_flag has to apply before the count, not after
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT e.id, COUNT(*) AS n FROM enc e JOIN dx d ON d.enc_id = e.id WHERE d.primary_flag = 1 GROUP BY e.id HAVING COUNT(*) > 1 ORDER BY n DESC, e.id
    (189, 6)
    (246, 4)
    (279, 4)
    (301, 4)
    (370, 4)
    (419, 4)
    (610, 4)
    (618, 4)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT 
    e.enc_id, 
    COUNT(d.code) AS primary_diagnosis_count
FROM 
    enc e
INNER JOIN 
    dx d ON e.id = d.enc_id
WHERE 
    d.primary_flag = 1
GROUP BY 
    e.enc_id
HAVING 
    COUNT(d.code) > 1
    ОШИБКА: OperationalError: no such column: e.enc_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполняется: в enc нет колонки enc_id

## 17. medicine/med2-024 ru/0

ловушка: the question is about the migration itself, so the two columns must be counted apart instead of being merged with COALESCE; the status name comes from the lookup
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS status, SUM(CASE WHEN e.dt_adm IS NOT NULL THEN 1 ELSE 0 END) AS legacy_column, SUM(CASE WHEN e.admitted_at IS NOT NULL THEN 1 ELSE 0 END) AS new_column FROM enc e JOIN status_ref r ON r.cd = e.status_cd GROUP BY r.title ORDER BY r.title
    ('active', 45, 97)
    ('cancelled', 25, 45)
    ('discharged', 184, 434)
    ('planned', 16, 54)

ответ модели:
    SELECT 
    e.status_cd,
    SUM(CASE WHEN e.admitted_at IS NOT NULL AND e.dt_adm IS NULL THEN 1 ELSE 0 END) AS admitted_at_count,
    SUM(CASE WHEN e.admitted_at IS NULL AND e.dt_adm IS NOT NULL THEN 1 ELSE 0 END) AS dt_adm_count
FROM 
    enc e
GROUP BY 
    e.status_cd
    (0, 54, 16)
    (1, 97, 45)
    (2, 434, 184)
    (3, 45, 25)

ошибка исполнения: нет

вердикт: model
заметка: числа верные, но колонки переставлены местами, сначала новая, потом старая, а вопрос порядок задаёт прямо: сколько по старой колонке, а сколько по новой. Расширение правила про порядок колонок сюда не распространяется

## 18. public_services/gov2-029 ru/1

ловушка: two joins to reach the region: the case carries an office and the office carries the region code; the difference between two text dates needs julianday; a case closed exactly on the deadline is not late and must not enter the average
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS region, ROUND(AVG(julianday(c.closed_at) - julianday(c.due_dt)), 2) AS days FROM case_rec c JOIN office o ON o.id = c.office_id JOIN region_ref r ON r.cd = o.region_cd WHERE c.closed_at > c.due_dt GROUP BY r.title ORDER BY days DESC, r.title
    ('Northport', 21.83)
    ('Thorne', 21.11)
    ('Eastvale', 20.29)
    ('Marden', 20.14)

ответ модели:
    SELECT 
  o.region_cd,
  ROUND(AVG(julianday(c.closed_at) - julianday(c.due_dt)), 2) AS avg_days_overdue
FROM 
  case_rec c
INNER JOIN 
  office o ON c.office_id = o.id
WHERE 
  c.closed_at > c.due_dt
GROUP BY 
  o.region_cd
    (1, 21.83)
    (2, 20.29)
    (3, 20.14)
    (4, 21.11)

ошибка исполнения: нет

вердикт: evaluator
заметка: те же четыре средних, регион назван кодом вместо названия: 1 это Northport, 2 Eastvale, 3 Marden, 4 Thorne, проверил по region_ref

## 19. public_services/gov2-030 ru/1

ловушка: how many regions exist is a fact of region_ref, not a number to hard-code; the region is one step beyond the office, which is itself one step beyond the case
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT c.applicant_id FROM case_rec c JOIN office o ON o.id = c.office_id GROUP BY c.applicant_id HAVING COUNT(DISTINCT o.region_cd) = (SELECT COUNT(*) FROM region_ref))
    (21,)

ответ модели:
    SELECT r.title AS region_title, COUNT(*) AS applicant_count
FROM region_ref r
INNER JOIN office o ON r.cd = o.region_cd
INNER JOIN case_rec c ON o.id = c.office_id
GROUP BY r.title
    ('Eastvale', 164)
    ('Marden', 148)
    ('Northport', 307)
    ('Thorne', 141)

ошибка исполнения: нет

вердикт: model
заметка: посчитаны дела по регионам, а спрошено число людей, у которых дело есть в каждом регионе; 21 против четырёх строк

## 20. public_services/gov2-039 ru/1

ловушка: the share is of two aggregates over the same group, and the numerator carries two conditions at once; an integer division returns zero here, the ratio has to be taken in floating point; the question asks which, so the share is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT o.title FROM case_rec c JOIN office o ON o.id = c.office_id GROUP BY o.title ORDER BY SUM(CASE WHEN c.closed_at IS NULL AND c.due_dt < '2026-11-02' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) DESC, o.title LIMIT 1
    ('Northport east',)

ответ модели:
    SELECT o.title
FROM case_rec cr
JOIN office o ON cr.office_id = o.id
WHERE cr.dt_sub LIKE '2026-11-02%'
GROUP BY o.title
ORDER BY COUNT(*) DESC
LIMIT 1
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: доля не считается вовсе, вместо неё отбор по дате подачи, результат пуст
