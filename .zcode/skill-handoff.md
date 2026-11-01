# VoxLab Build — ECC Skill Handoff

You (the build session) have a skill list from before the ECC collection was installed,
so the skills below don't appear in your `/` menu. They are plain markdown files on disk —
**read a skill's SKILL.md with your Read tool before starting the phase it covers, and
follow its guidance** for that phase. Each takes < 1 minute to read.

## Skills for the remaining build phases

| Phase | Skill path (read SKILL.md inside) | Use it for |
|---|---|---|
| Demo agent (agent-examples/customer-support-agent) | `C:\Users\Subha Prasana Parida\.agents\skills\fastapi-patterns\SKILL.md` | App structure, routers, service layer, testing |
| Demo agent / backend polish | `C:\Users\Subha Prasana Parida\.agents\skills\python-patterns\SKILL.md` | Python idioms, error handling patterns |
| pytest suite (backend/tests) | `C:\Users\Subha Prasana Parida\.agents\skills\python-testing\SKILL.md` | Test layout, fixtures, async tests |
| pytest suite | `C:\Users\Subha Prasana Parida\.agents\skills\tdd-workflow\SKILL.md` | Red-green-refactor order for engine tests |
| Backend error paths | `C:\Users\Subha Prasana Parida\.agents\skills\error-handling\SKILL.md` | Consistent error responses, retry policy |
| Frontend scaffold + all pages | `C:\Users\Subha Prasana Parida\.agents\skills\nextjs-turbopack\SKILL.md` | Next.js App Router + Turbopack setup |
| Frontend components/pages | `C:\Users\Subha Prasana Parida\.agents\skills\react-patterns\SKILL.md` | Component structure, hooks, state |
| Frontend styling/layout | `C:\Users\Subha Prasana Parida\.agents\skills\frontend-patterns\SKILL.md` | Layout and UI composition patterns |
| Frontend tests | `C:\Users\Subha Prasana Parida\.agents\skills\react-testing\SKILL.md` | Component + hook testing |
| Docker/compose finalization | `C:\Users\Subha Prasana Parida\.agents\skills\docker-patterns\SKILL.md` | Dockerfile + compose best practices |

## After the build (verification pass)

- `C:\Users\Subha Prasana Parida\.agents\skills\security-review\SKILL.md` — review auth, SSRF guard, credential encryption
- `C:\Users\Subha Prasana Parida\.agents\skills\code-review-and-quality\SKILL.md` — overall quality pass

## Rules

1. Read the SKILL.md **before** the phase starts, not after writing code.
2. Skills are guidance, not mandates — where a skill conflicts with the build plan
   (`.zcode/plans/plan-session_d5b6d814f93663ec4c751f46a3f4685f.md`), the plan wins.
3. Don't copy skill content into code or docs; just apply it.
