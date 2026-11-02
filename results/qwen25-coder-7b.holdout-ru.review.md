# Ручной разбор провалов: qwen25-coder-7b.holdout-ru.jsonl

Провалов всего: 57 из 96.
В выборке: 20, зерно 0, отбор детерминированный.
Порог протокола: не меньше 20 (или все, если их меньше).

В каждом блоке заполните строку «вердикт» одним из значений:
  model      модель ответила неверно
  evaluator  ложное срабатывание проверяльщика: ответ по сути верен
  unsure     не разобрался, нужен ещё один взгляд

Пустой вердикт останавливает подсчёт. «unsure» это допустимый ответ,
он попадёт в публикуемую долю отдельной категорией, а не растворится.


## 1. banking/bank-002 ru/1

ловушка: direction lives in dir_cd, not in the sign of amt_cents; amounts are minor units and must be divided by 100
вопрос:  Сложи приходы, вычти расходы и дай результат в основных единицах, а не в копейках.

эталон:
    SELECT SUM(CASE WHEN dir_cd = 2 THEN amt_cents ELSE -amt_cents END) / 100.0 AS net FROM txn
    (-189905.58,)

ответ модели:
    SELECT 
    SUM(CASE WHEN dir_cd = 'C' THEN amt_cents / 100 ELSE 0 END) - 
    SUM(CASE WHEN dir_cd = 'D' THEN amt_cents / 100 ELSE 0 END) AS net_amount
FROM 
    txn
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 2. banking/bank-006 ru/0

ловушка: rate_bp is basis points, so the answer is a hundredth of the stored number; an open loan is closed_at IS NULL, there is no status column here
вопрос:  Какая средняя ставка по непогашенным кредитам в процентах?

эталон:
    SELECT AVG(rate_bp) / 100.0 AS avg_rate_pct FROM loan WHERE closed_at IS NULL
    (11.487196261682243,)

ответ модели:
    SELECT AVG(rate_bp) AS avg_interest_rate
FROM loan
WHERE status_cd != 'PAID'
    ОШИБКА: OperationalError: no such column: status_cd

ошибка исполнения: pred_sql failed to execute

вердикт: model
заметка: запрос не исполнился

## 3. banking/bank-007 ru/0

ловушка: DISTINCT customer, not account count; 'active' is status_cd = 1, and residency is a second coded column
вопрос:  Сколько разных клиентов держат действующий счёт, в разрезе резидентства?

эталон:
    SELECT r.title AS residency, COUNT(DISTINCT a.cust_id) AS customers FROM acct a JOIN cust c ON c.id = a.cust_id JOIN resid_ref r ON r.cd = c.resid_cd WHERE a.status_cd = 1 GROUP BY r.title ORDER BY customers DESC, r.title
    ('resident', 189)
    ('non-resident', 34)

ответ модели:
    SELECT r.title AS resid_title, COUNT(DISTINCT c.id) AS active_customer_count
FROM cust c
JOIN resid_ref r ON c.resid_cd = r.cd
JOIN acct a ON c.id = a.cust_id
JOIN acct_status_ref asr ON a.status_cd = asr.cd
WHERE a.status_cd = 'active'
GROUP BY r.title
    (пусто)

ошибка исполнения: нет

вердикт: model
заметка: пустой ответ там, где эталон даёт строки

## 4. hr/hr-002 ru/1

ловушка: 'working' is status_cd = 1, not left_at IS NULL; somebody on unpaid leave has no leaving date and is not working
вопрос:  Посчитай сотрудников, у которых текущий статус «работает».

эталон:
    SELECT COUNT(*) AS n FROM emp WHERE status_cd = 1
    (186,)

ответ модели:
    SELECT COUNT(*) 
FROM emp 
JOIN emp_status_ref ON emp.status_cd = emp_status_ref.cd 
WHERE emp_status_ref.title = 'работает'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 5. hr/hr-004 ru/0

ловушка: department name lives in dept; status is a code
вопрос:  Сколько работающих в каждом подразделении, по названию подразделения?

эталон:
    SELECT d.title, COUNT(*) AS n FROM emp e JOIN dept d ON d.id = e.dept_id WHERE e.status_cd = 1 GROUP BY d.title ORDER BY n DESC, d.title
    ('Support', 35)
    ('Operations', 34)
    ('Engineering', 32)
    ('Data', 31)
    ('Finance', 28)
    ('Platform', 26)

ответ модели:
    SELECT 
    d.title AS department_title,
    COUNT(e.id) AS employee_count
FROM 
    dept d
JOIN 
    emp e ON d.id = e.dept_id
WHERE 
    e.status_cd = 'A'
GROUP BY 
    d.title
ORDER BY 
    d.title
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
    SELECT emp.id, emp.full_name
FROM emp
LEFT JOIN pay_hist ON emp.id = pay_hist.emp_id
WHERE pay_hist.id IS NULL
    (60, 'Igor Benali')
    (77, 'Anna Almeida')
    (147, 'Irina Linde')
    (184, 'Artem Marek')
    (221, 'Igor Kovach')
    (222, 'Artem Soto')
    (223, 'Irina Benali')
    (224, 'Victor Benali')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен

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
    SELECT e.id, e.full_name
FROM emp e
LEFT JOIN pay_hist ph ON e.id = ph.emp_id
WHERE ph.id IS NULL
    (60, 'Igor Benali')
    (77, 'Anna Almeida')
    (147, 'Irina Linde')
    (184, 'Artem Marek')
    (221, 'Igor Kovach')
    (222, 'Artem Soto')
    (223, 'Irina Benali')
    (224, 'Victor Benali')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен

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
    SELECT 
    org_cd AS origin, 
    dst_cd AS destination, 
    COUNT(*) AS route_count
FROM 
    shp
GROUP BY 
    org_cd, 
    dst_cd
ORDER BY 
    route_count DESC
LIMIT 5
    (7, 5, 21)
    (1, 8, 20)
    (2, 4, 20)
    (3, 4, 18)
    (8, 4, 18)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 9. logistics/log-004 ru/0

ловушка: cost is stored in minor units and must be divided by 100
вопрос:  Сколько стоят все плечи маршрутов вместе, в денежных единицах?

эталон:
    SELECT SUM(cost_cents) / 100.0 AS total_cost FROM leg
    (8579947.13,)

ответ модели:
    SELECT SUM(cost_cents) / 100 AS total_cost
FROM leg
    (8579947,)

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
    SELECT SUM(leg.cost_cents / 100) AS total_cost
FROM leg
    (8579038,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 11. logistics/log-005 ru/1

ловушка: anti-join; an inner join silently returns the opposite set
вопрос:  Перечисли отправки, по которым не зафиксировано ни одного происшествия.

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
    SELECT shp.id, shp.dt_disp
FROM shp
LEFT JOIN inc ON shp.id = inc.shp_id
WHERE inc.id IS NULL
    (2, None)
    (7, None)
    (8, None)
    (19, None)
    (22, None)
    (23, '2025-05-14')
    (26, None)
    (33, None)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен

## 12. manufacturing/mfg-002 ru/0

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Сколько всего ушло в брак в пересчёте на базовую единицу?

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(m.qty * u.to_base) AS total_defect_quantity
FROM mov m
JOIN defect d ON m.id = d.mov_id
JOIN mov_kind_ref mk ON m.kind_cd = mk.cd
JOIN unit_ref u ON m.unit_cd = u.cd
WHERE mk.title = 'Defect'
    (None,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 13. manufacturing/mfg-002 ru/1

ловушка: quantities are in three different units; the factor is in unit_ref; 'scrap' is kind_cd = 3
вопрос:  Сложи забракованное количество, приведя все строки к одной единице.

эталон:
    SELECT SUM(m.qty * u.to_base) AS base_qty FROM mov m JOIN unit_ref u ON u.cd = m.unit_cd WHERE m.kind_cd = 3
    (68444.0,)

ответ модели:
    SELECT SUM(mov.qty * unit_ref.to_base) AS total_defective_quantity
FROM mov
JOIN defect ON mov.id = defect.mov_id
JOIN unit_ref ON mov.unit_cd = unit_ref.cd
WHERE defect.grade_cd IS NOT NULL
    (154137.0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 14. manufacturing/mfg-003 ru/0

ловушка: the date is split across the legacy pair dt_op/recorded_at
вопрос:  Сколько движений приходится на первый квартал 2026 года?

эталон:
    SELECT COUNT(*) AS n FROM mov WHERE COALESCE(dt_op, recorded_at) >= '2026-01-01' AND COALESCE(dt_op, recorded_at) < '2026-04-01'
    (85,)

ответ модели:
    SELECT COUNT(*) 
FROM mov 
WHERE dt_op BETWEEN '2026-01-01' AND '2026-03-31'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 15. manufacturing/mfg-006 ru/1

ловушка: the shift belongs to the line, not to the defect; two joins to reach it
вопрос:  Раздели дефекты по тому, дневная смена на линии или ночная.

эталон:
    SELECT s.title AS shift, COUNT(*) AS defects FROM defect d JOIN mov m ON m.id = d.mov_id JOIN line l ON l.id = m.line_id JOIN shift_ref s ON s.cd = l.shift_cd GROUP BY s.title ORDER BY defects DESC, s.title
    ('night', 185)
    ('day', 135)

ответ модели:
    SELECT 
    grade_ref.title AS grade,
    CASE 
        WHEN shift_ref.title = 'Дневная' THEN 'Дневная смена'
        ELSE 'Ночная смена'
    END AS shift_type
FROM 
    defect
JOIN 
    mov ON defect.mov_id = mov.id
JOIN 
    line ON mov.line_id = line.id
JOIN 
    shift_ref ON line.shift_cd = shift_ref.cd
JOIN 
    grade_ref ON defect.grade_cd = grade_ref.cd
    ('minor', 'Ночная смена')
    ('minor', 'Ночная смена')
    ('major', 'Ночная смена')
    ('minor', 'Ночная смена')
    ('critical', 'Ночная смена')
    ('minor', 'Ночная смена')
    ('major', 'Ночная смена')
    ('major', 'Ночная смена')
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 16. medicine/med-001 ru/0

ловушка: sex is a code, needs the lookup join
вопрос:  Сколько пациентов каждого пола?

эталон:
    SELECT r.title AS sex, COUNT(*) AS n FROM pat p JOIN sex_ref r ON r.cd = p.sex_cd GROUP BY r.title ORDER BY n DESC
    ('female', 201)
    ('male', 199)

ответ модели:
    SELECT sex_cd, COUNT(*) AS patient_count
FROM pat
GROUP BY sex_cd
    (1, 199)
    (2, 201)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 17. medicine/med-006 ru/0

ловушка: route is a code; AVG over days, not SUM
вопрос:  Какая средняя длительность курса для каждого способа введения?

эталон:
    SELECT r.title AS route, AVG(x.days) AS avg_days FROM rx x JOIN route_ref r ON r.cd = x.route_cd GROUP BY r.title ORDER BY avg_days DESC
    ('oral', 15.870523415977962)
    ('topical', 15.564432989690722)
    ('inhalation', 15.211488250652742)
    ('intravenous', 14.887978142076502)

ответ модели:
    SELECT route_ref.title, AVG(enc.discharged - enc.admitted_at) AS avg_duration
FROM enc
JOIN rx ON enc.id = rx.enc_id
JOIN route_ref ON rx.route_cd = route_ref.cd
GROUP BY route_ref.title
    ('inhalation', 0.024752475247524754)
    ('intravenous', 0.029069767441860465)
    ('oral', 0.01744186046511628)
    ('topical', 0.020100502512562814)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 18. medicine/med-008 ru/1

ловушка: HAVING, which RedSQL found models get wrong most often
вопрос:  Покажи пациентов с тремя и более обращениями и число обращений у каждого.

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
    SELECT p.id, p.full_name, COUNT(e.id) AS num_encounters
FROM pat p
JOIN enc e ON p.id = e.pat_id
GROUP BY p.id, p.full_name
HAVING COUNT(e.id) >= 3
    (3, 'Mark Reiner', 3)
    (7, 'Timur Varga', 3)
    (9, 'Pavel Marek', 3)
    (10, 'Igor Marek', 3)
    (11, 'Mark Bauer', 3)
    (17, 'Pavel Marek', 5)
    (19, 'Artem Kovach', 3)
    (22, 'Timur Almeida', 3)
    ... и ещё строки (показаны первые 8)

ошибка исполнения: нет

вердикт: evaluator
заметка: все запрошенные столбцы на месте плюс лишние, ответ по сути верен

## 19. public_services/gov-002 ru/0

ловушка: the deadline is inclusive: closing on the due date is not late; an open case has no closing date and cannot be late yet
вопрос:  Сколько дел закрыто после срока?

эталон:
    SELECT COUNT(*) AS n FROM case_rec WHERE closed_at IS NOT NULL AND closed_at > due_dt
    (160,)

ответ модели:
    SELECT COUNT(*)
FROM case_rec cr
JOIN stage s ON cr.id = s.case_id
JOIN result_ref rr ON s.result_cd = rr.cd
WHERE rr.title = 'Closed After Deadline'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям

## 20. public_services/gov-004 ru/1

ловушка: the submission date is split across the legacy pair dt_sub/submitted_at
вопрос:  Посчитай дела, поданные с апреля по июнь 2026 года включительно.

эталон:
    SELECT COUNT(*) AS n FROM case_rec WHERE COALESCE(dt_sub, submitted_at) >= '2026-04-01' AND COALESCE(dt_sub, submitted_at) < '2026-07-01'
    (124,)

ответ модели:
    SELECT COUNT(*) 
FROM case_rec 
WHERE dt_sub BETWEEN '2026-04-01' AND '2026-06-30'
    (0,)

ошибка исполнения: нет

вердикт: model
заметка: результат расходится с эталоном по значениям
