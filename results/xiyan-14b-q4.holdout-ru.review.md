# Ручной разбор провалов: xiyan-14b-q4.holdout-ru.jsonl

Провалов всего: 66 из 96.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank-004 ru/1

ловушка: the category name lives in mcc_ref, the code alone is not an answer
вопрос:  Назови тройку самых частых категорий трат и число операций в каждой.

эталон:
    SELECT m.title, COUNT(*) AS n FROM txn t JOIN mcc_ref m ON m.code = t.mcc GROUP BY m.title ORDER BY n DESC, m.title LIMIT 3
    ('cash withdrawal', 340)
    ('electronics stores', 312)
    ('restaurants', 302)

ответ модели:
    SELECT T2.title, COUNT(*) AS num_operations FROM txn AS T1 JOIN dir_ref AS T2 ON T1.dir_cd = T2.cd GROUP BY T2.title ORDER BY num_operations DESC LIMIT 3
    ('debit', 1612)
    ('credit', 788)

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

## 3. banking/bank-007 ru/0

ловушка: DISTINCT customer, not account count; 'active' is status_cd = 1, and residency is a second coded column
вопрос:  Сколько разных клиентов держат действующий счёт, в разрезе резидентства?

эталон:
    SELECT r.title AS residency, COUNT(DISTINCT a.cust_id) AS customers FROM acct a JOIN cust c ON c.id = a.cust_id JOIN resid_ref r ON r.cd = c.resid_cd WHERE a.status_cd = 1 GROUP BY r.title ORDER BY customers DESC, r.title
    ('resident', 189)
    ('non-resident', 34)

ответ модели:
    SELECT T2.resid_cd , count(DISTINCT T1.cust_id) FROM acct AS T1 JOIN cust AS T2 ON T1.cust_id = T2.id WHERE T1.status_cd = 'A' GROUP BY T2.resid_cd
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 4. hr/hr-002 ru/0

ловушка: 'working' is status_cd = 1, not left_at IS NULL; somebody on unpaid leave has no leaving date and is not working
вопрос:  Сколько человек работает сейчас?

эталон:
    SELECT COUNT(*) AS n FROM emp WHERE status_cd = 1
    (186,)

ответ модели:
    SELECT count(*) FROM emp WHERE status_cd = 'A'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

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
    SELECT amount_minor FROM pay_hist WHERE from_dt = (SELECT max(from_dt) FROM pay_hist WHERE emp_id = 1) ORDER BY amount_minor DESC LIMIT 5
    (262700,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 6. hr/hr-004 ru/1

ловушка: department name lives in dept; status is a code
вопрос:  По каждому подразделению посчитай сотрудников, которые сейчас работают.

эталон:
    SELECT d.title, COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 GROUP BY d.title ORDER BY n DESC, d.title
    ('Support', 35)
    ('Operations', 34)
    ('Engineering', 32)
    ('Data', 31)
    ('Finance', 28)
    ('Platform', 26)

ответ модели:
    SELECT T2.title , count(*) FROM emp AS T1 JOIN dept AS T2 ON T1.dept_id = T2.id WHERE T1.status_cd = 'A' GROUP BY T2.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 7. hr/hr-005 ru/1

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Перечисли людей, которым ни разу не заводили строку оплаты.

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
    SELECT full_name FROM emp EXCEPT SELECT T1.full_name FROM emp AS T1 JOIN pay_hist AS T2 ON T1.id = T2.emp_id
    ('Anna Petran',)
    ('Artem Almeida',)
    ('Artem Linde',)
    ('Elena Kristof',)
    ('Elena Petran',)
    ('Igor Benali',)
    ('Igor Kovach',)
    ('Igor Marek',)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 8. hr/hr-007 ru/1

ловушка: kind is a code; SUM over days, not a row count
вопрос:  По каждому виду отсутствия сложи количество дней.

эталон:
    SELECT k.title AS kind, SUM(a.days) AS days FROM absence a JOIN absence_kind_ref k ON k.cd = a.kind_cd GROUP BY k.title ORDER BY days DESC, k.title
    ('annual leave', 2697)
    ('sick', 1103)
    ('training', 706)

ответ модели:
    SELECT kind_cd , sum(days) FROM absence GROUP BY kind_cd
    (1, 2697)
    (2, 1103)
    (3, 706)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 9. logistics/log-002 ru/1

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
    SELECT T2.org_cd, T2.dst_cd, COUNT(*) FROM shp AS T1 JOIN inc AS T2 ON T1.id = T2.shp_id GROUP BY T2.org_cd, T2.dst_cd ORDER BY COUNT(*) DESC LIMIT 5
    ОШИБКА: OperationalError: no such column: T2.org_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 10. logistics/log-005 ru/0

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  По каким отправкам не было ни одного происшествия?

эталон:
    SELECT s.id FROM shp s WHERE NOT EXISTS (SELECT 1 FROM inc i WHERE i.shp_id = s.id) ORDER BY s.id
    (2,)
    (7,)
    (8,)
    (19,)
    (22,)
    (23,)
    (26,)
    (33,)
    ... и ещё строки (показаны первые 8)

ответ модели:
    SELECT COUNT(*) FROM shp WHERE id NOT IN ( SELECT shp_id FROM inc )
    (553,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 11. logistics/log-006 ru/0

ловушка: 'delivered' is status_cd = 2, not delivered_at IS NOT NULL; a lost shipment can carry a delivery attempt date, so the two disagree
вопрос:  Сколько отправок доставлено?

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 2
    (503,)

ответ модели:
    SELECT count(*) FROM shp WHERE status_cd = "D"
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 12. logistics/log-006 ru/1

ловушка: 'delivered' is status_cd = 2, not delivered_at IS NOT NULL; a lost shipment can carry a delivery attempt date, so the two disagree
вопрос:  Посчитай отправки, которые сейчас находятся в состоянии «доставлено».

эталон:
    SELECT COUNT(*) AS n FROM shp WHERE status_cd = 2
    (503,)

ответ модели:
    SELECT count(*) FROM status_ref AS T1 JOIN shp AS T2 ON T1.cd = T2.status_cd WHERE T1.title = "доставлено"
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 13. manufacturing/mfg-002 ru/0

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Сколько всего ушло в брак в пересчёте на базовую единицу?

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(T2.qty * T1.to_base) FROM unit_ref AS T1 INNER JOIN mov AS T2 ON T1.cd = T2.unit_cd INNER JOIN defect AS T3 ON T2.id = T3.mov_id WHERE T3.grade_cd = '1'
    (93650.0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 14. medicine/med-001 ru/0

ловушка: sex is a code, needs the lookup join
вопрос:  Сколько пациентов каждого пола?

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

## 15. medicine/med-001 ru/1

ловушка: sex is a code, needs the lookup join
вопрос:  Разбей пациентов по полу и покажи количество в каждой группе.

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

## 16. medicine/med-003 ru/0

ловушка: admission date is split across the legacy pair dt_adm/admitted_at
вопрос:  Сколько госпитализаций было в первом квартале 2026 года?

эталон:
    SELECT COUNT(*) AS n FROM enc WHERE COALESCE(dt_adm, admitted_at) >= '2026-01-01' AND COALESCE(dt_adm, admitted_at) < '2026-04-01'
    (148,)

ответ модели:
    SELECT COUNT(*) FROM enc WHERE dt_adm >= '2026-01-01' AND dt_adm < '2026-04-01'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 17. public_services/gov-001 ru/1

ловушка: the region belongs to the office, not to the case; two joins to reach it
вопрос:  Разбей дела по регионам и покажи количество в каждом.

эталон:
    SELECT r.title AS region, COUNT(*) AS n FROM case_rec c JOIN office o ON o.id = c.office_id JOIN region_ref r ON r.cd = o.region_cd GROUP BY r.title ORDER BY n DESC, r.title
    ('Northport', 328)
    ('Marden', 158)
    ('Eastvale', 147)
    ('Thorne', 127)

ответ модели:
    SELECT T2.region_cd , count(*) FROM case_rec AS T1 JOIN office AS T2 ON T1.office_id = T2.id GROUP BY T2.region_cd
    (1, 328)
    (2, 147)
    (3, 158)
    (4, 127)

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
    SELECT count(*) FROM CASE_REC WHERE dt_sub >= "2026-04-01" AND dt_sub < "2026-07-01"
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 19. public_services/gov-006 ru/1

ловушка: result_cd is NULL for a stage still open, and NULL is not a code; an inner join is correct here, which is the opposite of gov-005
вопрос:  Для этапов, у которых есть результат, разбей их по тому, какой он.

эталон:
    SELECT r.title AS result, COUNT(*) AS n FROM stage s JOIN result_ref r ON r.cd = s.result_cd GROUP BY r.title ORDER BY n DESC, r.title
    ('approved', 743)
    ('refused', 278)
    ('withdrawn', 122)

ответ модели:
    SELECT T2.result_cd, COUNT(*) FROM stage AS T1 JOIN result_ref AS T2 ON T1.result_cd = T2.cd WHERE T1.result_cd IS NOT NULL GROUP BY T2.result_cd
    ОШИБКА: OperationalError: no such column: T2.result_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 20. public_services/gov-008 ru/0

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
    SELECT T1.full_name FROM applicant AS T1 JOIN case_rec AS T2 ON T1.id = T2.applicant_id GROUP BY T1.id HAVING COUNT(T2.id) > 2
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
