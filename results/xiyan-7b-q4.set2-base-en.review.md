# Ручной разбор провалов: xiyan-7b-q4.set2-base-en.jsonl

Провалов всего: 447 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-015 en/0

ловушка: the merchant category is a code, its name lives in mcc_ref; spending is dir_cd = 1, a code and not a sign; amounts are minor units and must be divided by 100
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT SUM(t.amt_cents) / 100.0 AS spent FROM txn t JOIN mcc_ref m ON m.code = t.mcc WHERE m.title = 'grocery stores' AND t.dir_cd = 1
    (49332.21,)

ответ модели:
    SELECT SUM(T1.amt_cents) / 100 FROM txn AS T1 INNER JOIN dir_ref AS T2 ON T1.dir_cd = T2.cd WHERE T2.title = 'Grocery'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: ищет категорию в справочнике направлений, результат None

## 2. hr/hr2-001 en/0

ловушка: salary is effective-dated; only the latest row per person counts; amounts are in minor units and must be divided by 100.0; two currencies, which cannot be added into one total
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT c.title AS currency, SUM(p.amount_minor) / 100.0 AS total FROM pay_hist p JOIN cur_ref c ON c.cd = p.cur_cd WHERE p.from_dt = ( SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = p.emp_id ) GROUP BY c.title ORDER BY c.title
    ('EUR', 1131411.0)
    ('USD', 255128.0)

ответ модели:
    SELECT sum(amount_minor) , T1.cd FROM cur_ref AS T1 JOIN pay_hist AS T2 ON T1.cd = T2.cur_cd WHERE T2.left_at IS NULL GROUP BY T1.cd
    ОШИБКА: OperationalError: no such column: T2.left_at

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к pay_hist.left_at, которой нет

## 3. hr/hr2-027 en/0

ловушка: HAVING over a distinct count, not over a plain count of rows; the answer is the number of people, so the grouped rows have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT emp_id FROM pay_hist GROUP BY emp_id HAVING COUNT(DISTINCT cur_cd) > 1)
    (105,)

ответ модели:
    SELECT COUNT(DISTINCT emp_id) FROM pay_hist WHERE cur_cd IN ( SELECT cd FROM cur_ref WHERE title IN ('US Dollars', 'Canadian Dollars') )
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: ищет валюты US Dollars и Canadian Dollars, которых нет, ответ 0

## 4. hr/hr2-041 en/1

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
    SELECT T1.dept_id , T2.full_name , T2.hired_at FROM dept AS T1 JOIN emp AS T2 ON T1.id = T2.dept_id WHERE T2.status_cd = 'A' ORDER BY T2.hired_at LIMIT 1
    ОШИБКА: OperationalError: no such column: T1.dept_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к dept.dept_id и берёт одну строку на всю таблицу

## 5. hr/hr2-047 en/1

ловушка: the salary in force is the latest from_dt per person, so the history would widen every spread; the ordering key is a difference of two aggregates, and it is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title FROM emp e JOIN dept d ON d.id = e.dept_id JOIN pay_hist p ON p.emp_id = e.id WHERE e.status_cd = 1 AND p.cur_cd = 1 AND p.from_dt = (SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id) GROUP BY d.title ORDER BY MAX(p.amount_minor) - MIN(p.amount_minor) DESC, d.title LIMIT 1
    ('Operations',)

ответ модели:
    SELECT T1.title FROM dept AS T1 JOIN emp AS T2 ON T1.id = T2.dept_id WHERE T2.id IN ( SELECT emp_id FROM pay_hist AS T3 JOIN cur_ref AS T4 ON T3.cur_cd = T4.cd WHERE T4.title = 'Euro' GROUP BY T3.emp_id ORDER BY MAX(T3.amount_minor) - MIN(T3.amount_minor) DESC LIMIT 1 )
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: валюта ищется как Euro, выдача пустая

## 6. logistics/log2-006 en/1

ловушка: distance per shipment means summing its legs first and averaging after, not averaging the legs
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(total), 1) AS mean_km FROM (SELECT SUM(dist_km) AS total FROM leg GROUP BY shp_id)
    (3668.7,)

ответ модели:
    SELECT round(avg(dist_km), 1) FROM leg
    (1328.9,)

ошибка исполнения: нет

вердикт: model
заметка: усредняет плечи вместо суммы по перевозке, 1328.9 против 3668.7

## 7. logistics/log2-030 en/0

ловушка: leg joined twice to itself, once as the first and once as the last; the last leg is the largest seq of that shipment, which is a correlated subquery; a single-leg shipment satisfies the equality trivially and the question excludes it
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM leg l1 JOIN leg l2 ON l2.shp_id = l1.shp_id WHERE l1.seq = 1 AND l2.seq = (SELECT MAX(seq) FROM leg WHERE shp_id = l1.shp_id) AND l2.seq > 1 AND l1.carr_id = l2.carr_id
    (6,)

ответ модели:
    SELECT COUNT(*) FROM leg AS T1 INNER JOIN leg AS T2 ON T1.shp_id = T2.shp_id WHERE T1.seq = 1 AND T2.seq = ( SELECT MAX(seq) FROM leg AS T3 WHERE T3.shp_id = T1.shp_id )
    (652,)

ошибка исполнения: нет

вердикт: model
заметка: не исключил перевозки из одного плеча и не сравнил перевозчиков, 652 против 6

## 8. logistics/log2-040 en/0

ловушка: the numerator counts shipments, not incidents, so one shipment with three incidents counts once; an integer division returns zero here, the ratio has to be taken in floating point
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(100.0 * (SELECT COUNT(DISTINCT shp_id) FROM inc) / (SELECT COUNT(*) FROM shp), 2) AS pct
    (21.57,)

ответ модели:
    SELECT CAST(COUNT(DISTINCT inc.shp_id) AS REAL) * 100 / ( SELECT COUNT(DISTINCT shp.id) FROM shp ) AS percentage FROM inc
    (21.571428571428573,)

ошибка исполнения: нет

вердикт: evaluator
заметка: та же доля 21.571, отличие только в отсутствии округления до двух знаков

## 9. logistics/log2-046 en/0

ловушка: the origin end, not the destination, and both are codes into the same lookup; the question asks which, so the weight is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT o.title FROM shp s JOIN loc_ref o ON o.cd = s.org_cd GROUP BY o.title ORDER BY SUM(s.weight_kg) DESC, o.title LIMIT 1
    ('Eastvale',)

ответ модели:
    SELECT T1.city FROM cust AS T1 INNER JOIN shp AS T2 ON T1.id = T2.cust_id GROUP BY T1.city ORDER BY SUM(T2.weight_kg) DESC LIMIT 1
    ('Kesling',)

ошибка исполнения: нет

вердикт: model
заметка: берёт город клиента вместо города отправления

## 10. manufacturing/mfg2-002 en/0

ловушка: pieces are not a weight, and their conversion factor is 1.0, so including them changes the answer without producing any error; tonnes convert by 1000, which is in the lookup
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(SUM(m.qty * u.to_base), 2) AS kg FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE u.title IN ('kilogram', 'tonne')
    (677143.0,)

ответ модели:
    SELECT SUM(T1.qty) FROM mov AS T1 INNER JOIN unit_ref AS T2 ON T1.unit_cd = T2.cd WHERE T2.title = 'kilogram'
    (66543.0,)

ошибка исполнения: нет

вердикт: model
заметка: взял только килограммы и не перевёл тонны

## 11. manufacturing/mfg2-018 en/0

ловушка: the comparison has to happen after the conversion, not on qty; a row in pieces has no weight and cannot qualify
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT m.id, p.title AS part, l.title AS line, m.qty * u.to_base AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id JOIN line l ON l.id = m.line_id WHERE u.title IN ('kilogram', 'tonne') AND m.qty * u.to_base > 1000 ORDER BY base_qty DESC, m.id
    (719, 'gearwheel', 'Finishing', 11870.0)
    (523, 'plate', 'Assembly A', 11850.0)
    (13, 'bracket', 'Finishing', 11670.0)
    (209, 'plate', 'Finishing', 11600.0)
    (245, 'bracket', 'Machining', 11590.0)
    (763, 'bushing', 'Finishing', 11490.0)
    (784, 'bracket', 'Assembly A', 11430.0)
    (671, 'plate', 'Assembly B', 11280.0)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT T1.part_id , T1.line_id FROM mov AS T1 WHERE T1.qty > 1000
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает количество без перевода единиц, выдача пустая

## 12. manufacturing/mfg2-020 en/0

ловушка: DISTINCT part, not a movement count
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT l.title, COUNT(DISTINCT m.part_id) AS parts FROM mov m JOIN line l ON l.id = m.line_id GROUP BY l.title ORDER BY parts DESC, l.title
    ('Assembly A', 6)
    ('Assembly B', 6)
    ('Finishing', 6)
    ('Machining', 6)

ответ модели:
    SELECT T1.id , count(DISTINCT T2.part_id) FROM line AS T1 JOIN mov AS T2 ON T1.id = T2.line_id GROUP BY T1.id
    (1, 6)
    (2, 6)
    (3, 6)
    (4, 6)

ошибка исполнения: нет

вердикт: model
заметка: вернул идентификатор линии вместо названия

## 13. manufacturing/mfg2-026 en/0

ловушка: HAVING over a distinct count, not over a plain count of defects; the grade is a code, and counting its distinct values is the question
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT mov_id FROM defect GROUP BY mov_id HAVING COUNT(DISTINCT grade_cd) > 1)
    (46,)

ответ модели:
    SELECT COUNT(*) FROM ( SELECT T1.grade_cd FROM defect AS T1 INNER JOIN defect AS T2 ON T1.mov_id = T2.mov_id WHERE T1.grade_cd != T2.grade_cd ) AS T3
    (176,)

ошибка исполнения: нет

вердикт: model
заметка: считает пары дефектов, а не движения, 176 против 46

## 14. manufacturing/mfg2-028 en/0

ловушка: the unit is a code, 1 is the piece, and the question is about the recorded unit rather than the converted quantity; the share counts the qualifying rows against all rows of the group, so the condition goes inside the aggregate
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT l.title, ROUND(100.0 * SUM(CASE WHEN m.unit_cd = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct FROM mov m JOIN line l ON l.id = m.line_id GROUP BY l.title ORDER BY pct DESC, l.title
    ('Machining', 54.66)
    ('Assembly B', 53.1)
    ('Assembly A', 53.04)
    ('Finishing', 51.92)

ответ модели:
    SELECT T1.id , CAST(COUNT(CASE WHEN T1.unit_cd = 'pc' THEN 1 ELSE NULL END) AS REAL) * 100 / COUNT(*) FROM mov AS T1
    (1, 0.0)

ошибка исполнения: нет

вердикт: model
заметка: единица сравнивается со строкой pc и нет группировки по линии

## 15. manufacturing/mfg2-048 en/0

ловушка: two joins to reach it: the defect carries neither the unit nor the quantity; the unit is named in the lookup, so the filter cannot be written on the code alone
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM defect d JOIN mov m ON m.id = d.mov_id JOIN unit_ref u ON u.cd = m.unit_cd WHERE u.title = 'piece'
    (166,)

ответ модели:
    SELECT count(*) FROM mov AS T1 INNER JOIN defect AS T2 ON T1.id = T2.mov_id INNER JOIN unit_ref AS T3 ON T1.unit_cd = T3.cd WHERE T3.title = 'pz'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: единица ищется как pz, ответ 0

## 16. public_services/gov2-005 en/1

ловушка: the submission date is split across the legacy pair dt_sub/submitted_at; only the closed cases have both ends of the interval
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title, ROUND(AVG(julianday(c.closed_at) - julianday(COALESCE(c.dt_sub, c.submitted_at))), 1) AS days FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL GROUP BY sv.title ORDER BY days DESC, sv.title
    ('building permit', 25.2)
    ('trading licence', 20.4)
    ('residence certificate', 13.9)
    ('land record extract', 10.9)
    ('business registration', 10.3)

ответ модели:
    SELECT T1.title , avg(T3.due_dt - T3.submitted_at) FROM service AS T1 JOIN case_rec AS T3 ON T1.id = T3.service_id WHERE T3.closed_at IS NOT NULL GROUP BY T1.id
    ('building permit', 0.04597701149425287)
    ('business registration', 0.011111111111111112)
    ('land record extract', 0.0)
    ('residence certificate', 0.041666666666666664)
    ('trading licence', 0.0392156862745098)

ошибка исполнения: нет

вердикт: model
заметка: вычитает текстовые даты и берёт срок вместо даты закрытия

## 17. public_services/gov2-008 en/0

ловушка: the threshold is a column of another table, not a constant; the submission date comes from the legacy pair
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL AND julianday(c.closed_at) - julianday(COALESCE(c.dt_sub, c.submitted_at)) > 2 * sv.sla_days
    (115,)

ответ модели:
    SELECT count(*) FROM case_rec AS T1 JOIN service AS T2 ON T1.service_id = T2.id WHERE T1.closed_at > (julianday(T1.due_dt) - julianday(T1.dt_sub)) * 2
    (94,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает дату закрытия с числом дней, 94 против 115

## 18. public_services/gov2-019 en/0

ловушка: 'refused' is a word in result_ref, and the service is two joins away from the stage
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title, COUNT(*) AS n FROM stage s JOIN case_rec c ON c.id = s.case_id JOIN service sv ON sv.id = c.service_id JOIN result_ref r ON r.cd = s.result_cd WHERE r.title = 'refused' GROUP BY sv.title ORDER BY n DESC, sv.title
    ('building permit', 61)
    ('trading licence', 57)
    ('land record extract', 55)
    ('business registration', 49)
    ('residence certificate', 39)

ответ модели:
    SELECT T3.title , COUNT(*) FROM stage AS T1 JOIN result_ref AS T2 ON T1.result_cd = T2.cd JOIN service AS T3 ON T1.case_id = T3.id WHERE T2.title = 'Refused' GROUP BY T3.id
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: соединяет этап с услугой по идентификатору дела, выдача пустая

## 19. public_services/gov2-036 en/0

ловушка: case_rec checked against itself under another alias, matched on the person and the service at once; the submission date is split across the legacy pair dt_sub/submitted_at, on both sides of the comparison; late means strictly after the due date, because the deadline is inclusive
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec c WHERE EXISTS (SELECT 1 FROM case_rec c2 WHERE c2.applicant_id = c.applicant_id AND c2.service_id = c.service_id AND COALESCE(c2.dt_sub, c2.submitted_at) < COALESCE(c.dt_sub, c.submitted_at) AND c2.closed_at > c2.due_dt)
    (49,)

ответ модели:
    SELECT count(*) FROM case_rec t1 JOIN case_rec t2 ON t1.applicant_id = t2.applicant_id AND t1.service_id = t2.service_id AND t1.dt_sub < t2.dt_sub WHERE t1.due_dt < t1.dt_sub
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: перепутаны стороны сравнения дат и нет условия на просрочку предыдущего дела

## 20. public_services/gov2-040 en/1

ловушка: case_rec joined twice to itself, with the pair taken once by comparing ids; the submission date is split across the legacy pair, so the equality is between two coalesced expressions
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec a JOIN case_rec b ON b.applicant_id = a.applicant_id AND b.id > a.id AND COALESCE(a.dt_sub, a.submitted_at) = COALESCE(b.dt_sub, b.submitted_at) WHERE a.service_id <> b.service_id
    (3,)

ответ модели:
    SELECT COUNT(*) FROM case_rec AS T1 JOIN case_rec AS T2 ON T1.applicant_id = T2.applicant_id AND T1.dt_sub = T2.dt_sub AND T1.id > T2.id WHERE T1.service_id != T2.service_id
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: без COALESCE на дату подачи равенство не срабатывает, ответ 0
