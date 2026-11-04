# Ручной разбор провалов: xiyan-14b-q4.set2-base-ru.jsonl

Провалов всего: 475 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-014 ru/0

ловушка: an account with no closing date cannot qualify and must be excluded; dates are text, so the year is the first four characters
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM acct WHERE closed_at IS NOT NULL AND substr(opened_at, 1, 4) = substr(closed_at, 1, 4)
    (17,)

ответ модели:
    SELECT COUNT(*) FROM acct WHERE status_cd = 'Closed' AND opened_at >= '2022-01-01' AND closed_at <= '2022-12-31'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: статус сравнивается со словом Closed и зашит 2022 год, ответ 0

## 2. hr/hr2-023 ru/0

ловушка: an anti-join of a table against itself under two aliases
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.title FROM dept d WHERE NOT EXISTS (SELECT 1 FROM dept c WHERE c.parent_id = d.id) ORDER BY d.title
    ('Data',)
    ('Finance',)
    ('Platform',)
    ('Support',)

ответ модели:
    SELECT title FROM dept WHERE id NOT IN ( SELECT parent_id FROM dept )
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: NOT IN с NULL в подзапросе возвращает пусто

## 3. hr/hr2-038 ru/0

ловушка: dept joined twice to itself, and COALESCE on the parent is what rolls a sub-department up to its top; the salary in force is the latest from_dt per person, so a plain join multiplies the total by the number of revisions; the currencies must not be added together, so the euro rows are the only ones that count
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT top.title, SUM(p.amount_minor) / 100.0 AS payroll FROM emp e JOIN dept d ON d.id = e.dept_id JOIN dept top ON top.id = COALESCE(d.parent_id, d.id) JOIN pay_hist p ON p.emp_id = e.id WHERE e.status_cd = 1 AND p.cur_cd = 1 AND p.from_dt = (SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id) GROUP BY top.title ORDER BY payroll DESC, top.title
    ('Engineering', 357940.0)
    ('Operations', 254790.0)
    ('Finance', 181600.0)

ответ модели:
    SELECT T1.title , sum(T3.amount_minor) FROM dept AS T1 JOIN emp AS T2 ON T1.id = T2.dept_id JOIN pay_hist AS T3 ON T2.id = T3.emp_id WHERE T3.cur_cd = 'EUR' GROUP BY T1.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: валюта сравнивается со строкой EUR вместо кода, выдача пустая

## 4. logistics/log2-002 ru/1

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
    SELECT T1.title AS city_org, T3.title AS city_dst, COUNT(*) AS cnt FROM cust AS T1 INNER JOIN shp AS T2 ON T1.id = T2.org_cd INNER JOIN cust AS T3 ON T3.id = T2.dst_cd GROUP BY T1.title, T3.title
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
заметка: соединяет коды мест с таблицей клиентов, в ответе названия фирм

## 5. logistics/log2-023 ru/0

ловушка: loc_ref is joined twice under two aliases; the country is a second hop from the city code; domestic shipments must be left out
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT o.country AS from_country, d.country AS to_country, SUM(s.weight_kg) AS kg FROM shp s JOIN loc_ref o ON o.cd = s.org_cd JOIN loc_ref d ON d.cd = s.dst_cd WHERE o.country <> d.country GROUP BY o.country, d.country ORDER BY kg DESC, o.country, d.country
    ('Aldoria', 'Cavira', 853980)
    ('Cavira', 'Dornia', 768032)
    ('Dornia', 'Breland', 652546)
    ('Aldoria', 'Dornia', 645359)
    ('Dornia', 'Cavira', 619521)
    ('Cavira', 'Aldoria', 605945)
    ('Cavira', 'Breland', 579089)
    ('Aldoria', 'Breland', 576170)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT T2.country AS from_country , T3.country AS to_country , sum(T1.weight_kg) AS total_weight FROM shp AS T1 JOIN loc_ref AS T2 ON T1.org_cd = T2.cd JOIN loc_ref AS T3 ON T1.dst_cd = T3.cd GROUP BY T2.country , T3.country
    ('Aldoria', 'Aldoria', 438746)
    ('Aldoria', 'Breland', 576170)
    ('Aldoria', 'Cavira', 853980)
    ('Aldoria', 'Dornia', 645359)
    ('Breland', 'Aldoria', 566250)
    ('Breland', 'Breland', 332712)
    ('Breland', 'Cavira', 537690)
    ('Breland', 'Dornia', 574769)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: не исключил внутренние перевозки, появились пары страны с самой собой

## 6. logistics/log2-031 ru/1

ловушка: the mode is a property of the carrier, so it is two steps away from the leg; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT l.shp_id FROM leg l JOIN carr c ON c.id = l.carr_id GROUP BY l.shp_id HAVING COUNT(DISTINCT c.mode_cd) > 1)
    (434,)

ответ модели:
    SELECT COUNT(*) FROM leg AS T1 JOIN leg AS T2 ON T1.shp_id = T2.shp_id WHERE T1.carr_id != T2.carr_id
    (4464,)

ошибка исполнения: нет

вердикт: model
заметка: считает пары плеч с разными перевозчиками, 4464 против 434

## 7. logistics/log2-037 ru/1

ловушка: an inner join drops the shipments with no leg and raises the average; COUNT(*) counts the row the outer join produced, so the count has to be over the leg's own column
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(k), 2) AS mean_legs FROM (SELECT s.id, COUNT(l.id) AS k FROM shp s LEFT JOIN leg l ON l.shp_id = s.id GROUP BY s.id)
    (2.57,)

ответ модели:
    SELECT AVG(CASE WHEN T2.id IS NULL THEN 0 ELSE 1 END) AS avg FROM shp AS T1 LEFT JOIN leg AS T2 ON T1.id = T2.shp_id
    (0.974025974025974,)

ошибка исполнения: нет

вердикт: model
заметка: усредняет признак наличия плеча, 0.97 против 2.57

## 8. logistics/log2-044 ru/0

ловушка: the cost is a sum over legs while the weight is a single column of the shipment; an integer division returns zero here, the ratio has to be taken in floating point; the question asks which, so the ratio is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT s.id FROM shp s JOIN leg l ON l.shp_id = s.id GROUP BY s.id, s.weight_kg ORDER BY SUM(l.cost_cents) * 1.0 / s.weight_kg DESC, s.id LIMIT 1
    (271,)

ответ модели:
    SELECT T1.title FROM carr AS T1 JOIN leg AS T2 ON T1.id = T2.carr_id ORDER BY T2.cost_cents / T2.dist_km DESC LIMIT 1
    ('Novak Haulage',)

ошибка исполнения: нет

вердикт: model
заметка: вернул перевозчика и считает стоимость на километр вместо веса

## 9. manufacturing/mfg2-010 ru/1

ловушка: the date is split across the legacy pair, on both ends of the range
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT l.title, COUNT(*) AS n FROM mov m JOIN line l ON l.id = m.line_id WHERE COALESCE(m.dt_op, m.recorded_at) >= '2026-01-01' AND COALESCE(m.dt_op, m.recorded_at) < '2026-07-01' GROUP BY l.title ORDER BY n DESC, l.title
    ('Machining', 46)
    ('Finishing', 39)
    ('Assembly B', 34)
    ('Assembly A', 27)

ответ модели:
    SELECT COUNT(*) FROM mov AS T1 INNER JOIN line AS T2 ON T1.line_id = T2.id WHERE T1.dt_op >= '2026-01-01' AND T1.dt_op <= '2026-06-30'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: без COALESCE на дату движения и без разреза по линиям, ответ 0

## 10. manufacturing/mfg2-012 ru/1

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
    SELECT T1.code, T1.title, COUNT(*) FROM part AS T1 INNER JOIN defect AS T2 ON T1.id = T2.mov_id INNER JOIN grade_ref AS T3 ON T2.grade_cd = T3.cd WHERE T3.title = 'критический' GROUP BY T1.code, T1.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: степень ищется по русскому названию и дефект соединён с деталью напрямую

## 11. manufacturing/mfg2-019 ru/0

ловушка: the shift is on the line, not on the movement; the piece rows are not a weight and must be left out
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT s.title AS shift, ROUND(SUM(m.qty * u.to_base), 2) AS kg FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN line l ON l.id = m.line_id JOIN shift_ref s ON s.cd = l.shift_cd WHERE u.title IN ('kilogram', 'tonne') GROUP BY s.title ORDER BY kg DESC, s.title
    ('day', 342510.0)
    ('night', 334633.0)

ответ модели:
    SELECT T2.title, SUM(T3.qty) * T4.to_base AS total_weight FROM mov AS T3 INNER JOIN line AS T2 ON T3.line_id = T2.id INNER JOIN shift_ref AS T1 ON T2.shift_cd = T1.cd INNER JOIN unit_ref AS T4 ON T3.unit_cd = T4.cd GROUP BY T2.title
    ('Assembly A', 41366.61)
    ('Assembly B', 39770.43)
    ('Finishing', 37968.38)
    ('Machining', 39775.18)

ошибка исполнения: нет

вердикт: model
заметка: множит сумму на коэффициент одной произвольной строки и группирует по линии вместо смены

## 12. manufacturing/mfg2-038 ru/1

ловушка: an inner join drops the movements with no defect and flatters every line; the denominator has to count movements once, which the outer join otherwise repeats; the question asks which, so the ratio is not part of the answer
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT l.title FROM mov m JOIN line l ON l.id = m.line_id LEFT JOIN defect d ON d.mov_id = m.id GROUP BY l.title ORDER BY COUNT(d.id) * 1.0 / COUNT(DISTINCT m.id) DESC, l.title LIMIT 1
    ('Assembly B',)

ответ модели:
    SELECT T2.title FROM mov AS T1 INNER JOIN line AS T2 ON T1.line_id = T2.id INNER JOIN defect AS T3 ON T1.id = T3.mov_id GROUP BY T2.title ORDER BY COUNT(T3.id) / COUNT(T1.id) DESC LIMIT 1
    ('Machining',)

ошибка исполнения: нет

вердикт: model
заметка: внутреннее соединение отбрасывает движения без брака, выбрана другая линия

## 13. medicine/med2-043 ru/1

ловушка: the admission date is split across the legacy pair dt_adm/admitted_at; dates are text, so the year is the first four characters; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT pat_id FROM enc GROUP BY pat_id HAVING COUNT(DISTINCT substr(COALESCE(dt_adm, admitted_at), 1, 4)) > 1)
    (188,)

ответ модели:
    SELECT COUNT(DISTINCT pat_id) FROM enc WHERE strftime('%Y', dt_adm) != '2022'
    (190,)

ошибка исполнения: нет

вердикт: model
заметка: считает пациентов с поступлением не в 2022 году вместо тех, у кого годы разные

## 14. public_services/gov2-003 ru/1

ловушка: the denominator is the closed cases only; the unfinished ones cannot be late yet and must not dilute the share; a percentage needs 100.0, because integer division returns zero
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title, ROUND(100.0 * SUM(CASE WHEN c.closed_at > c.due_dt THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL GROUP BY sv.title ORDER BY pct DESC, sv.title
    ('land record extract', 33.3)
    ('trading licence', 27.7)
    ('residence certificate', 24.1)
    ('business registration', 21.5)
    ('building permit', 20.6)

ответ модели:
    SELECT T2.title , CAST(SUM(CASE WHEN T1.due_dt < T1.closed_at THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM case_rec AS T1 JOIN service AS T2 ON T1.service_id = T2.id GROUP BY T2.title
    ('building permit', 18.120805369127517)
    ('business registration', 19.444444444444443)
    ('land record extract', 29.508196721311474)
    ('residence certificate', 20.76923076923077)
    ('trading licence', 26.623376623376622)

ошибка исполнения: нет

вердикт: model
заметка: в знаменателе все дела, а не только завершённые

## 15. public_services/gov2-019 ru/0

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
    SELECT T2.title , count(*) FROM stage AS T1 JOIN service AS T2 ON T1.case_id = T2.id WHERE T1.result_cd = "拒绝" GROUP BY T2.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает результат с иероглифами, выдача пустая

## 16. public_services/gov2-024 ru/0

ловушка: people reapply, so the two numbers answer different questions; one person filing in two regions counts in both, and the regional figures therefore do not add up to the overall number of people
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS region, COUNT(DISTINCT c.applicant_id) AS people, COUNT(*) AS cases FROM case_rec c JOIN office o ON o.id = c.office_id JOIN region_ref r ON r.cd = o.region_cd GROUP BY r.title ORDER BY r.title
    ('Eastvale', 114, 164)
    ('Marden', 116, 148)
    ('Northport', 176, 307)
    ('Thorne', 108, 141)

ответ модели:
    SELECT T2.region_cd , count(DISTINCT T3.applicant_id) , count(*) FROM office AS T1 JOIN service AS T2 ON T1.id = T2.office_id JOIN case_rec AS T3 ON T2.id = T3.service_id GROUP BY T2.region_cd
    ОШИБКА: OperationalError: no such column: T2.region_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: соединяет отделение с услугой, обращается к несуществующей колонке

## 17. public_services/gov2-037 ru/1

ловушка: an inner join drops the cases with no stage and raises the average; COUNT(*) counts the row the outer join produced, so the count has to be over the stage's own column
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(k), 2) AS mean_stages FROM (SELECT c.id, COUNT(s.id) AS k FROM case_rec c LEFT JOIN stage s ON s.case_id = c.id GROUP BY c.id)
    (1.97,)

ответ модели:
    SELECT AVG(CASE WHEN T2.case_id IS NULL THEN 0 ELSE COUNT(T2.case_id) END) FROM case_rec AS T1 LEFT JOIN stage AS T2 ON T1.id = T2.case_id GROUP BY T1.id HAVING COUNT(T1.id) = 2
    ОШИБКА: OperationalError: misuse of aggregate function COUNT()

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: COUNT внутри AVG, misuse of aggregate

## 18. public_services/gov2-038 ru/0

ловушка: the submission date is split across the legacy pair dt_sub/submitted_at; the difference between two text dates needs julianday; a case with no closing date has no duration and must be left out
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT sv.title, CAST(MAX(julianday(c.closed_at) - julianday(COALESCE(c.dt_sub, c.submitted_at))) AS INTEGER) AS days FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL GROUP BY sv.title ORDER BY days DESC, sv.title
    ('building permit', 69)
    ('trading licence', 61)
    ('residence certificate', 54)
    ('business registration', 48)
    ('land record extract', 45)

ответ модели:
    SELECT T2.title , max(T1.due_dt - T1.dt_sub) FROM case_rec AS T1 JOIN service AS T2 ON T1.service_id = T2.id WHERE T1.closed_at IS NOT NULL GROUP BY T2.title
    ('building permit', 0)
    ('business registration', 0)
    ('land record extract', 0)
    ('residence certificate', 0)
    ('trading licence', 0)

ошибка исполнения: нет

вердикт: model
заметка: вычитает текстовые даты и берёт срок вместо даты закрытия, все нули

## 19. public_services/gov2-042 ru/1

ловушка: the applicant's city holds a region name, so the comparison is between a column of one table and a column of another; an applicant with no city recorded matches nothing, because NULL is not equal to anything, and still belongs in the denominator; three joins to reach the region from the case
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS region, ROUND(100.0 * SUM(CASE WHEN a.city = r.title THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct FROM case_rec c JOIN applicant a ON a.id = c.applicant_id JOIN office o ON o.id = c.office_id JOIN region_ref r ON r.cd = o.region_cd GROUP BY r.title ORDER BY pct DESC, r.title
    ('Thorne', 26.24)
    ('Eastvale', 21.95)
    ('Marden', 20.27)
    ('Northport', 17.59)

ответ модели:
    SELECT T1.title AS region_title , CAST(SUM(CASE WHEN T3.city = T1.title THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) AS proportion FROM region_ref AS T1 JOIN office AS T2 ON T1.cd = T2.region_cd JOIN applicant AS T3 ON T3.id = T2.id GROUP BY T1.title ORDER BY proportion DESC
    ('Thorne', 0.0)
    ('Northport', 0.0)
    ('Marden', 0.0)
    ('Eastvale', 0.0)

ошибка исполнения: нет

вердикт: model
заметка: соединяет заявителя с отделением по идентификатору, все доли нулевые

## 20. public_services/gov2-046 ru/1

ловушка: the allowance is a column of the service, so the threshold differs from row to row; the subtraction runs in the opposite direction from the usual lateness question; a case with no closing date cannot qualify and must be excluded
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM case_rec c JOIN service sv ON sv.id = c.service_id WHERE c.closed_at IS NOT NULL AND julianday(c.due_dt) - julianday(c.closed_at) > sv.sla_days * 1.0 / 2
    (206,)

ответ модели:
    SELECT COUNT(*) FROM case_rec AS T1 JOIN service AS T2 ON T1.service_id = T2.id WHERE T1.closed_at < T1.due_dt AND T1.due_dt - T1.closed_at > T2.sla_days / 2
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: вычитает текстовые даты без julianday, ответ 0
