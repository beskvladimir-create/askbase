# Ручной разбор провалов: qwen25-coder-7b.set2-base-en.jsonl

Провалов всего: 427 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-013 en/1

ловушка: residency is a code, needs the lookup join
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS residency, COUNT(*) AS n FROM cust c JOIN resid_ref r ON r.cd = c.resid_cd GROUP BY r.title ORDER BY n DESC, r.title
    ('resident', 284)
    ('non-resident', 66)

ответ модели:
    SELECT 
    CASE 
        WHEN resid_cd IS NOT NULL THEN 'Resident'
        ELSE 'Non-Resident'
    END AS residency_status,
    COUNT(*) AS customer_count
FROM 
    cust
GROUP BY 
    residency_status
    ('Resident', 350)

ошибка исполнения: нет

вердикт: model
заметка: признак резидентства определяет по непустоте кода, одна строка вместо двух

## 2. banking/bank2-035 en/1

ловушка: two scalings in one expression: the principal is in minor units and the rate is in basis points; a loan with no closing date is the one the question asks about
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(principal * rate_bp) / 1000000.0, 2) AS annual_interest FROM loan WHERE closed_at IS NULL
    (476692.56,)

ответ модели:
    SELECT SUM((principal * rate_bp / 10000) * 365) AS total_interest
FROM loan
WHERE closed_at IS NULL
    (17399262380,)

ошибка исполнения: нет

вердикт: model
заметка: умножает ещё на 365 и не делит копейки, 17 миллиардов вместо 476 тысяч

## 3. hr/hr2-002 en/1

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
    ROUND(AVG(ph.amount_minor / 100.0), 2) AS mean_salary_euro
FROM 
    dept d
JOIN 
    emp e ON d.id = e.dept_id
JOIN 
    pay_hist ph ON e.id = ph.emp_id
JOIN 
    cur_ref cr ON ph.cur_cd = cr.cd
WHERE 
    cr.title = 'Euro'
GROUP BY 
    d.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: валюта ищется по названию Euro, которого в справочнике нет

## 4. hr/hr2-029 en/0

ловушка: the row before is the nearest earlier date, which is a correlated minimum and not simply the previous id; pay_hist joined twice to itself, and the pair must be adjacent rather than any two rows
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM pay_hist a JOIN pay_hist b ON b.emp_id = a.emp_id AND b.from_dt = (SELECT MIN(x.from_dt) FROM pay_hist x WHERE x.emp_id = a.emp_id AND x.from_dt > a.from_dt) WHERE b.amount_minor < a.amount_minor
    (243,)

ответ модели:
    SELECT COUNT(*) 
FROM pay_hist 
WHERE amount_minor < (SELECT amount_minor 
                      FROM pay_hist 
                      WHERE emp_id = pay_hist.emp_id 
                      ORDER BY from_dt DESC 
                      LIMIT 1)
    (62,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает с последней строкой, а не с соседней, 62 против 243

## 5. hr/hr2-041 en/1

ловушка: the earliest date is per department, which makes the subquery correlated; the same condition on the status has to hold inside the subquery as outside it; the answer is a person, so the minimum cannot simply be selected on its own
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title AS department, e.full_name FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 AND e.hired_at = (SELECT MIN(e2.hired_at) FROM emp e2 WHERE e2.dept_id = e.dept_id AND e2.status_cd = 1) ORDER BY d.title, e.full_name
    ('Data', 'Irina Soto')
    ('Engineering', 'Alina Oduya')
    ('Finance', 'Pavel Soto')
    ('Operations', 'Boris Kristof')
    ('Platform', 'Boris Almeida')
    ('Support', 'Sofia Hale')

ответ модели:
    SELECT d.title AS dept_title, e.full_name AS emp_full_name, e.hired_at AS hire_date
FROM dept d
JOIN emp e ON d.id = e.dept_id
WHERE e.status_cd = 'A' -- Assuming 'A' is the code for active employees
AND e.left_at IS NULL -- Assuming employees who have left are not considered
AND e.hired_at = (
    SELECT MIN(h.hired_at)
    FROM emp h
    WHERE h.dept_id = d.id
    AND h.status_cd = 'A'
    AND h.left_at IS NULL
)
ORDER BY d.id
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: статус сравнивается с буквой A, выдача пустая

## 6. hr/hr2-048 en/1

ловушка: dept checked against itself under another alias, by the parent reference and not by a join to the employee; working is status_cd = 1, and the leaving date does not decide it
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 AND EXISTS (SELECT 1 FROM dept c WHERE c.parent_id = d.id)
    (65,)

ответ модели:
    SELECT COUNT(e.id)
FROM emp e
JOIN dept d ON e.dept_id = d.id
WHERE d.parent_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1
    FROM dept subd
    WHERE subd.parent_id = d.id
    AND NOT EXISTS (
        SELECT 1
        FROM emp sube
        WHERE sube.dept_id = subd.id
    )
)
    (126,)

ошибка исполнения: нет

вердикт: model
заметка: ищет отделы, у всех детей которых есть сотрудники, 126 против 65

## 7. logistics/log2-011 en/0

ловушка: lost is status_cd = 3, a code and not a word; a customer with two lost shipments must appear once, not twice
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT DISTINCT c.title FROM cust c JOIN shp s ON s.cust_id = c.id WHERE s.status_cd = 3 ORDER BY c.title
    ('Alder Freight',)
    ('Brackwater Logistics',)
    ('Castwell Freight',)
    ('Castwell Haulage',)
    ('Kestrel Shipping',)
    ('Kestrel Transit',)
    ('Lumen Freight',)
    ('Lumen Haulage',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT DISTINCT c.title
FROM cust c
JOIN shp s ON c.id = s.cust_id
JOIN status_ref sr ON s.status_cd = sr.cd
WHERE sr.title = 'Lost'
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: статус ищется по названию Lost, выдача пустая

## 8. logistics/log2-034 en/0

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
заметка: сравнивает дату отправки вместо даты сдачи, ответ 0

## 9. logistics/log2-044 en/1

ловушка: the cost is a sum over legs while the weight is a single column of the shipment; an integer division returns zero here, the ratio has to be taken in floating point; the question asks which, so the ratio is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT s.id FROM shp s JOIN leg l ON l.shp_id = s.id GROUP BY s.id, s.weight_kg ORDER BY SUM(l.cost_cents) * 1.0 / s.weight_kg DESC, s.id LIMIT 1
    (271,)

ответ модели:
    SELECT shp.id, shp.weight_kg, SUM(leg.cost_cents) / shp.weight_kg AS cost_per_kg
FROM shp
JOIN leg ON shp.id = leg.shp_id
GROUP BY shp.id, shp.weight_kg
ORDER BY cost_per_kg DESC
LIMIT 1
    (271, 44, 29899)

ошибка исполнения: нет

вердикт: evaluator
заметка: та же перевозка 271, добавлены вес и отношение, которых вопрос не просил

## 10. manufacturing/mfg2-002 en/0

ловушка: pieces are not a weight, and their conversion factor is 1.0, so including them changes the answer without producing any error; tonnes convert by 1000, which is in the lookup
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(m.qty * u.to_base), 2) AS kg FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE u.title IN ('kilogram', 'tonne')
    (677143.0,)

ответ модели:
    SELECT SUM(mov.qty * unit_ref.to_base) AS total_weight_kg
FROM mov
JOIN unit_ref ON mov.unit_cd = unit_ref.cd
WHERE unit_ref.title = 'weight'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: ищет единицу с названием weight, результат None

## 11. manufacturing/mfg2-006 en/0

ловушка: the price table holds a history, so one part has several rows
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, COUNT(*) AS windows, MIN(pp.valid_from) AS first_from FROM part p JOIN part_price pp ON pp.part_id = p.id GROUP BY p.code ORDER BY p.code
    ('BR-100', 4, '2023-07-21')
    ('BU-550', 4, '2023-07-21')
    ('GR-440', 4, '2023-07-21')
    ('PL-330', 4, '2023-07-21')
    ('SH-210', 4, '2023-07-21')
    ('SP-660', 4, '2023-07-21')

ответ модели:
    SELECT p.id, p.title, COUNT(pp.id) AS price_windows, MIN(pp.valid_from) AS earliest_run
FROM part p
JOIN part_price pp ON p.id = pp.part_id
GROUP BY p.id, p.title
    (1, 'bracket', 4, '2023-07-21')
    (2, 'shaft', 4, '2023-07-21')
    (3, 'plate', 4, '2023-07-21')
    (4, 'gearwheel', 4, '2023-07-21')
    (5, 'bushing', 4, '2023-07-21')
    (6, 'spring', 4, '2023-07-21')

ошибка исполнения: нет

вердикт: evaluator
заметка: те же четыре окна и та же дата по каждой детали, деталь названа id и названием вместо кода

## 12. manufacturing/mfg2-023 en/0

ловушка: two counts over one pass, each on a different code
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT l.title, SUM(CASE WHEN m.kind_cd = 2 THEN 1 ELSE 0 END) AS receipts, SUM(CASE WHEN m.kind_cd = 1 THEN 1 ELSE 0 END) AS issues FROM mov m JOIN line l ON l.id = m.line_id GROUP BY l.title ORDER BY l.title
    ('Assembly A', 95, 96)
    ('Assembly B', 95, 105)
    ('Finishing', 88, 99)
    ('Machining', 108, 94)

ответ модели:
    SELECT 
    l.title AS line_title,
    COUNT(m.id) AS total_receipts,
    COUNT(d.id) AS total_issues
FROM 
    line l
LEFT JOIN 
    mov m ON l.id = m.line_id
LEFT JOIN 
    defect d ON m.id = d.mov_id
GROUP BY 
    l.title
    ('Assembly A', 257, 72)
    ('Assembly B', 263, 95)
    ('Finishing', 244, 84)
    ('Machining', 258, 69)

ошибка исполнения: нет

вердикт: model
заметка: считает движения и дефекты вместо поступлений и выдач

## 13. manufacturing/mfg2-025 en/0

ловушка: the answer is the number of movements, so the grouped rows have to be counted again; HAVING, which RedSQL found models get wrong most often
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT mov_id FROM defect GROUP BY mov_id HAVING COUNT(*) > 1)
    (87,)

ответ модели:
    SELECT COUNT(mov_id) AS num_movements_with_more_than_one_defect
FROM defect
GROUP BY mov_id
HAVING COUNT(id) > 1
    (2,)
    (2,)
    (2,)
    (3,)
    (3,)
    (3,)
    (2,)
    (2,)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: не считает сгруппированные строки повторно, вернул список

## 14. manufacturing/mfg2-031 en/1

ловушка: the price is joined on a range, and a plain join on part_id multiplies every movement by its number of price windows; the quantity has to be converted before it is multiplied by the price; the question asks which, so the value is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT m.id FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part_price pp ON pp.part_id = m.part_id AND pp.valid_from <= COALESCE(m.dt_op, m.recorded_at) AND (pp.valid_to IS NULL OR pp.valid_to > COALESCE(m.dt_op, m.recorded_at)) ORDER BY m.qty * u.to_base * pp.minor DESC, m.id LIMIT 1
    (209,)

ответ модели:
    SELECT m.*
FROM mov m
JOIN part_price pp ON m.part_id = pp.part_id
WHERE m.dt_op BETWEEN pp.valid_from AND pp.valid_to
ORDER BY m.qty * pp.minor DESC
LIMIT 1
    (155, 3, 4, '2025-07-13', None, 395.0, 2, 2)

ошибка исполнения: нет

вердикт: model
заметка: вернул всю строку движения и выбрал не то движение, 155 против 209

## 15. manufacturing/mfg2-033 en/0

ловушка: part_price joined twice to itself, once for the open window and once for the earliest; the open window is the one with no valid_to, which no date comparison finds; the question asks which, so the difference is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code FROM part p JOIN part_price a ON a.part_id = p.id AND a.valid_to IS NULL JOIN part_price b ON b.part_id = p.id AND b.valid_from = (SELECT MIN(x.valid_from) FROM part_price x WHERE x.part_id = p.id) ORDER BY a.minor - b.minor DESC, p.code LIMIT 1
    ('PL-330',)

ответ модели:
    SELECT p.id, p.title, MAX(pp.valid_to) - MIN(pp.valid_from) AS price_change
FROM part p
JOIN part_price pp ON p.id = pp.part_id
GROUP BY p.id, p.title
ORDER BY price_change DESC
LIMIT 1
    (1, 'bracket', 3)

ошибка исполнения: нет

вердикт: model
заметка: вычитает даты окон вместо цен

## 16. medicine/med2-007 en/1

ловушка: the admission date has to be assembled from the legacy pair; 'longer than two weeks' is a strict comparison against 14 days
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM enc WHERE status_cd = 2 AND julianday(discharged) - julianday(COALESCE(dt_adm, admitted_at)) > 14
    (210,)

ответ модели:
    SELECT COUNT(*) 
FROM enc 
WHERE status_cd = 'discharged' AND (discharged - admitted_at) > 14
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает статус со словом discharged и вычитает текстовые даты, ответ 0

## 17. public_services/gov2-023 en/0

ловушка: a NULL test inside a conditional sum, not a WHERE, because the denominator is every case of the service; a percentage needs 100.0
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title, ROUND(100.0 * SUM(CASE WHEN c.closed_at IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct FROM case_rec c JOIN service sv ON sv.id = c.service_id GROUP BY sv.title ORDER BY pct DESC, sv.title
    ('residence certificate', 13.8)
    ('building permit', 12.1)
    ('land record extract', 11.5)
    ('business registration', 9.7)
    ('trading licence', 3.9)

ответ модели:
    SELECT 
    s.title AS service_title,
    ROUND(SUM(CASE WHEN t.result_cd = 'IN_PROGRESS' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS progress_percentage
FROM 
    service s
JOIN 
    case_rec c ON s.id = c.service_id
JOIN 
    stage t ON c.id = t.case_id
GROUP BY 
    s.title
    ('building permit', 0.0)
    ('business registration', 0.0)
    ('land record extract', 0.0)
    ('residence certificate', 0.0)
    ('trading licence', 0.0)

ошибка исполнения: нет

вердикт: model
заметка: ищет результат IN_PROGRESS, все доли нулевые

## 18. public_services/gov2-026 en/0

ловушка: stage joined twice to itself, with the order given by seq rather than by id; an undecided stage is NULL in result_cd, which no equality test matches; two such pairs on one case must not count it twice
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(DISTINCT a.case_id) AS n FROM stage a JOIN stage b ON b.case_id = a.case_id AND b.seq > a.seq WHERE a.result_cd IS NULL AND b.result_cd IS NOT NULL
    (135,)

ответ модели:
    SELECT COUNT(*)
FROM stage s1
JOIN stage s2 ON s1.case_id = s2.case_id AND s1.seq < s2.seq
WHERE s1.result_cd IS NOT NULL AND s2.result_cd IS NULL
    (231,)

ошибка исполнения: нет

вердикт: model
заметка: перепутаны местами решённый и нерешённый этапы, 231 против 135

## 19. public_services/gov2-032 en/1

ловушка: the last stage is the largest seq of that case, which is a correlated subquery; refused is result_cd = 2, a code and not a word; the question asks which, so the count is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title FROM stage s JOIN case_rec c ON c.id = s.case_id JOIN service sv ON sv.id = c.service_id WHERE s.seq = (SELECT MAX(s2.seq) FROM stage s2 WHERE s2.case_id = s.case_id) AND s.result_cd = 2 GROUP BY sv.title ORDER BY COUNT(*) DESC, sv.title LIMIT 1
    ('building permit',)

ответ модели:
    SELECT s.title
FROM service s
JOIN case_rec cr ON s.id = cr.service_id
JOIN stage st ON cr.id = st.case_id
JOIN result_ref rr ON st.result_cd = rr.cd
WHERE rr.title = 'Refused'
GROUP BY s.title
ORDER BY COUNT(cr.id) DESC
LIMIT 1
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: ищет результат по названию Refused, выдача пустая

## 20. public_services/gov2-046 en/1

ловушка: the allowance is a column of the service, so the threshold differs from row to row; the subtraction runs in the opposite direction from the usual lateness question; a case with no closing date cannot qualify and must be excluded
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL AND julianday(c.due_dt) - julianday(c.closed_at) > sv.sla_days * 1.0 / 2
    (206,)

ответ модели:
    SELECT COUNT(*)
FROM case_rec cr
JOIN service s ON cr.service_id = s.id
JOIN result_ref rr ON cr.stage_id = (SELECT id FROM stage WHERE case_id = cr.id AND seq = (SELECT MAX(seq) FROM stage WHERE case_id = cr.id))
WHERE cr.closed_at < cr.due_dt AND cr.closed_at < cr.due_dt - INTERVAL (s.sla_days / 2) DAY
    ОШИБКА: OperationalError: near "DAY": syntax error

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: INTERVAL ... DAY, синтаксиса нет в SQLite
