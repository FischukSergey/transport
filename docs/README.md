# Документация спринтов

Источник истины по системе: [`../концепция.md`](../концепция.md), [`../архитектура.md`](../архитектура.md), [`../функционал.md`](../функционал.md).

Каждый спринт — отдельный коммит или пачка связанных коммитов, не весь проект разом. **Sprint 1 закрыт. Sprint 2 закрыт.** Sprint 3 не начат.

HTTP API нет. Файл `contract-sprint-N.md` занимает место `api-sprint-N.md` из соседнего проекта: это контракт входа и выхода спринта. Следующий спринт не меняет его молча.

| Спринт | Тема | План | Контракт | Чеклист | Ограничения |
|---|---|---|---|---|---|
| 1 | Каркас | [plan](sprint-1-plan.md) | [contract](contract-sprint-1.md) | [checklist](sprint-1-checklist.md) | [limitations](known-limitations-sprint-1.md) |
| 2 | Стоимость месяца | [plan](sprint-2-plan.md) | [contract](contract-sprint-2.md) | [checklist](sprint-2-checklist.md) | [limitations](known-limitations-sprint-2.md) |
| 3 | Смена группы | [plan](sprint-3-plan.md) | [contract](contract-sprint-3.md) | [checklist](sprint-3-checklist.md) | [limitations](known-limitations-sprint-3.md) |
| 4 | База и справочники | [plan](sprint-4-plan.md) | [contract](contract-sprint-4.md) | [checklist](sprint-4-checklist.md) | [limitations](known-limitations-sprint-4.md) |
| 5 | Импорт | [plan](sprint-5-plan.md) | [contract](contract-sprint-5.md) | [checklist](sprint-5-checklist.md) | [limitations](known-limitations-sprint-5.md) |
| 6 | Закрытие месяца | [plan](sprint-6-plan.md) | [contract](contract-sprint-6.md) | [checklist](sprint-6-checklist.md) | [limitations](known-limitations-sprint-6.md) |
| 7 | План-факт и статистика | [plan](sprint-7-plan.md) | [contract](contract-sprint-7.md) | [checklist](sprint-7-checklist.md) | [limitations](known-limitations-sprint-7.md) |
| 8 | Качество данных | [plan](sprint-8-plan.md) | [contract](contract-sprint-8.md) | [checklist](sprint-8-checklist.md) | [limitations](known-limitations-sprint-8.md) |
| 9 | Сборка Windows | [plan](sprint-9-plan.md) | [contract](contract-sprint-9.md) | [checklist](sprint-9-checklist.md) | [limitations](known-limitations-sprint-9.md) |

Порядок из концепции собирается так:

1. Движок и тесты методики — спринты 2 и 3, после каркаса.
2. База и импорт — спринты 4 и 5.
3. Расчёт и план-факт в интерфейсе — спринты 6 и 7.
4. Аномалии и сборка exe — спринты 8 и 9.

Прогноз до конца года в эти спринты не входит. Для него нужны сезонность, прогноз погоды и история аналогичных периодов прошлых лет.
