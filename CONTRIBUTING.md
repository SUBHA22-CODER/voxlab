# Contributing to VoxLab

Thank you for contributing to VoxLab! Please follow these guidelines:

## Development Workflow
1. Fork and create a feature branch (`git checkout -b feature/my-feature`).
2. Follow PEP 8 guidelines for Python and TypeScript strict mode for Next.js.
3. Write unit tests in `backend/tests/` for any new engine feature, attack persona, or metric.
4. Verify all tests pass before submitting a pull request:
   ```bash
   cd backend && pytest -q
   cd ../frontend && npm run build
   ```
5. Maintain documentation parity: update `docs/` and `CHANGELOG.md` when introducing new API endpoints or schema modifications.
