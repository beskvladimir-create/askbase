# Ручной разбор провалов: xiyan-7b-q4.holdout-ru.jsonl

Провалов всего: 67 из 96.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank-003 ru/1

ловушка: operation date is split across the legacy pair dt_op/posted_at
вопрос:  Посчитай операции, датированные с апреля по июнь 2026 года включительно.

эталон:
    SELECT COUNT(*) AS n FROM txn WHERE COALESCE(dt_op, posted_at) >= '2026-04-01' AND COALESCE(dt_op, posted_at) < '2026-07-01'
    (410,)

ответ модели:
    SELECT count(*) FROM txn WHERE dt_op BETWEEN '2026-04-01' AND '2026-06-30'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 2. banking/bank-005 ru/0

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  У каких клиентов нет ни одного счёта?

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

## 3. banking/bank-007 ru/1

ловушка: DISTINCT customer, not account count; 'active' is status_cd = 1, and residency is a second coded column
вопрос:  Раздели владельцев действующих счетов на резидентов и нерезидентов, считая каждого клиента один раз.

эталон:
    SELECT r.title AS residency, COUNT(DISTINCT a.cust_id) AS customers FROM acct a JOIN cust c ON c.id = a.cust_id JOIN resid_ref r ON r.cd = c.resid_cd WHERE a.status_cd = 1 GROUP BY r.title ORDER BY customers DESC, r.title
    ('resident', 189)
    ('non-resident', 34)

ответ модели:
    SELECT DISTINCT CASE WHEN T1.resid_cd = 'R' THEN 'Resident' ELSE 'Non-Resident' END AS residency_status FROM cust AS T1 INNER JOIN acct AS T2 ON T1.id = T2.cust_id INNER JOIN acct_status_ref AS T3 ON T2.status_cd = T3.cd WHERE T3.title = 'Open'
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 4. hr/hr-003 ru/0

ловушка: salary is effective-dated; the current one is the latest from_dt per person; amounts are minor units and must be divided by 100
вопрос:  Кто пять самых высокооплачиваемых по действующей сейчас зарплате?

эталон:
    SELECT e.full_name, p.amount_minor / 100.0 AS pay FROM emp e JOIN pay_hist p ON p.emp_id = e.id WHERE p.from_dt = ( SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id ) ORDER BY pay DESC, e.full_name LIMIT 5
    ('Irina Oduya', 10996.0)
    ('Victor Kristof', 10988.0)
    ('Artem Oduya', 10948.0)
    ('Daniel Almeida', 10890.0)
    ('Victor Marek', 10856.0)

ответ модели:
    SELECT T1.full_name FROM emp AS T1 INNER JOIN pay_hist AS T2 ON T1.id = T2.emp_id WHERE T2.from_dt = ( SELECT MAX(from_dt) FROM pay_hist WHERE emp_id = T1.id ) ORDER BY T2.amount_minor DESC LIMIT 5
    ('Irina Oduya',)
    ('Victor Kristof',)
    ('Artem Oduya',)
    ('Daniel Almeida',)
    ('Victor Marek',)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 5. hr/hr-003 ru/1

ловушка: salary is effective-dated; the current one is the latest from_dt per person; amounts are minor units and must be divided by 100
вопрос:  Покажи пятёрку по зарплате, которая действует на сегодня, в основных единицах.

эталон:
    SELECT e.full_name, p.amount_minor / 100.0 AS pay FROM emp e JOIN pay_hist p ON p.emp_id = e.id WHERE p.from_dt = ( SELECT MAX(p2.from_dt) FROM pay_hist p2 WHERE p2.emp_id = e.id ) ORDER BY pay DESC, e.full_name LIMIT 5
    ('Irina Oduya', 10996.0)
    ('Victor Kristof', 10988.0)
    ('Artem Oduya', 10948.0)
    ('Daniel Almeida', 10890.0)
    ('Victor Marek', 10856.0)

ответ модели:
    SELECT T1.full_name FROM emp AS T1 INNER JOIN pay_hist AS T2 ON T1.id = T2.emp_id WHERE T2.from_dt = '2018-01-01' ORDER BY T2.amount_minor DESC LIMIT 5
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 6. hr/hr-005 ru/0

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  У каких сотрудников нет ни одной записи о зарплате?

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

## 7. hr/hr-006 ru/1

ловушка: the same table joined twice under two aliases, through mgr_id
вопрос:  Назови пятёрку тех, у кого больше всего людей в прямом подчинении.

эталон:
    SELECT m.full_name AS manager, COUNT(*) AS reports FROM emp e JOIN emp m ON m.id = e.mgr_id GROUP BY m.id, m.full_name ORDER BY reports DESC, m.full_name LIMIT 5
    ('Artem Oduya', 11)
    ('Irina Bauer', 10)
    ('Sofia Linde', 10)
    ('Alina Linde', 9)
    ('Daniel Kovach', 9)

ответ модели:
    SELECT title FROM dept GROUP BY parent_id ORDER BY count(id) DESC LIMIT 5
    ('Operations',)
    ('Platform',)
    ('Support',)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 8. logistics/log-002 ru/1

ловушка: one lookup table joined twice under two aliases; a single join answers about one end of the route and looks correct
вопрос:  Назови пятёрку самых частых маршрутов, указывая откуда ушла отправка и куда она шла.

эталон:
    SELECT o.title AS origin, d.title AS destination, COUNT(*) AS n FROM shp s JOIN loc_ref o ON o.cd = s.org_cd JOIN loc_ref d ON d.cd = s.dst_cd GROUP BY o.title, d.title ORDER BY n DESC, o.title, d.title LIMIT 5
    ('Kesling', 'Thorne', 21)
    ('Eastvale', 'Lowick', 20)
    ('Northport', 'Harrow', 20)
    ('Harrow', 'Lowick', 18)
    ('Marden', 'Lowick', 18)

ответ модели:
    SELECT T1.title AS FROM , T3.title AS TO , COUNT(*) AS num FROM loc_ref AS T1 JOIN shp AS T2 ON T1.cd = T2.org_cd JOIN loc_ref AS T3 ON T3.cd = T2.dst_cd GROUP BY T1.title , T3.title ORDER BY num DESC LIMIT 5
    ОШИБКА: OperationalError: near "FROM": syntax error

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 9. logistics/log-004 ru/0

ловушка: cost is stored in minor units and must be divided by 100
вопрос:  Сколько стоят все плечи маршрутов вместе, в денежных единицах?

эталон:
    SELECT SUM(cost_cents) / 100.0 AS total_cost FROM leg
    (8579947.13,)

ответ модели:
    SELECT sum(cost_cents) FROM leg
    (857994713,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 10. logistics/log-004 ru/1

ловушка: cost is stored in minor units and must be divided by 100
вопрос:  Сложи стоимость всех плеч и дай ответ в основных единицах, а не в копейках.

эталон:
    SELECT SUM(cost_cents) / 100.0 AS total_cost FROM leg
    (8579947.13,)

ответ модели:
    SELECT SUM(cost_cents) / 100 AS total_cost FROM leg
    (8579947,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 11. logistics/log-007 ru/0

ловушка: DISTINCT carrier, not leg count; the destination end of the route, not the origin
вопрос:  Сколько разных перевозчиков обслуживает каждое место назначения?

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
    SELECT dst_cd, COUNT(DISTINCT carr_id) AS distinct_carriers FROM leg GROUP BY dst_cd
    ОШИБКА: OperationalError: no such column: dst_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 12. manufacturing/mfg-002 ru/0

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Сколько всего ушло в брак в пересчёте на базовую единицу?

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(T1.qty * T2.to_base) AS total FROM mov AS T1 INNER JOIN unit_ref AS T2 ON T1.unit_cd = T2.cd INNER JOIN defect AS T3 ON T1.id = T3.mov_id
    (154137.0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 13. medicine/med-001 ru/1

ловушка: sex is a code, needs the lookup join
вопрос:  Разбей пациентов по полу и покажи количество в каждой группе.

эталон:
    SELECT r.title AS sex, COUNT(*) AS n FROM pat p JOIN sex_ref r ON r.cd = p.sex_cd GROUP BY r.title ORDER BY n DESC
    ('female', 201)
    ('male', 199)

ответ модели:
    SELECT sex_cd, count(*) FROM pat GROUP BY sex_cd
    (1, 199)
    (2, 201)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 14. medicine/med-002 ru/0

ловушка: 'discharged' is status_cd = 2, not the discharged column
вопрос:  Какие пять врачей выписали больше всего пациентов?

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

## 15. medicine/med-003 ru/1

ловушка: admission date is split across the legacy pair dt_adm/admitted_at
вопрос:  Посчитай случаи, поступившие с января по март 2026 года включительно.

эталон:
    SELECT COUNT(*) AS n FROM enc WHERE COALESCE(dt_adm, admitted_at) >= '2026-01-01' AND COALESCE(dt_adm, admitted_at) < '2026-04-01'
    (148,)

ответ модели:
    SELECT count(*) FROM enc WHERE strftime('%Y-%m', dt_adm) BETWEEN '2026-01' AND '2026-03'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 16. medicine/med-008 ru/0

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Какие пациенты поступали больше двух раз?

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

## 17. public_services/gov-002 ru/1

ловушка: the deadline is inclusive: closing on the due date is not late; an open case has no closing date and cannot be late yet
вопрос:  Посчитай дела, завершённые с опозданием, то есть позже даты срока, а не в неё.

эталон:
    SELECT COUNT(*) AS n FROM case_rec WHERE closed_at IS NOT NULL AND closed_at > due_dt
    (160,)

ответ модели:
    SELECT count(*) FROM case_rec AS T1 INNER JOIN stage AS T2 ON T1.id = T2.case_id INNER JOIN result_ref AS T3 ON T2.result_cd = T3.cd WHERE T3.title = 'Completed' AND T1.due_dt < T1.closed_at
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 18. public_services/gov-004 ru/0

ловушка: the submission date is split across the legacy pair dt_sub/submitted_at
вопрос:  Сколько дел подано во втором квартале 2026 года?

эталон:
    SELECT COUNT(*) AS n FROM case_rec WHERE COALESCE(dt_sub, submitted_at) >= '2026-04-01' AND COALESCE(dt_sub, submitted_at) < '2026-07-01'
    (124,)

ответ модели:
    SELECT COUNT(*) FROM case_rec WHERE strftime('%Y-%m', dt_sub) = '2026-04' OR strftime('%Y-%m', dt_sub) = '2026-05' OR strftime('%Y-%m', dt_sub) = '2026-06'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 19. public_services/gov-008 ru/0

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Кто подавал больше двух дел?

эталон:
    SELECT a.full_name, COUNT(*) AS cases FROM case_rec c JOIN applicant a ON a.id = c.applicant_id GROUP BY a.id, a.full_name HAVING COUNT(*) > 2 ORDER BY cases DESC, a.full_name
    ('Alina Oduya', 9)
    ('Anna Soto', 9)
    ('Anna Almeida', 8)
    ('Elena Oduya', 8)
    ('Elena Varga', 8)
    ('Mark Kristof', 8)
    ('Timur Linde', 8)
    ('Victor Linde', 8)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT T1.full_name FROM applicant AS T1 INNER JOIN case_rec AS T2 ON T1.id = T2.applicant_id GROUP BY T1.id HAVING COUNT(T2.id) > 2
    ('Anna Soto',)
    ('Elena Oduya',)
    ('Olga Soto',)
    ('Irina Novak',)
    ('Elena Kovach',)
    ('Sofia Reiner',)
    ('Alina Varga',)
    ('Vera Kristof',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: вопрос не просил столбец, который возвращает эталон, ответ по сути верен

## 20. public_services/gov-008 ru/1

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Покажи заявителей с тремя и более делами и число дел у каждого.

эталон:
    SELECT a.full_name, COUNT(*) AS cases FROM case_rec c JOIN applicant a ON a.id = c.applicant_id GROUP BY a.id, a.full_name HAVING COUNT(*) > 2 ORDER BY cases DESC, a.full_name
    ('Alina Oduya', 9)
    ('Anna Soto', 9)
    ('Anna Almeida', 8)
    ('Elena Oduya', 8)
    ('Elena Varga', 8)
    ('Mark Kristof', 8)
    ('Timur Linde', 8)
    ('Victor Linde', 8)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT T1.id , T1.full_name , count(T2.id) FROM applicant AS T1 JOIN case_rec AS T2 ON T1.id = T2.applicant_id GROUP BY T1.id HAVING count(T2.id) >= 3
    (3, 'Anna Soto', 9)
    (4, 'Elena Oduya', 8)
    (6, 'Olga Soto', 3)
    (7, 'Irina Novak', 3)
    (8, 'Elena Kovach', 3)
    (10, 'Sofia Reiner', 5)
    (12, 'Alina Varga', 6)
    (13, 'Vera Kristof', 3)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен
