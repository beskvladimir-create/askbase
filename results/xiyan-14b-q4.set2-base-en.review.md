# Ручной разбор провалов: xiyan-14b-q4.set2-base-en.jsonl

Провалов всего: 465 из 576.
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
    SELECT resid_cd , count(*) FROM cust GROUP BY resid_cd
    (1, 284)
    (2, 66)

ошибка исполнения: нет

вердикт: model
заметка: вернул коды резидентства вместо названий, по ответу не понять, где резиденты

## 2. hr/hr2-022 en/1

ловушка: the currency is a code and its name is in the lookup; an earlier row in another currency does not make the person an answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT e.full_name FROM emp e JOIN pay_hist p ON p.emp_id = e.id JOIN cur_ref c ON c.cd = p.cur_cd WHERE c.title = 'USD' AND p.from_dt = ( SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id ) ORDER BY e.full_name
    ('Alina Almeida',)
    ('Alina Kovach',)
    ('Alina Oduya',)
    ('Alina Petran',)
    ('Anna Reiner',)
    ('Anna Varga',)
    ('Artem Marek',)
    ('Artem Marek',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT T1.full_name FROM emp AS T1 JOIN pay_hist AS T2 ON T1.id = T2.emp_id JOIN cur_ref AS T3 ON T2.cur_cd = T3.cd WHERE T3.title = 'USD' GROUP BY T1.full_name
    ('Alina Almeida',)
    ('Alina Kovach',)
    ('Alina Marek',)
    ('Alina Oduya',)
    ('Alina Petran',)
    ('Anna Bauer',)
    ('Anna Benali',)
    ('Anna Hale',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: нет отбора по действующей строке зарплаты, попали все, кому когда-либо платили в долларах

## 3. hr/hr2-039 en/1

ловушка: anti-join; an inner join silently returns the opposite set; unpaid leave is status_cd = 2, a code and not a word
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title FROM dept d WHERE NOT EXISTS (SELECT 1 FROM emp e WHERE e.dept_id = d.id AND e.status_cd = 2) ORDER BY d.title
    ('Engineering',)

ответ модели:
    SELECT title FROM dept EXCEPT SELECT T2.title FROM emp AS T1 JOIN dept AS T2 ON T1.dept_id = T2.id WHERE T1.status_cd = 'U'
    ('Data',)
    ('Engineering',)
    ('Finance',)
    ('Operations',)
    ('Platform',)
    ('Support',)

ошибка исполнения: нет

вердикт: model
заметка: статус сравнивается с буквой U, вычитание ничего не убрало, вернулись все отделы

## 4. logistics/log2-004 en/0

ловушка: the status and the delivery date disagree by design, and the question is about exactly that disagreement
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 3 AND delivered_at IS NOT NULL
    (15,)

ответ модели:
    SELECT count(*) FROM shp AS T1 JOIN status_ref AS T2 ON T1.status_cd = T2.cd WHERE T2.title = "Lost" AND T1.delivered_at IS NOT NULL
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: статус ищется по названию Lost, ответ 0

## 5. logistics/log2-025 en/1

ловушка: the dispatch date is split across the legacy pair dt_disp/dispatched_at; the comparison is between two columns of two tables, not against a literal
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM inc i JOIN shp s ON s.id = i.shp_id WHERE i.at < COALESCE(s.dt_disp, s.dispatched_at)
    (136,)

ответ модели:
    SELECT count(*) FROM inc AS T1 JOIN shp AS T2 ON T1.ship_id = T2.id WHERE T1.at < T2.dispatched_at
    ОШИБКА: OperationalError: no such column: T1.ship_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к inc.ship_id, колонка называется иначе

## 6. logistics/log2-032 en/1

ловушка: the mode belongs to the carrier, not to the leg, so the join goes through carr; costs are minor units and must be divided by 100
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT m.title AS mode, SUM(l.cost_cents) / 100.0 AS cost FROM leg l JOIN carr c ON c.id = l.carr_id JOIN mode_ref m ON m.cd = c.mode_cd GROUP BY m.title ORDER BY cost DESC, m.title
    ('road', 4171492.1)
    ('rail', 2335255.97)
    ('sea', 1566985.53)
    ('air', 659359.57)

ответ модели:
    SELECT T1.title , sum(T2.cost_cents) / 100 FROM mode_ref AS T1 JOIN leg AS T2 ON T1.cd = T2.carr_id GROUP BY T1.title
    ('air', 186271)
    ('rail', 292219)
    ('road', 165263)
    ('sea', 230986)

ошибка исполнения: нет

вердикт: model
заметка: соединяет справочник видов транспорта по коду с идентификатором перевозчика

## 7. logistics/log2-038 en/1

ловушка: how many countries exist is a fact of loc_ref, not a number to hard-code; the country is one step beyond the destination code; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT c.id FROM cust c JOIN shp s ON s.cust_id = c.id JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY c.id HAVING COUNT(DISTINCT d.country) = (SELECT COUNT(DISTINCT country) FROM loc_ref))
    (37,)

ответ модели:
    SELECT COUNT(*) FROM cust AS T1 JOIN shp AS T2 ON T1.id = T2.cust_id JOIN loc_ref AS T3 ON T3.cd = T2.dst_cd WHERE T3.country = 'USA' INTERSECT SELECT COUNT(*) FROM cust AS T1 JOIN shp AS T2 ON T1.id = T2.cust_id JOIN loc_ref AS T3 ON T3.cd = T2.dst_cd WHERE T3.country = 'Canada'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: выдумал страны USA и Canada, которых в данных нет

## 8. logistics/log2-045 en/0

ловушка: the country of arrival is two steps from the leg: shipment, then the destination code; the destination end, not the origin; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT l.carr_id FROM leg l JOIN shp s ON s.id = l.shp_id JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY l.carr_id HAVING COUNT(DISTINCT d.country) > 1)
    (45,)

ответ модели:
    SELECT COUNT(*) FROM carr AS T1 JOIN loc_ref AS T2 ON T1.id = T2.cd GROUP BY T1.id HAVING COUNT(*) > 1
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: соединяет перевозчика со справочником мест по идентификатору

## 9. manufacturing/mfg2-012 en/0

ловушка: critical is grade_cd = 3, a code; the part is reached through the movement, not from the defect
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, p.title, COUNT(*) AS n FROM defect d JOIN mov m ON m.id = d.mov_id JOIN part p ON p.id = m.part_id WHERE d.grade_cd = 3 GROUP BY p.id, p.code, p.title ORDER BY n DESC, p.code
    ('BR-100', 'bracket', 16)
    ('PL-330', 'plate', 10)
    ('SH-210', 'shaft', 10)
    ('GR-440', 'gearwheel', 2)
    ('BU-550', 'bushing', 1)

ответ модели:
    SELECT T1.code , T1.title , count(*) FROM part AS T1 JOIN defect AS T2 ON T1.id = T2.mov_id WHERE T2.grade_cd = "CRITICAL" GROUP BY T1.code , T1.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: степень сравнивается со словом CRITICAL и дефект соединён с деталью напрямую

## 10. manufacturing/mfg2-014 en/0

ловушка: a difference between two text dates needs julianday; the movement date comes from the legacy pair
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM defect d JOIN mov m ON m.id = d.mov_id WHERE julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at)) > 90
    (155,)

ответ модели:
    SELECT COUNT(*) FROM defect AS T1 JOIN mov AS T2 ON T1.mov_id = T2.id WHERE JULIANDAY(T1.found_at) - JULIANDAY(T2.dt_op) > 90
    (150,)

ошибка исполнения: нет

вердикт: model
заметка: без COALESCE на дату движения, 150 против 155

## 11. manufacturing/mfg2-019 en/0

ловушка: the shift is on the line, not on the movement; the piece rows are not a weight and must be left out
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT s.title AS shift, ROUND(SUM(m.qty * u.to_base), 2) AS kg FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN line l ON l.id = m.line_id JOIN shift_ref s ON s.cd = l.shift_cd WHERE u.title IN ('kilogram', 'tonne') GROUP BY s.title ORDER BY kg DESC, s.title
    ('day', 342510.0)
    ('night', 334633.0)

ответ модели:
    SELECT T2.title , sum(T3.qty) FROM part AS T1 JOIN line AS T2 ON T1.id = T3.part_id JOIN mov AS T3 ON T1.id = T3.part_id GROUP BY T2.title
    ('Assembly A', 158880.6)
    ('Assembly B', 158880.6)
    ('Finishing', 158880.6)
    ('Machining', 158880.6)

ошибка исполнения: нет

вердикт: model
заметка: соединение через несуществующую связь, во всех строках одна и та же сумма

## 12. manufacturing/mfg2-021 en/1

ловушка: HAVING on a count, which cannot be written as a WHERE
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.code, COUNT(*) AS defects FROM defect d JOIN mov m ON m.id = d.mov_id JOIN part p ON p.id = m.part_id GROUP BY p.id, p.code HAVING COUNT(*) > 30 ORDER BY defects DESC, p.code
    ('BR-100', 117)
    ('SH-210', 82)
    ('PL-330', 59)
    ('GR-440', 35)

ответ модели:
    SELECT T1.code , count(*) FROM part AS T1 JOIN defect AS T2 ON T1.id = T2.mov_id GROUP BY T1.code HAVING count(*) > 30
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: дефект соединён с деталью по mov_id, выдача пустая

## 13. manufacturing/mfg2-041 en/1

ловушка: mov joined twice to itself, with the pair taken once by comparing ids; the movement date is split across the legacy pair, so the equality is between two coalesced expressions
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM mov a JOIN mov b ON b.part_id = a.part_id AND b.id > a.id AND COALESCE(a.dt_op, a.recorded_at) = COALESCE(b.dt_op, b.recorded_at) WHERE a.line_id <> b.line_id
    (64,)

ответ модели:
    SELECT COUNT(*) FROM mov AS T1 JOIN mov AS T2 ON T1.dt_op = T2.dt_op AND T1.line_id != T2.line_id
    (372,)

ошибка исполнения: нет

вердикт: model
заметка: пара считается дважды и без COALESCE, 372 против 64

## 14. medicine/med2-046 en/1

ловушка: the grouping is over two columns at once, and the answer counts groups rather than rows; HAVING, which RedSQL found models get wrong most often
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT pat_id, doc_id FROM enc GROUP BY pat_id, doc_id HAVING COUNT(*) > 1)
    (25,)

ответ модели:
    SELECT COUNT(*) FROM ( SELECT T1.id AS patient_id, T2.id AS doctor_id FROM pat AS T1 JOIN enc AS T2 ON T1.id = T2.pat_id JOIN enc AS T3 ON T1.id = T3.pat_id WHERE T2.id = T3.id GROUP BY T1.id, T2.id HAVING COUNT(*) >= 2 ) AS T4
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: соединяет случай сам с собой по равенству идентификаторов, ответ 0

## 15. public_services/gov2-008 en/0

ловушка: the threshold is a column of another table, not a constant; the submission date comes from the legacy pair
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL AND julianday(c.closed_at) - julianday(COALESCE(c.dt_sub, c.submitted_at)) > 2 * sv.sla_days
    (115,)

ответ модели:
    SELECT count(*) FROM case_rec AS T1 JOIN service AS T2 ON T1.service_id = T2.id WHERE T1.closed_at IS NOT NULL AND T1.due_dt - T1.submitted_at > 2 * T2.sla_days
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: вычитает текстовые даты и берёт срок вместо даты закрытия, ответ 0

## 16. public_services/gov2-023 en/1

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
    SELECT T2.title , CAST(SUM(CASE WHEN T1.closed_at IS NULL THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM case_rec AS T1 JOIN service AS T2 ON T1.service_id = T2.id GROUP BY T2.title
    ('building permit', 12.080536912751677)
    ('business registration', 9.722222222222221)
    ('land record extract', 11.475409836065573)
    ('residence certificate', 13.846153846153847)
    ('trading licence', 3.896103896103896)

ошибка исполнения: нет

вердикт: evaluator
заметка: те же пять долей, отличие только в отсутствии округления до одного знака

## 17. public_services/gov2-029 en/0

ловушка: two joins to reach the region: the case carries an office and the office carries the region code; the difference between two text dates needs julianday; a case closed exactly on the deadline is not late and must not enter the average
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS region, ROUND(AVG(julianday(c.closed_at) - julianday(c.due_dt)), 2) AS days FROM case_rec c JOIN office o ON o.id = c.office_id JOIN region_ref r ON r.cd = o.region_cd WHERE c.closed_at > c.due_dt GROUP BY r.title ORDER BY days DESC, r.title
    ('Northport', 21.83)
    ('Thorne', 21.11)
    ('Eastvale', 20.29)
    ('Marden', 20.14)

ответ модели:
    SELECT T2.region_cd , avg(closed_at - due_dt) FROM case_rec AS T1 JOIN office AS T2 ON T1.office_id = T2.id WHERE closed_at > due_dt GROUP BY T2.region_cd
    (1, 0.031746031746031744)
    (2, 0.05714285714285714)
    (3, 0.045454545454545456)
    (4, 0.08571428571428572)

ошибка исполнения: нет

вердикт: model
заметка: вычитает текстовые даты без julianday и выводит код региона вместо названия

## 18. public_services/gov2-042 en/1

ловушка: the applicant's city holds a region name, so the comparison is between a column of one table and a column of another; an applicant with no city recorded matches nothing, because NULL is not equal to anything, and still belongs in the denominator; three joins to reach the region from the case
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS region, ROUND(100.0 * SUM(CASE WHEN a.city = r.title THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct FROM case_rec c JOIN applicant a ON a.id = c.applicant_id JOIN office o ON o.id = c.office_id JOIN region_ref r ON r.cd = o.region_cd GROUP BY r.title ORDER BY pct DESC, r.title
    ('Thorne', 26.24)
    ('Eastvale', 21.95)
    ('Marden', 20.27)
    ('Northport', 17.59)

ответ модели:
    SELECT T1.title , CAST(SUM(CASE WHEN T3.city = T1.title THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM region_ref AS T1 JOIN office AS T2 ON T1.cd = T2.region_cd JOIN applicant AS T3 ON T3.id = T2.id GROUP BY T1.title
    ('Eastvale', 0.0)
    ('Marden', 0.0)
    ('Northport', 0.0)
    ('Thorne', 0.0)

ошибка исполнения: нет

вердикт: model
заметка: соединяет заявителя с отделением по идентификатору, все доли нулевые

## 19. public_services/gov2-044 en/0

ловушка: an anti-join on the same table, asking that no later stage exists; a decided stage is one whose result_cd is not NULL, which no equality test finds
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM stage s WHERE s.seq = 1 AND s.result_cd IS NOT NULL AND NOT EXISTS (SELECT 1 FROM stage s2 WHERE s2.case_id = s.case_id AND s2.seq > 1)
    (169,)

ответ модели:
    SELECT count(*) FROM stage AS T1 JOIN case_rec AS T2 ON T1.case_id = T2.id WHERE T1.seq = 1 AND NOT EXISTS ( SELECT 1 FROM stage AS T3 WHERE T3.case_id = T2.id AND T3.seq > 1 )
    (208,)

ошибка исполнения: нет

вердикт: model
заметка: нет условия на решённость первого этапа, 208 против 169

## 20. public_services/gov2-048 en/1

ловушка: two conditions of opposite sign on the same table, and dropping either one changes the set; a registered person with no case at all must not be counted among them
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM applicant a WHERE EXISTS (SELECT 1 FROM case_rec c WHERE c.applicant_id = a.id) AND NOT EXISTS (SELECT 1 FROM case_rec c WHERE c.applicant_id = a.id AND c.closed_at IS NOT NULL)
    (4,)

ответ модели:
    SELECT COUNT(DISTINCT applicant_id) FROM case_rec WHERE closed_at IS NULL
    (62,)

ошибка исполнения: нет

вердикт: model
заметка: считает заявителей с незакрытым делом, а не тех, у кого незакрыты все
