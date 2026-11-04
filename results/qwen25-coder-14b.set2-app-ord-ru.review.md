# Ручной разбор провалов: qwen25-coder-14b.set2-app-ord-ru.jsonl

Провалов всего: 289 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-037 ru/0

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
JOIN acct a ON c.id = a.cust_id
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
заметка: берёт клиентов с любым закрытым счётом вместо тех, у кого закрыты все

## 2. hr/hr2-011 ru/0

ловушка: a comparison between the same column on two aliases of one table
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT e.full_name FROM emp e JOIN emp m ON m.id = e.mgr_id WHERE e.dept_id <> m.dept_id ORDER BY e.full_name
    ('Alina Almeida',)
    ('Alina Bauer',)
    ('Alina Hale',)
    ('Alina Kovach',)
    ('Alina Linde',)
    ('Alina Marek',)
    ('Alina Oduya',)
    ('Alina Petran',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT e1.full_name AS employee_name, e2.full_name AS manager_name, d1.title AS employee_department, d2.title AS manager_department
FROM emp e1
JOIN emp e2 ON e1.mgr_id = e2.id
JOIN dept d1 ON e1.dept_id = d1.id
JOIN dept d2 ON e2.dept_id = d2.id
WHERE d1.id != d2.id
    ('Sofia Linde', 'Alina Petran', 'Operations', 'Finance')
    ('Sofia Kovach', 'Alina Hale', 'Platform', 'Support')
    ('Sofia Soto', 'Mark Kristof', 'Data', 'Finance')
    ('Pavel Varga', 'Alina Petran', 'Engineering', 'Finance')
    ('Victor Oduya', 'Mark Kristof', 'Data', 'Finance')
    ('Boris Linde', 'Mark Petran', 'Finance', 'Operations')
    ('Mark Novak', 'Alina Petran', 'Data', 'Finance')
    ('Olga Novak', 'Victor Oduya', 'Platform', 'Support')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: те же 177 сотрудников, проверил запросом; добавлены руководитель и два отдела, которых вопрос не просил

## 3. hr/hr2-012 ru/1

ловушка: there is no tenure column; it has to be computed from hired_at; 'working' is the status, not the absence of a leaving date
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG((julianday('2026-11-02') - julianday(hired_at)) / 365.25), 1) AS years FROM emp WHERE status_cd = 1
    (6.7,)

ответ модели:
    SELECT AVG(julianday('2026-11-02') - julianday(hired_at)) / 365.25 AS avg_tenure
FROM emp
WHERE status_cd = 1
    (6.747469100630351,)

ошибка исполнения: нет

вердикт: evaluator
заметка: тот же стаж 6.747, отличие только в отсутствии округления до одного знака

## 4. hr/hr2-037 ru/0

ловушка: the comparison is against the parent's own count, which is a correlated subquery inside HAVING; a department with no parent is not a sub-department and must be excluded; working is status_cd = 1, and the leaving date does not decide it
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title AS department, COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 AND d.parent_id IS NOT NULL GROUP BY d.id, d.title HAVING COUNT(*) > (SELECT COUNT(*) FROM emp e2 WHERE e2.dept_id = d.parent_id AND e2.status_cd = 1) ORDER BY n DESC, d.title
    ('Data', 32)
    ('Platform', 32)

ответ модели:
    SELECT d.title AS department_title
FROM dept d
JOIN emp e ON d.id = e.dept_id
GROUP BY d.id
HAVING COUNT(e.id) > (
    SELECT COUNT(e2.id)
    FROM emp e2
    WHERE e2.dept_id = d.parent_id
)
    ('Operations',)
    ('Engineering',)
    ('Data',)
    ('Finance',)

ошибка исполнения: нет

вердикт: model
заметка: нет отбора по работающим и по наличию родителя, набор другой

## 5. hr/hr2-039 ru/0

ловушка: anti-join; an inner join silently returns the opposite set; unpaid leave is status_cd = 2, a code and not a word
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title FROM dept d WHERE NOT EXISTS (SELECT 1 FROM emp e WHERE e.dept_id = d.id AND e.status_cd = 2) ORDER BY d.title
    ('Engineering',)

ответ модели:
    SELECT d.title
FROM dept d
LEFT JOIN emp e ON d.id = e.dept_id
LEFT JOIN emp_status_ref esr ON e.status_cd = esr.cd
WHERE esr.title != 'unpaid leave'
GROUP BY d.id
HAVING COUNT(e.id) = COUNT(CASE WHEN esr.title = 'unpaid leave' THEN e.id END)
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: условие в WHERE отсекает нужные строки до группировки, выдача пустая

## 6. logistics/log2-034 ru/1

ловушка: the status says delivered while the date says the delivery has not happened yet; today is a literal in the question, there is no current date in the data
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE delivered_at > '2026-11-02'
    (19,)

ответ модели:
    SELECT COUNT(*) 
FROM shp 
WHERE COALESCE(dt_disp, dispatched_at) > '2026-11-02'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает дату отправки вместо даты сдачи, ответ 0

## 7. manufacturing/mfg2-002 ru/1

ловушка: pieces are not a weight, and their conversion factor is 1.0, so including them changes the answer without producing any error; tonnes convert by 1000, which is in the lookup
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(m.qty * u.to_base), 2) AS kg FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE u.title IN ('kilogram', 'tonne')
    (677143.0,)

ответ модели:
    SELECT SUM(CASE WHEN unit_cd = 1 THEN qty * to_base ELSE qty END) AS total_kg
FROM mov
JOIN unit_ref ON mov.unit_cd = unit_ref.cd
WHERE unit_cd != 1
    (67153.6,)

ошибка исполнения: нет

вердикт: model
заметка: исключил не штуки, а первую единицу по коду, сумма в десять раз меньше

## 8. manufacturing/mfg2-004 ru/1

ловушка: the direction is in kind_cd, not in the sign of qty; scrap is a third kind and belongs on neither side of the subtraction
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title, ROUND(SUM(CASE WHEN m.kind_cd = 2 THEN m.qty * u.to_base WHEN m.kind_cd = 1 THEN -m.qty * u.to_base ELSE 0 END), 2) AS net FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id GROUP BY p.title ORDER BY net DESC, p.title
    ('bracket', 35124.0)
    ('bushing', 16750.0)
    ('plate', 8170.0)
    ('spring', -7557.0)
    ('shaft', -16565.0)
    ('gearwheel', -23201.0)

ответ модели:
    SELECT 
    p.title AS part_title,
    SUM(CASE WHEN m.kind_cd = 2 THEN m.qty * ur.to_base ELSE 0 END) - 
    SUM(CASE WHEN m.kind_cd = 1 THEN m.qty * ur.to_base ELSE 0 END) AS net_quantity
FROM 
    part p
JOIN 
    mov m ON p.id = m.part_id
JOIN 
    unit_ref ur ON m.unit_cd = ur.cd
LEFT JOIN 
    defect d ON m.id = d.mov_id
WHERE 
    d.id IS NULL
GROUP BY 
    p.title
    ('bracket', 41476.0)
    ('bushing', 9687.0)
    ('gearwheel', -8621.0)
    ('plate', 15959.0)
    ('shaft', -5155.0)
    ('spring', -7608.0)

ошибка исполнения: нет

вердикт: model
заметка: исключает движения с дефектом вместо вида брака, числа другие

## 9. manufacturing/mfg2-014 ru/1

ловушка: a difference between two text dates needs julianday; the movement date comes from the legacy pair
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM defect d JOIN mov m ON m.id = d.mov_id WHERE julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at)) > 90
    (155,)

ответ модели:
    SELECT COUNT(*) AS defect_count
FROM defect d
JOIN mov m ON d.mov_id = m.id
WHERE d.found_at > m.dt_op + 90
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: складывает 90 с текстовой датой без julianday, ответ 0

## 10. manufacturing/mfg2-022 ru/1

ловушка: the window covering a date is a comparison on both ends, and the open end is a NULL rather than a far-off date; the price is in minor units
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, pp.minor / 100.0 AS price FROM part p JOIN part_price pp ON pp.part_id = p.id WHERE pp.valid_from <= '2026-03-01' AND (pp.valid_to IS NULL OR pp.valid_to > '2026-03-01') ORDER BY p.code
    ('BR-100', 21.2)
    ('BU-550', 49.22)
    ('GR-440', 48.65)
    ('PL-330', 133.63)
    ('SH-210', 16.59)
    ('SP-660', 23.57)

ответ модели:
    SELECT 
    p.title AS part_title,
    pp.minor * ur.to_base AS price_in_base_units
FROM 
    part p
JOIN 
    part_price pp ON p.id = pp.part_id
JOIN 
    unit_ref ur ON p.id = ur.cd
WHERE 
    pp.valid_from <= '2026-03-01' 
    AND (pp.valid_to IS NULL OR pp.valid_to > '2026-03-01')
    AND ur.title = 'piece'
    ('bracket', 2120.0)

ошибка исполнения: нет

вердикт: model
заметка: соединяет деталь с кодом единицы, осталась одна строка

## 11. manufacturing/mfg2-024 ru/1

ловушка: the range join; a join on part_id alone inflates the total about fourfold and the single number gives no hint of it; the conversion and the minor units both apply to every row
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(m.qty * u.to_base * pp.minor / 100.0), 2) AS total FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part_price pp ON pp.part_id = m.part_id AND COALESCE(m.dt_op, m.recorded_at) >= pp.valid_from AND (pp.valid_to IS NULL OR COALESCE(m.dt_op, m.recorded_at) < pp.valid_to)
    (28968594.26,)

ответ модели:
    SELECT SUM(mov.qty * part_price.minor * unit_ref.to_base) AS total_value
FROM mov
JOIN part_price ON mov.part_id = part_price.part_id
JOIN unit_ref ON mov.unit_cd = unit_ref.cd
WHERE part_price.valid_from <= COALESCE(mov.dt_op, mov.recorded_at)
  AND (part_price.valid_to IS NULL OR part_price.valid_to > COALESCE(mov.dt_op, mov.recorded_at))
    (2896859426.0,)

ошибка исполнения: нет

вердикт: model
заметка: копейки не переведены, сумма в сто раз больше

## 12. manufacturing/mfg2-041 ru/0

ловушка: mov joined twice to itself, with the pair taken once by comparing ids; the movement date is split across the legacy pair, so the equality is between two coalesced expressions
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM mov a JOIN mov b ON b.part_id = a.part_id AND b.id > a.id AND COALESCE(a.dt_op, a.recorded_at) = COALESCE(b.dt_op, b.recorded_at) WHERE a.line_id <> b.line_id
    (64,)

ответ модели:
    SELECT COUNT(DISTINCT m1.part_id) AS count
FROM mov m1
JOIN mov m2 ON m1.part_id = m2.part_id AND m1.dt_op = m2.dt_op AND m1.line_id != m2.line_id
WHERE m1.dt_op = m2.dt_op AND m1.line_id != m2.line_id
    (5,)

ошибка исполнения: нет

вердикт: model
заметка: считает разные детали, а не пары движений, 5 против 64

## 13. medicine/med2-007 ru/0

ловушка: the admission date has to be assembled from the legacy pair; 'longer than two weeks' is a strict comparison against 14 days
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM enc WHERE status_cd = 2 AND julianday(discharged) - julianday(COALESCE(dt_adm, admitted_at)) > 14
    (210,)

ответ модели:
    SELECT COUNT(*) 
FROM enc 
WHERE status_cd = 2 
AND (discharged - COALESCE(dt_adm, admitted_at)) > 14
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: вычитает текстовые даты без julianday, ответ 0

## 14. medicine/med2-026 ru/1

ловушка: cancelled is status_cd = 3, a code and not a word; two conditions of opposite sign on the same table, and dropping either one changes the set; a patient with no encounter at all must not be counted among them
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.full_name FROM pat p WHERE EXISTS (SELECT 1 FROM enc e WHERE e.pat_id = p.id) AND NOT EXISTS (SELECT 1 FROM enc e WHERE e.pat_id = p.id AND e.status_cd <> 3) ORDER BY p.full_name
    ('Anna Reiner',)
    ('Anna Soto',)
    ('Boris Linde',)
    ('Elena Marek',)
    ('Elena Reiner',)
    ('Igor Kovach',)
    ('Pavel Marek',)
    ('Victor Novak',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT p.full_name
FROM pat p
JOIN enc e ON p.id = e.pat_id
WHERE e.status_cd = 3
GROUP BY p.id
HAVING COUNT(e.id) = COUNT(CASE WHEN e.status_cd != 3 THEN 1 END)
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: HAVING после отбора по отменённым всегда ложно, выдача пустая

## 15. medicine/med2-031 ru/1

ловушка: an inner join drops the encounters with no prescription and raises the average; COUNT(*) counts the row the outer join produced, so the count has to be over the prescription's own column
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(k), 2) AS mean_rx FROM (SELECT e.id, COUNT(x.id) AS k FROM enc e LEFT JOIN rx x ON x.enc_id = e.id GROUP BY e.id)
    (1.67,)

ответ модели:
    SELECT AVG(CASE WHEN COUNT(rx.id) > 0 THEN COUNT(rx.id) ELSE 0 END) AS avg_rx_count
FROM enc
LEFT JOIN rx ON enc.id = rx.enc_id
WHERE enc.status_cd = 2
GROUP BY enc.id
    ОШИБКА: OperationalError: misuse of aggregate function COUNT()

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: COUNT внутри AVG, misuse of aggregate

## 16. public_services/gov2-006 ru/0

ловушка: the region belongs to the office, two joins from the case; unfinished is a NULL in the closing date, not a status value
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS region, COUNT(*) AS n FROM case_rec c JOIN office o ON o.id = c.office_id JOIN region_ref r ON r.cd = o.region_cd WHERE c.closed_at IS NULL GROUP BY r.title ORDER BY n DESC, r.title
    ('Northport', 40)
    ('Eastvale', 14)
    ('Thorne', 13)
    ('Marden', 10)

ответ модели:
    SELECT 
    r.title AS region,
    COUNT(c.id) AS open_cases
FROM 
    region_ref r
JOIN 
    office o ON r.cd = o.region_cd
JOIN 
    case_rec c ON o.id = c.office_id
LEFT JOIN 
    stage s ON c.id = s.case_id
WHERE 
    s.result_cd IS NULL
GROUP BY 
    r.title
    ('Eastvale', 105)
    ('Marden', 77)
    ('Northport', 154)
    ('Thorne', 82)

ошибка исполнения: нет

вердикт: model
заметка: считает этапы без решения вместо дел без даты закрытия

## 17. public_services/gov2-009 ru/1

ловушка: the group is a pair of columns, and grouping by the person alone counts people who asked for several different services
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT a.full_name, sv.title AS service, COUNT(*) AS times FROM case_rec c JOIN applicant a ON a.id = c.applicant_id JOIN service sv ON sv.id = c.service_id GROUP BY a.id, a.full_name, sv.id, sv.title HAVING COUNT(*) > 1 ORDER BY times DESC, a.full_name, sv.title
    ('Boris Kovach', 'land record extract', 4)
    ('Daniel Petran', 'land record extract', 4)
    ('Elena Novak', 'trading licence', 4)
    ('Pavel Novak', 'land record extract', 4)
    ('Anna Almeida', 'business registration', 3)
    ('Artem Bauer', 'business registration', 3)
    ('Artem Bauer', 'residence certificate', 3)
    ('Artem Kovach', 'land record extract', 3)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT 
    a.full_name AS applicant_name, 
    s.title AS service_title
FROM 
    applicant a
JOIN 
    case_rec cr ON a.id = cr.applicant_id
JOIN 
    service s ON cr.service_id = s.id
GROUP BY 
    a.full_name, s.title
HAVING 
    COUNT(cr.id) > 1
    ('Alina Almeida', 'business registration')
    ('Alina Almeida', 'land record extract')
    ('Alina Almeida', 'trading licence')
    ('Alina Oduya', 'trading licence')
    ('Alina Petran', 'business registration')
    ('Alina Reiner', 'business registration')
    ('Alina Reiner', 'residence certificate')
    ('Alina Reiner', 'trading licence')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: группирует по имени, а не по заявителю; тёзки слиты, 196 пар против 162, проверил запросом

## 18. public_services/gov2-028 ru/1

ловушка: the deadline is inclusive, so landing on it is neither late nor early and both strict comparisons miss this group; the share counts the qualifying rows against all rows of the group, so the condition goes inside the aggregate
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title, ROUND(100.0 * SUM(CASE WHEN c.closed_at = c.due_dt THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL GROUP BY sv.title ORDER BY pct DESC, sv.title
    ('building permit', 12.21)
    ('trading licence', 12.16)
    ('business registration', 10.0)
    ('land record extract', 8.02)
    ('residence certificate', 4.46)

ответ модели:
    SELECT 
    s.title AS service_title,
    ROUND(COUNT(CASE WHEN c.closed_at = c.due_dt THEN 1 END) * 100.0 / COUNT(*), 2) AS percentage
FROM 
    service s
JOIN 
    case_rec c ON s.id = c.service_id
GROUP BY 
    s.title
    ('building permit', 10.74)
    ('business registration', 9.03)
    ('land record extract', 7.1)
    ('residence certificate', 3.85)
    ('trading licence', 11.69)

ошибка исполнения: нет

вердикт: model
заметка: в знаменателе все дела, а не только закрытые

## 19. public_services/gov2-030 ru/0

ловушка: how many regions exist is a fact of region_ref, not a number to hard-code; the region is one step beyond the office, which is itself one step beyond the case
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT c.applicant_id FROM case_rec c JOIN office o ON o.id = c.office_id GROUP BY c.applicant_id HAVING COUNT(DISTINCT o.region_cd) = (SELECT COUNT(*) FROM region_ref))
    (21,)

ответ модели:
    SELECT r.title AS region, COUNT(DISTINCT a.id) AS applicant_count
FROM region_ref r
JOIN office o ON r.cd = o.region_cd
JOIN case_rec c ON o.id = c.office_id
JOIN applicant a ON c.applicant_id = a.id
GROUP BY r.title
    ('Eastvale', 114)
    ('Marden', 116)
    ('Northport', 176)
    ('Thorne', 108)

ошибка исполнения: нет

вердикт: model
заметка: вернул разрез по регионам вместо числа подавших во всех

## 20. public_services/gov2-037 ru/1

ловушка: an inner join drops the cases with no stage and raises the average; COUNT(*) counts the row the outer join produced, so the count has to be over the stage's own column
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(k), 2) AS mean_stages FROM (SELECT c.id, COUNT(s.id) AS k FROM case_rec c LEFT JOIN stage s ON s.case_id = c.id GROUP BY c.id)
    (1.97,)

ответ модели:
    SELECT AVG(CASE WHEN COUNT(stage.id) > 0 THEN COUNT(stage.id) ELSE 0 END) AS avg_stages
FROM case_rec
LEFT JOIN stage ON case_rec.id = stage.case_id
GROUP BY case_rec.id
    ОШИБКА: OperationalError: misuse of aggregate function COUNT()

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: COUNT внутри AVG, misuse of aggregate
