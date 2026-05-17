# Lead Bot Stage 1 — Implementation Overview

**Spec:** [`docs/superpowers/specs/2026-05-17-lead-bot-ux-core-design.md`](../specs/2026-05-17-lead-bot-ux-core-design.md)

Этап 1 спека реализуется как цепочка из 9 step-планов. Каждый step производит самодостаточное working software и завершается green-тестами + git-тегом.

## Dependency chain

```
Step 0 (Content Layer)
   │
   ▼
Step 1a — Migration 0003 (category.is_internal)
   │
   ▼
Step 1 (SPA Navigation Foundation)
   │
   ▼
Step 2 (Simple Screens: MAIN_MENU/MY_LEADS/FAQ/SUPPORT)
   │
   ▼
Step 3 (Lead Form FSM on Screen)
   │
   ▼
Step 4 (User Features: repeat, support flow, cancel reason)
   │
   ▼
Step 4a — Migration 0004 (contacted status + close_reason + priority)
   │
   ▼
Step 5 (Admin UI + Management)
   │
   ▼
Step 6 (Refactoring)
   │
   ▼
Step 6a — Migration 0005 (indexes + cascades)
   │
   ▼
Step 7 (Bot Tests)
```

## Step plans

| Step | Plan file | Status | Estimated tasks |
|------|-----------|--------|-----------------|
| 0 | [`2026-05-17-stage-1-step-0-content-layer.md`](2026-05-17-stage-1-step-0-content-layer.md) | Ready | ~14 |
| 1a | TBD — created after Step 0 review | Pending | ~3 |
| 1 | TBD — created after Step 1a review | Pending | ~12 |
| 2 | TBD — created after Step 1 review | Pending | ~15 |
| 3 | TBD — created after Step 2 review | Pending | ~18 |
| 4 | TBD — created after Step 3 review | Pending | ~10 |
| 4a | TBD — created after Step 4 review | Pending | ~4 |
| 5 | TBD — created after Step 4a review | Pending | ~20 |
| 6 | TBD — created after Step 5 review | Pending | ~8 |
| 6a | TBD — created after Step 6 review | Pending | ~2 |
| 7 | TBD — created after Step 6a review | Pending | ~12 |

## Quality gates (после каждого шага)

1. `.venv/bin/pytest -q` — все тесты зелёные.
2. `.venv/bin/ruff check .` — lint зелёный.
3. `.venv/bin/ruff format --check .` — форматирование соответствует.
4. Все task-чекбоксы шага отмечены.
5. Git tag `stage1-step-N` создан.

## Done criteria этапа 1

Из спека:
1. Пользователь ни в одном сценарии не «залипает» в FSM.
2. Каждый экран имеет навигационный футер.
3. Создание заявки в одном root-сообщении (за исключением reply-промптов).
4. «Мои заявки» с пагинацией работает на 50+ заявок.
5. «Повторить заявку», «Связаться с менеджером», FAQ — рабочие.
6. Админ ведёт всю работу через бот.
7. `ADMIN_LEAD_LIST` сортирует по приоритету, `ADMIN_MENU` счётчики корректны.
8. Клиент при отмене и админ при отказе указывают причину.
9. Адаптация под нового клиента без правок кода (только YAML).
10. `pytest` зелёный, bot-тесты покрывают FSM + менеджмент.
11. `ruff check .` зелёный.

## Notes

- Скоуп каждого step-плана включает только задачи, явно описанные в спеке для этого Step. Идеи «а ещё неплохо бы…» отклоняются — выносятся в этап 2.
- Тесты пишутся **до** реализации (TDD). Это требование скилла.
- Каждый Task в каждом step-плане — атомарный коммит. Не группируем несколько тасков в один коммит.
- Git tag после каждого Step: `git tag stage1-step-0-content-layer`, `stage1-step-1a-cat-internal`, и т.д.
