# Ручной разбор провалов: xiyan-14b-q4.holdout-en.jsonl

Провалов всего: 73 из 96.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank-004 en/0

ловушка: the category name lives in mcc_ref, the code alone is not an answer
вопрос:  Which three merchant categories are used most often, by name?

эталон:
    SELECT m.title, COUNT(*) AS n FROM txn t JOIN mcc_ref m ON m.code = t.mcc GROUP BY m.title ORDER BY n DESC, m.title LIMIT 3
    ('cash withdrawal', 340)
    ('electronics stores', 312)
    ('restaurants', 302)

ответ модели:
    SELECT T2.title FROM txn AS T1 JOIN mcc_ref AS T2 ON T1.mcc = T2.code GROUP BY T2.title ORDER BY count(*) DESC LIMIT 3
    ('cash withdrawal',)
    ('electronics stores',)
    ('restaurants',)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 2. banking/bank-004 en/1

ловушка: the category name lives in mcc_ref, the code alone is not an answer
вопрос:  Name the top three spending categories and how many transactions each has.

эталон:
    SELECT m.title, COUNT(*) AS n FROM txn t JOIN mcc_ref m ON m.code = t.mcc GROUP BY m.title ORDER BY n DESC, m.title LIMIT 3
    ('cash withdrawal', 340)
    ('electronics stores', 312)
    ('restaurants', 302)

ответ модели:
    SELECT T2.title , count(*) FROM txn AS T1 JOIN dir_ref AS T2 ON T1.dir_cd = T2.cd GROUP BY T2.title ORDER BY count(*) DESC LIMIT 3
    ('debit', 1612)
    ('credit', 788)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 3. banking/bank-005 en/1

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  List the customers who have never had an account opened for them.

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
    SELECT full_name FROM cust EXCEPT SELECT T1.full_name FROM cust AS T1 JOIN acct AS T2 ON T1.id = T2.cust_id
    ('Alina Reiner',)
    ('Alina Varga',)
    ('Anna Novak',)
    ('Artem Reiner',)
    ('Boris Hale',)
    ('Elena Kovach',)
    ('Igor Almeida',)
    ('Igor Benali',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 4. hr/hr-001 en/0

ловушка: status is a code, needs the lookup join
вопрос:  How many people are there in each employment status?

эталон:
    SELECT s.title AS status, COUNT(*) AS n FROM emp e JOIN emp_status_ref s ON s.cd = e.status_cd GROUP BY s.title ORDER BY n DESC, s.title
    ('working', 186)
    ('left', 55)
    ('unpaid leave', 19)

ответ модели:
    SELECT status_cd , count(*) FROM emp GROUP BY status_cd
    (1, 186)
    (2, 19)
    (3, 55)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 5. hr/hr-003 en/1

ловушка: salary is effective-dated; the current one is the latest from_dt per person; amounts are minor units and must be divided by 100
вопрос:  Give me the top five by the salary in force today, in whole units.

эталон:
    SELECT e.full_name, p.amount_minor / 100.0 AS pay FROM emp e JOIN pay_hist p ON p.emp_id = e.id WHERE p.from_dt = ( SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id ) ORDER BY pay DESC, e.full_name LIMIT 5
    ('Irina Oduya', 10996.0)
    ('Victor Kristof', 10988.0)
    ('Artem Oduya', 10948.0)
    ('Daniel Almeida', 10890.0)
    ('Victor Marek', 10856.0)

ответ модели:
    SELECT emp_id , amount_minor FROM pay_hist ORDER BY amount_minor DESC LIMIT 5
    (164, 1099600)
    (48, 1098900)
    (31, 1098800)
    (192, 1098000)
    (9, 1095200)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 6. logistics/log-004 en/0

ловушка: cost is stored in minor units and must be divided by 100
вопрос:  What do all the legs cost in total, in currency units?

эталон:
    SELECT SUM(cost_cents) / 100.0 AS total_cost FROM leg
    (8579947.13,)

ответ модели:
    SELECT sum(cost_cents) / 100 FROM leg
    (8579947,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 7. logistics/log-004 en/1

ловушка: cost is stored in minor units and must be divided by 100
вопрос:  Add up the cost of every leg and give the answer in whole units rather than minor units.

эталон:
    SELECT SUM(cost_cents) / 100.0 AS total_cost FROM leg
    (8579947.13,)

ответ модели:
    SELECT sum(cost_cents) / 100 FROM leg
    (8579947,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 8. logistics/log-007 en/1

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
    SELECT dst_cd , count(DISTINCT carr_id) FROM leg GROUP BY dst_cd
    ОШИБКА: OperationalError: no such column: dst_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 9. logistics/log-008 en/0

ловушка: HAVING on an aggregate, which RedSQL found models get wrong most often
вопрос:  Which shipments travelled more than three thousand kilometres in total?

эталон:
    SELECT g.shp_id, SUM(g.dist_km) AS km FROM leg g GROUP BY g.shp_id HAVING SUM(g.dist_km) > 3000 ORDER BY km DESC, g.shp_id
    (234, 12097)
    (552, 11822)
    (545, 11459)
    (659, 11313)
    (391, 11159)
    (278, 11090)
    (606, 10943)
    (558, 10837)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT T1.id FROM shp AS T1 JOIN leg AS T2 ON T1.id = T2.shp_id GROUP BY T1.id HAVING sum(T2.dist_km) > 3000
    (5,)
    (7,)
    (8,)
    (9,)
    (10,)
    (12,)
    (14,)
    (16,)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 10. manufacturing/mfg-004 en/0

ловушка: the price is effective-dated; the join is on a range, not on equality; valid_to NULL means still in force; quantities need converting and the price is in minor units
вопрос:  Which three parts cost the most in total, at the price in force on each movement?

эталон:
    SELECT p.title, SUM(m.qty * u.to_base * pp.minor / 100.0) AS cost FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd JOIN part p ON p.id = m.part_id JOIN part_price pp ON pp.part_id = m.part_id AND COALESCE(m.dt_op, m.recorded_at) >= pp.valid_from AND (pp.valid_to IS NULL OR COALESCE(m.dt_op, m.recorded_at) < pp.valid_to) GROUP BY p.title ORDER BY cost DESC, p.title LIMIT 3
    ('bracket', 9447027.370000001)
    ('shaft', 9250141.08)
    ('bushing', 5679813.23)

ответ модели:
    SELECT T1.title , sum(T3.minor) FROM part AS T1 JOIN mov AS T2 ON T1.id = T2.part_id JOIN part_price AS T3 ON T1.id = T3.part_id GROUP BY T1.id ORDER BY sum(T3.minor) DESC LIMIT 3
    ('bracket', 4251588)
    ('shaft', 4201223)
    ('bushing', 1966206)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 11. manufacturing/mfg-006 en/1

ловушка: the shift belongs to the line, not to the defect; two joins to reach it
вопрос:  Split the defects by whether the line runs days or nights.

эталон:
    SELECT s.title AS shift, COUNT(*) AS defects FROM defect d JOIN mov m ON m.id = d.mov_id JOIN line l ON l.id = m.line_id JOIN shift_ref s ON s.cd = l.shift_cd GROUP BY s.title ORDER BY defects DESC, s.title
    ('night', 185)
    ('day', 135)

ответ модели:
    SELECT T2.title , count(*) FROM mov AS T1 JOIN line AS T2 ON T1.line_id = T2.id JOIN defect AS T3 ON T1.id = T3.mov_id GROUP BY T2.shift_cd
    ('Assembly A', 135)
    ('Assembly B', 185)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 12. manufacturing/mfg-007 en/0

ловушка: DISTINCT part, not a movement count
вопрос:  How many distinct parts are measured in each unit?

эталон:
    SELECT u.title AS unit, COUNT(DISTINCT m.part_id) AS parts FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd GROUP BY u.title ORDER BY parts DESC, u.title
    ('kilogram', 6)
    ('piece', 6)
    ('tonne', 6)

ответ модели:
    SELECT unit_cd , count(DISTINCT part_id) FROM mov GROUP BY unit_cd
    (1, 6)
    (2, 6)
    (3, 6)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 13. manufacturing/mfg-008 en/0

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
    SELECT T1.title FROM part AS T1 JOIN defect AS T2 ON T1.id = T2.part_id GROUP BY T1.id HAVING count(*) > 10
    ОШИБКА: OperationalError: no such column: T2.part_id

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 14. medicine/med-001 en/0

ловушка: sex is a code, needs the lookup join
вопрос:  How many patients are there of each sex?

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

## 15. medicine/med-003 en/0

ловушка: admission date is split across the legacy pair dt_adm/admitted_at
вопрос:  How many admissions happened in the first quarter of 2026?

эталон:
    SELECT COUNT(*) AS n FROM enc WHERE COALESCE(dt_adm, admitted_at) >= '2026-01-01' AND COALESCE(dt_adm, admitted_at) < '2026-04-01'
    (148,)

ответ модели:
    SELECT count(*) FROM enc WHERE dt_adm >= "2026-01-01" AND dt_adm < "2026-04-01"
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 16. medicine/med-003 en/1

ловушка: admission date is split across the legacy pair dt_adm/admitted_at
вопрос:  Count the encounters admitted between January and March 2026 inclusive.

эталон:
    SELECT COUNT(*) AS n FROM enc WHERE COALESCE(dt_adm, admitted_at) >= '2026-01-01' AND COALESCE(dt_adm, admitted_at) < '2026-04-01'
    (148,)

ответ модели:
    SELECT count(*) FROM enc WHERE dt_adm >= "2026-01-01" AND dt_adm <= "2026-03-31"
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

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
    SELECT full_name FROM pat EXCEPT SELECT T1.full_name FROM pat AS T1 JOIN enc AS T2 ON T1.id = T2.pat_id
    ('Artem Novak',)
    ('Daniel Reiner',)
    ('Igor Petran',)
    ('Pavel Reiner',)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 18. medicine/med-005 en/1

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  List the patients who have never been admitted.

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
    SELECT full_name FROM pat EXCEPT SELECT T1.full_name FROM pat AS T1 JOIN enc AS T2 ON T1.id = T2.pat_id
    ('Artem Novak',)
    ('Daniel Reiner',)
    ('Igor Petran',)
    ('Pavel Reiner',)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 19. medicine/med-007 en/1

ловушка: DISTINCT patient, not encounter count
вопрос:  Per department, count the unique patients treated there.

эталон:
    SELECT d.dept, COUNT(DISTINCT e.pat_id) AS patients FROM enc e JOIN doc d ON d.id = e.doc_id GROUP BY d.dept ORDER BY patients DESC, d.dept
    ('cardiology', 214)
    ('surgery', 179)
    ('endocrinology', 141)
    ('oncology', 111)
    ('neurology', 58)

ответ модели:
    SELECT dept , count(DISTINCT id) FROM enc GROUP BY dept
    ОШИБКА: OperationalError: no such column: dept

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 20. medicine/med-008 en/0

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
    SELECT T1.full_name FROM pat AS T1 JOIN enc AS T2 ON T1.id = T2.pat_id GROUP BY T1.id HAVING count(*) > 2
    ('Mark Reiner',)
    ('Timur Varga',)
    ('Pavel Marek',)
    ('Igor Marek',)
    ('Mark Bauer',)
    ('Pavel Marek',)
    ('Artem Kovach',)
    ('Timur Almeida',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен
