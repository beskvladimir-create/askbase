# Ручной разбор провалов: xiyan-7b-q4.set2-base-ru.jsonl

Провалов всего: 473 из 576.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank2-012 ru/0

ловушка: principal is stored in minor units although its name does not say so; a loan is open when closed_at IS NULL
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT SUM(principal) / 100.0 AS outstanding FROM loan WHERE closed_at IS NULL
    (4193712.0,)

ответ модели:
    SELECT SUM(principal) FROM loan WHERE closed_at IS NULL
    (419371200,)

ошибка исполнения: нет

вердикт: model
заметка: копейки не переведены, 419 миллионов вместо 4.19 миллиона

## 2. hr/hr2-022 ru/1

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
    SELECT T1.full_name FROM emp AS T1 INNER JOIN pay_hist AS T2 ON T1.id = T2.emp_id INNER JOIN cur_ref AS T3 ON T2.cur_cd = T3.cd WHERE T3.title = 'US Dollars'
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: валюта ищется как US Dollars, выдача пустая

## 3. hr/hr2-036 ru/1

ловушка: a missing manager is NULL, which no equality test matches; the second condition is an existence test on the same table under another alias
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT e.full_name FROM emp e WHERE e.mgr_id IS NULL AND EXISTS (SELECT 1 FROM emp r WHERE r.mgr_id = e.id) ORDER BY e.full_name
    ('Alina Hale',)
    ('Alina Oduya',)
    ('Alina Petran',)
    ('Anna Kovach',)
    ('Anna Novak',)
    ('Artem Oduya',)
    ('Boris Almeida',)
    ('Boris Kristof',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT full_name FROM emp WHERE id IN ( SELECT mgr_id FROM emp WHERE mgr_id IS NOT NULL GROUP BY mgr_id HAVING COUNT(mgr_id) > 1 ) AND mgr_id IS NULL
    ('Alina Petran',)
    ('Mark Kristof',)
    ('Alina Hale',)
    ('Victor Oduya',)
    ('Nina Varga',)
    ('Mark Petran',)
    ('Anna Kovach',)
    ('Elena Marek',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: требует больше одного подчинённого и теряет часть людей

## 4. hr/hr2-048 ru/1

ловушка: dept checked against itself under another alias, by the parent reference and not by a join to the employee; working is status_cd = 1, and the leaving date does not decide it
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 AND EXISTS (SELECT 1 FROM dept c WHERE c.parent_id = d.id)
    (65,)

ответ модели:
    SELECT COUNT(DISTINCT T1.id) FROM emp AS T1 INNER JOIN dept AS T2 ON T1.dept_id = T2.id WHERE T2.id = T2.parent_id
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает отдел сам с собой по parent_id, ответ 0

## 5. logistics/log2-021 ru/1

ловушка: the customer's city is text and the origin is a code, so the two meet only through the lookup's title; a customer with no city recorded matches nothing, which is correct
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM shp s JOIN cust c ON c.id = s.cust_id JOIN loc_ref o ON o.cd = s.org_cd WHERE c.city = o.title
    (71,)

ответ модели:
    SELECT COUNT(*) FROM cust AS T1 INNER JOIN shp AS T2 ON T1.id = T2.cust_id WHERE T1.city = ( SELECT city FROM cust WHERE id = T2.cust_id )
    (650,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает город клиента сам с собой, условие всегда истинно, 650 против 71

## 6. logistics/log2-028 ru/1

ловушка: anti-join through a second table: the status is on the shipment, not on the leg; lost is status_cd = 3, a code and not a word
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT c.title FROM carr c WHERE NOT EXISTS ( SELECT 1 FROM leg l JOIN shp s ON s.id = l.shp_id WHERE l.carr_id = c.id AND s.status_cd = 3) ORDER BY c.title
    ('Bauer Haulage',)
    ('Hale Transit',)
    ('Kristof Logistics',)
    ('Marek Logistics',)
    ('Petran Haulage',)

ответ модели:
    SELECT T1.title FROM carr AS T1 JOIN leg AS T2 ON T1.id = T2.carr_id JOIN shp AS T3 ON T2.shp_id = T3.id JOIN status_ref AS T4 ON T3.status_cd = T4.cd WHERE T4.title != 'Lost' GROUP BY T1.id HAVING count(*) = 0
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: HAVING count(*) = 0 после внутреннего соединения недостижимо, выдача пустая

## 7. logistics/log2-034 ru/0

ловушка: the status says delivered while the date says the delivery has not happened yet; today is a literal in the question, there is no current date in the data
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE delivered_at > '2026-11-02'
    (19,)

ответ модели:
    SELECT COUNT(*) FROM shp WHERE dt_disp > '2026-11-02'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает дату отправки вместо даты сдачи, ответ 0

## 8. logistics/log2-038 ru/1

ловушка: how many countries exist is a fact of loc_ref, not a number to hard-code; the country is one step beyond the destination code; HAVING over a distinct count, and the grouped rows then have to be counted again
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT c.id FROM cust c JOIN shp s ON s.cust_id = c.id JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY c.id HAVING COUNT(DISTINCT d.country) = (SELECT COUNT(DISTINCT country) FROM loc_ref))
    (37,)

ответ модели:
    SELECT COUNT(DISTINCT T1.id) FROM cust AS T1 JOIN shp AS T2 ON T1.id = T2.cust_id JOIN loc_ref AS T3 ON T3.cd = T2.dst_cd GROUP BY T1.id HAVING COUNT(DISTINCT T3.country) = (SELECT COUNT(*) FROM loc_ref)
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает с числом строк справочника вместо числа стран, выдача пустая

## 9. manufacturing/mfg2-009 ru/0

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
    SELECT T1.id , SUM(T3.qty * T2.minor) AS cost FROM part AS T1 JOIN part_price AS T2 ON T1.id = T2.part_id JOIN mov AS T3 ON T1.id = T3.part_id WHERE T2.valid_from <= date('now') AND T2.valid_to >= date('now') GROUP BY T1.id
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: сравнивает окно с сегодняшней датой, открытое окно с NULL не найдено

## 10. manufacturing/mfg2-011 ru/0

ловушка: the shift belongs to the line, which is two joins from the defect; both the shift and the grade are codes, and both names are in lookups
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT g.title AS grade, COUNT(*) AS n FROM defect d JOIN mov m ON m.id = d.mov_id JOIN line l ON l.id = m.line_id JOIN shift_ref s ON s.cd = l.shift_cd JOIN grade_ref g ON g.cd = d.grade_cd WHERE s.title = 'night' GROUP BY g.title ORDER BY n DESC, g.title
    ('minor', 103)
    ('major', 59)
    ('critical', 17)

ответ модели:
    SELECT T1.grade_cd , COUNT(*) FROM grade_ref AS T1 JOIN defect AS T2 ON T1.cd = T2.grade_cd JOIN mov AS T3 ON T2.mov_id = T3.id JOIN shift_ref AS T4 ON T3.shift_cd = T4.cd WHERE T4.title = 'night' GROUP BY T1.grade_cd
    ОШИБКА: OperationalError: no such column: T1.grade_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: обращается к grade_ref.grade_cd и к mov.shift_cd, таких колонок нет

## 11. manufacturing/mfg2-017 ru/1

ловушка: both the numerator and the denominator need the unit conversion, and leaving it out of one of the two skews the share
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT p.title, ROUND(100.0 * SUM(CASE WHEN m.kind_cd = 3 THEN m.qty * u.to_base ELSE 0 END) / SUM(m.qty * u.to_base), 1) AS pct FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id GROUP BY p.title ORDER BY pct DESC, p.title
    ('bushing', 15.4)
    ('bracket', 15.2)
    ('shaft', 12.0)
    ('spring', 7.9)
    ('plate', 7.3)
    ('gearwheel', 3.4)

ответ модели:
    SELECT T1.id, CAST(COUNT(T2.id) AS REAL) * 100 / ( SELECT COUNT(T2.id) FROM part AS T1 LEFT JOIN mov AS T2 ON T1.id = T2.part_id LEFT JOIN defect AS T3 ON T2.id = T3.mov_id ) AS percentage FROM part AS T1 LEFT JOIN mov AS T2 ON T1.id = T2.part_id LEFT JOIN defect AS T3 ON T2.id = T3.mov_id GROUP BY T1.id
    (1, 36.20352250489237)
    (2, 25.73385518590998)
    (3, 17.5146771037182)
    (4, 11.741682974559687)
    (5, 6.457925636007828)
    (6, 2.3483365949119372)

ошибка исполнения: нет

вердикт: model
заметка: считает доли по числу строк соединения, а не по количеству в базовых единицах

## 12. manufacturing/mfg2-036 ru/1

ловушка: a defect found before its movement would drag the average down and the question excludes it; the movement date is split across the legacy pair dt_op/recorded_at; the grade is a code, its name lives in grade_ref
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT g.title AS grade, ROUND(AVG(julianday(d.found_at) - julianday(COALESCE(m.dt_op, m.recorded_at))), 2) AS days FROM defect d JOIN mov m ON m.id = d.mov_id JOIN grade_ref g ON g.cd = d.grade_cd WHERE d.found_at >= COALESCE(m.dt_op, m.recorded_at) GROUP BY g.title ORDER BY days DESC, g.title
    ('major', 479.17)
    ('minor', 385.42)
    ('critical', 324.8)

ответ модели:
    SELECT grade_ref.title , avg(julianday(defect.found_at) - julianday(mov.dt_op)) FROM defect JOIN grade_ref ON grade_ref.cd = defect.grade_cd JOIN mov ON mov.id = defect.mov_id WHERE defect.found_at > mov.dt_op GROUP BY grade_ref.title
    ('critical', 344.0)
    ('major', 503.68)
    ('minor', 411.8958333333333)

ошибка исполнения: нет

вердикт: model
заметка: без COALESCE на дату движения, 503.68 против 479.17

## 13. medicine/med2-041 ru/0

ловушка: the grouping is over two columns at once, and the answer counts groups rather than rows; nothing in the schema forbids the repetition, so the answer is a number and not zero
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM (SELECT enc_id, code FROM dx GROUP BY enc_id, code HAVING COUNT(*) > 1)
    (81,)

ответ модели:
    SELECT code, COUNT(*) AS occurrences FROM dx WHERE primary_flag = 'Y' GROUP BY code HAVING occurrences >= 2
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: фильтрует по primary_flag = Y и группирует без случая, выдача пустая

## 14. medicine/med2-048 ru/0

ловушка: two joins to reach it: prescription to encounter to doctor, where the department lives; the route is a code, 2 is intravenous; the share counts the qualifying rows against all rows of the group, so the condition goes inside the aggregate
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT d.dept, ROUND(100.0 * SUM(CASE WHEN x.route_cd = 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct FROM rx x JOIN enc e ON e.id = x.enc_id JOIN doc d ON d.id = e.doc_id GROUP BY d.dept ORDER BY pct DESC, d.dept
    ('surgery', 28.76)
    ('neurology', 26.83)
    ('oncology', 22.78)
    ('endocrinology', 22.69)
    ('cardiology', 21.99)

ответ модели:
    SELECT d.dept , CAST(COUNT(rx.id) AS REAL) * 100 / ( SELECT COUNT(*) FROM rx AS r2 JOIN enc AS e2 ON r2.enc_id = e2.id JOIN doc AS d2 ON e2.doc_id = d2.id WHERE d2.dept = d.dept ) AS percentage FROM rx JOIN enc ON rx.enc_id = enc.id JOIN doc AS d ON enc.doc_id = d.id WHERE rx.route_cd = ( SELECT cd FROM route_ref WHERE title = 'Intravenous' ) GROUP BY d.dept
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: путь введения ищется как Intravenous, выдача пустая

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
    SELECT T1.title , COUNT(*) FROM service AS T1 JOIN case_rec AS T2 ON T1.id = T2.service_id JOIN stage AS T3 ON T2.id = T3.case_id WHERE T3.result_cd = 'REJECT' GROUP BY T1.id
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: результат сравнивается со словом REJECT, выдача пустая

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
    SELECT T3.title , COUNT(DISTINCT T1.applicant_id) , COUNT(T1.id) FROM case_rec AS T1 INNER JOIN applicant AS T2 ON T1.applicant_id = T2.id INNER JOIN region_ref AS T3 ON T4.region_cd = T3.cd GROUP BY T3.title
    ОШИБКА: OperationalError: no such column: T4.region_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: ссылка на несуществующий псевдоним T4

## 17. public_services/gov2-037 ru/1

ловушка: an inner join drops the cases with no stage and raises the average; COUNT(*) counts the row the outer join produced, so the count has to be over the stage's own column
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT ROUND(AVG(k), 2) AS mean_stages FROM (SELECT c.id, COUNT(s.id) AS k FROM case_rec c LEFT JOIN stage s ON s.case_id = c.id GROUP BY c.id)
    (1.97,)

ответ модели:
    SELECT CAST(COUNT(T1.id) AS REAL) / COUNT(CASE WHEN T2.case_id IS NULL THEN 1 ELSE T2.seq END) AS num FROM case_rec AS T1 LEFT JOIN stage AS T2 ON T1.id = T2.case_id
    (1.0,)

ошибка исполнения: нет

вердикт: model
заметка: делит число дел на число этапов, ответ 1.0 вместо 1.97

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
    SELECT T1.title , max(T2.due_dt - T2.submitted_at) FROM service AS T1 JOIN case_rec AS T2 ON T1.id = T2.service_id WHERE T2.closed_at IS NOT NULL GROUP BY T1.title
    ('building permit', 1)
    ('business registration', 1)
    ('land record extract', 0)
    ('residence certificate', 1)
    ('trading licence', 1)

ошибка исполнения: нет

вердикт: model
заметка: вычитает текстовые даты и берёт срок вместо даты закрытия

## 19. public_services/gov2-044 ru/0

ловушка: an anti-join on the same table, asking that no later stage exists; a decided stage is one whose result_cd is not NULL, which no equality test finds
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT COUNT(*) AS n FROM stage s WHERE s.seq = 1 AND s.result_cd IS NOT NULL AND NOT EXISTS (SELECT 1 FROM stage s2 WHERE s2.case_id = s.case_id AND s2.seq > 1)
    (169,)

ответ модели:
    SELECT COUNT(*) FROM stage AS T1 LEFT JOIN stage AS T2 ON T1.case_id = T2.case_id AND T2.seq > T1.seq WHERE T1.seq = 1 AND T2.id IS NULL
    (208,)

ошибка исполнения: нет

вердикт: model
заметка: нет условия на решённость первого этапа, 208 против 169

## 20. public_services/gov2-047 ru/0

ловушка: distinct people, not cases: one person with three cases of the same result counts once; the last stage is the largest seq of that case, which is a correlated subquery; the result is a code, its name lives in result_ref, and an undecided stage drops out of the join
вопрос:  (не публикуется, набор 2 действующий; см. HOLDOUT.md, раздел про закрытые формулировки)

эталон:
    SELECT r.title AS result, COUNT(DISTINCT c.applicant_id) AS people FROM stage s JOIN case_rec c ON c.id = s.case_id JOIN result_ref r ON r.cd = s.result_cd WHERE s.seq = (SELECT MAX(s2.seq) FROM stage s2 WHERE s2.case_id = s.case_id) GROUP BY r.title ORDER BY people DESC, r.title
    ('approved', 173)
    ('refused', 93)
    ('withdrawn', 48)

ответ модели:
    SELECT T1.title , COUNT(DISTINCT T3.applicant_id) FROM result_ref AS T1 JOIN stage AS T2 ON T1.cd = T2.result_cd JOIN case_rec AS T3 ON T2.case_id = T3.id GROUP BY T1.title
    ('approved', 210)
    ('refused', 146)
    ('withdrawn', 102)

ошибка исполнения: нет

вердикт: model
заметка: считает людей по всем этапам, а не по последнему, числа выше
