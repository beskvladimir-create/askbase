# Ручной разбор провалов: xiyan-7b-q4.holdout-en.jsonl

Провалов всего: 71 из 96.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank-003 en/1

ловушка: operation date is split across the legacy pair dt_op/posted_at
вопрос:  Count the operations dated between April and June 2026 inclusive.

эталон:
    SELECT COUNT(*) AS n FROM txn WHERE COALESCE(dt_op, posted_at) >= '2026-04-01' AND COALESCE(dt_op, posted_at) < '2026-07-01'
    (410,)

ответ модели:
    SELECT COUNT(*) FROM txn WHERE dt_op BETWEEN '2026-04-01' AND '2026-06-30'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 2. banking/bank-004 en/0

ловушка: the category name lives in mcc_ref, the code alone is not an answer
вопрос:  Which three merchant categories are used most often, by name?

эталон:
    SELECT m.title, COUNT(*) AS n FROM txn t JOIN mcc_ref m ON m.code = t.mcc GROUP BY m.title ORDER BY n DESC, m.title LIMIT 3
    ('cash withdrawal', 340)
    ('electronics stores', 312)
    ('restaurants', 302)

ответ модели:
    SELECT T1.title FROM mcc_ref AS T1 JOIN txn AS T2 ON T1.code = T2.mcc GROUP BY T1.title ORDER BY count(*) DESC LIMIT 3
    ('cash withdrawal',)
    ('electronics stores',)
    ('restaurants',)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 3. banking/bank-005 en/0

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Which customers hold no account at all?

эталон:
    SELECT c.full_name FROM cust c WHERE NOT EXISTS (SELECT 1 FROM acct a WHERE a.cust_id = c.id) ORDER BY c.full_name
    ('Alina Bauer',)
    ('Alina Benali',)
    ('Alina Kovach',)
    ('Alina Marek',)
    ('Alina Oduya',)
    ('Alina Oduya',)
    ('Alina Reiner',)
    ('Alina Varga',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT id FROM cust WHERE id NOT IN (SELECT cust_id FROM acct)
    (28,)
    (39,)
    (41,)
    (51,)
    (54,)
    (58,)
    (59,)
    (60,)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 4. banking/bank-007 en/1

ловушка: DISTINCT customer, not account count; 'active' is status_cd = 1, and residency is a second coded column
вопрос:  Split holders of active accounts into residents and non-residents, counting each customer once.

эталон:
    SELECT r.title AS residency, COUNT(DISTINCT a.cust_id) AS customers FROM acct a JOIN cust c ON c.id = a.cust_id JOIN resid_ref r ON r.cd = c.resid_cd WHERE a.status_cd = 1 GROUP BY r.title ORDER BY customers DESC, r.title
    ('resident', 189)
    ('non-resident', 34)

ответ модели:
    SELECT DISTINCT CASE WHEN T1.resid_cd = 'R' THEN 'Resident' ELSE 'Non-Resident' END AS cust_type FROM cust AS T1 INNER JOIN acct AS T2 ON T1.id = T2.cust_id INNER JOIN acct_status_ref AS T3 ON T2.status_cd = T3.cd WHERE T3.title = 'Active'
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 5. hr/hr-003 en/0

ловушка: salary is effective-dated; the current one is the latest from_dt per person; amounts are minor units and must be divided by 100
вопрос:  Who are the five highest paid people, at their current salary?

эталон:
    SELECT e.full_name, p.amount_minor / 100.0 AS pay FROM emp e JOIN pay_hist p ON p.emp_id = e.id WHERE p.from_dt = ( SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id ) ORDER BY pay DESC, e.full_name LIMIT 5
    ('Irina Oduya', 10996.0)
    ('Victor Kristof', 10988.0)
    ('Artem Oduya', 10948.0)
    ('Daniel Almeida', 10890.0)
    ('Victor Marek', 10856.0)

ответ модели:
    SELECT T1.full_name FROM emp AS T1 INNER JOIN pay_hist AS T2 ON T1.id = T2.emp_id WHERE T2.from_dt = ( SELECT MAX(from_dt) FROM pay_hist AS T2i WHERE T2i.emp_id = T2.emp_id ) ORDER BY T2.amount_minor DESC LIMIT 5
    ('Irina Oduya',)
    ('Victor Kristof',)
    ('Artem Oduya',)
    ('Daniel Almeida',)
    ('Victor Marek',)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 6. hr/hr-005 en/0

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Which employees have no salary record at all?

эталон:
    SELECT e.full_name FROM emp e WHERE NOT EXISTS (SELECT 1 FROM pay_hist p WHERE p.emp_id = e.id) ORDER BY e.full_name
    ('Alina Novak',)
    ('Anna Almeida',)
    ('Anna Hale',)
    ('Anna Petran',)
    ('Artem Almeida',)
    ('Artem Linde',)
    ('Artem Marek',)
    ('Artem Reiner',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT id FROM emp WHERE id NOT IN (SELECT emp_id FROM pay_hist)
    (60,)
    (77,)
    (147,)
    (184,)
    (221,)
    (222,)
    (223,)
    (224,)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 7. logistics/log-004 en/0

ловушка: cost is stored in minor units and must be divided by 100
вопрос:  What do all the legs cost in total, in currency units?

эталон:
    SELECT SUM(cost_cents) / 100.0 AS total_cost FROM leg
    (8579947.13,)

ответ модели:
    SELECT sum(cost_cents) / 100 AS total_cost FROM leg
    (8579947,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 8. logistics/log-007 en/0

ловушка: DISTINCT carrier, not leg count; the destination end of the route, not the origin
вопрос:  How many distinct carriers serve each destination?

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
    SELECT count(DISTINCT T1.id) , T1.dst_cd FROM shp AS T1 JOIN leg AS T2 ON T1.id = T2.shp_id GROUP BY T1.dst_cd
    (72, 1)
    (91, 2)
    (72, 3)
    (103, 4)
    (77, 5)
    (86, 6)
    (75, 7)
    (75, 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 9. logistics/log-007 en/1

ловушка: DISTINCT carrier, not leg count; the destination end of the route, not the origin
вопрос:  Per destination, count the unique carriers that have carried a leg there.

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
    SELECT T1.title , COUNT (DISTINCT T3.carr_id) FROM loc_ref AS T1 JOIN leg AS T3 ON T1.cd = T3.dst_cd GROUP BY T1.title
    ОШИБКА: OperationalError: no such column: T3.dst_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 10. manufacturing/mfg-002 en/0

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  How much was scrapped in total, converted to the base unit?

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(T1.qty * T2.to_base) AS total FROM mov AS T1 INNER JOIN unit_ref AS T2 ON T1.unit_cd = T2.cd WHERE T1.kind_cd = 'scrap'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 11. manufacturing/mfg-002 en/1

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Add up the scrapped quantity, bringing every row to the same unit first.

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(CASE WHEN T1.unit_cd = 'pc' THEN T1.qty * 1000 WHEN T1.unit_cd = 'kg' THEN T1.qty ELSE T1.qty END) AS scrapped_quantity FROM mov AS T1 INNER JOIN mov_kind_ref AS T2 ON T1.kind_cd = T2.cd WHERE T2.title = 'scrapped'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 12. manufacturing/mfg-008 en/0

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Which parts have more than ten defects?

эталон:
    SELECT p.title, COUNT(*) AS defects FROM defect d JOIN mov m ON m.id = d.mov_id JOIN part p ON p.id = m.part_id GROUP BY p.id, p.title HAVING COUNT(*) > 10 ORDER BY defects DESC, p.title
    ('bracket', 128)
    ('shaft', 83)
    ('gearwheel', 41)
    ('plate', 39)
    ('bushing', 22)

ответ модели:
    SELECT T1.id FROM part AS T1 JOIN mov AS T2 ON T1.id = T2.part_id JOIN defect AS T3 ON T2.id = T3.mov_id GROUP BY T1.id HAVING COUNT(*) > 10
    (1,)
    (2,)
    (3,)
    (4,)
    (5,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 13. manufacturing/mfg-008 en/1

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Show the parts with eleven or more defects, and how many each has.

эталон:
    SELECT p.title, COUNT(*) AS defects FROM defect d JOIN mov m ON m.id = d.mov_id JOIN part p ON p.id = m.part_id GROUP BY p.id, p.title HAVING COUNT(*) > 10 ORDER BY defects DESC, p.title
    ('bracket', 128)
    ('shaft', 83)
    ('gearwheel', 41)
    ('plate', 39)
    ('bushing', 22)

ответ модели:
    SELECT T1.id , count(*) FROM part AS T1 JOIN mov AS T2 ON T1.id = T2.part_id JOIN defect AS T3 ON T2.id = T3.mov_id GROUP BY T1.id HAVING count(*) >= 11
    (1, 128)
    (2, 83)
    (3, 39)
    (4, 41)
    (5, 22)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 14. medicine/med-001 en/1

ловушка: sex is a code, needs the lookup join
вопрос:  Break the patient list down by sex and give me the counts.

эталон:
    SELECT r.title AS sex, COUNT(*) AS n FROM pat p JOIN sex_ref r ON r.cd = p.sex_cd GROUP BY r.title ORDER BY n DESC
    ('female', 201)
    ('male', 199)

ответ модели:
    SELECT sex_cd , count(*) FROM pat GROUP BY sex_cd
    (1, 199)
    (2, 201)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 15. medicine/med-002 en/1

ловушка: 'discharged' is status_cd = 2, not the discharged column
вопрос:  Give me the top five doctors by number of discharged encounters.

эталон:
    SELECT d.full_name, COUNT(*) AS n FROM enc e JOIN doc d ON d.id = e.doc_id WHERE e.status_cd = 2 GROUP BY d.full_name ORDER BY n DESC, d.full_name LIMIT 5
    ('Artem Petran', 35)
    ('Olga Almeida', 23)
    ('Anna Varga', 21)
    ('Artem Kristof', 21)
    ('Irina Varga', 21)

ответ модели:
    SELECT T1.full_name FROM doc AS T1 JOIN enc AS T2 ON T1.id = T2.doc_id GROUP BY T2.doc_id ORDER BY count(*) DESC LIMIT 5
    ('Artem Kristof',)
    ('Olga Almeida',)
    ('Artem Petran',)
    ('Boris Linde',)
    ('Sofia Kristof',)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 16. medicine/med-004 en/0

ловушка: diagnosis name lives in dx_ref, the code alone is not an answer
вопрос:  What are the three most common primary diagnoses, by name?

эталон:
    SELECT x.title, COUNT(*) AS n FROM dx JOIN dx_ref x ON x.code = dx.code WHERE dx.primary_flag = 1 GROUP BY x.title ORDER BY n DESC, x.title LIMIT 3
    ('essential hypertension', 104)
    ('epilepsy', 98)
    ('chronic kidney disease', 96)

ответ модели:
    SELECT T1.title FROM dx_ref AS T1 INNER JOIN dx AS T2 ON T1.code = T2.code WHERE T2.primary_flag = 'Y' GROUP BY T1.title ORDER BY COUNT(*) DESC LIMIT 3
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 17. medicine/med-005 en/0

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Which patients have no encounters at all?

эталон:
    SELECT p.full_name FROM pat p WHERE NOT EXISTS (SELECT 1 FROM enc e WHERE e.pat_id = p.id) ORDER BY p.full_name
    ('Alina Marek',)
    ('Anna Almeida',)
    ('Anna Bauer',)
    ('Anna Hale',)
    ('Anna Reiner',)
    ('Anna Reiner',)
    ('Artem Almeida',)
    ('Artem Novak',)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT id FROM pat WHERE id NOT IN (SELECT pat_id FROM enc)
    (4,)
    (13,)
    (14,)
    (15,)
    (20,)
    (41,)
    (62,)
    (68,)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 18. medicine/med-008 en/0

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Which patients were admitted more than twice?

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
    SELECT p.id, p.full_name FROM pat p JOIN enc e ON p.id = e.pat_id GROUP BY p.id HAVING COUNT(e.id) > 2
    (3, 'Mark Reiner')
    (7, 'Timur Varga')
    (9, 'Pavel Marek')
    (10, 'Igor Marek')
    (11, 'Mark Bauer')
    (17, 'Pavel Marek')
    (19, 'Artem Kovach')
    (22, 'Timur Almeida')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 19. medicine/med-008 en/1

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Show patients with three or more encounters, and how many each had.

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
    SELECT count(*) AS num_encounters , p.id , p.full_name FROM pat p JOIN enc e ON p.id = e.pat_id GROUP BY p.id HAVING num_encounters >= 3
    (3, 3, 'Mark Reiner')
    (3, 7, 'Timur Varga')
    (3, 9, 'Pavel Marek')
    (3, 10, 'Igor Marek')
    (3, 11, 'Mark Bauer')
    (5, 17, 'Pavel Marek')
    (3, 19, 'Artem Kovach')
    (3, 22, 'Timur Almeida')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 20. public_services/gov-004 en/1

ловушка: the submission date is split across the legacy pair dt_sub/submitted_at
вопрос:  Count the cases lodged between April and June 2026 inclusive.

эталон:
    SELECT COUNT(*) AS n FROM case_rec WHERE COALESCE(dt_sub, submitted_at) >= '2026-04-01' AND COALESCE(dt_sub, submitted_at) < '2026-07-01'
    (124,)

ответ модели:
    SELECT count(*) FROM case_rec WHERE STRFTIME('%Y-%m',dt_sub) BETWEEN '2026-04' AND '2026-06'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям
