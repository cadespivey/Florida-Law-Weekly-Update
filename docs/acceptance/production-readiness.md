# Production Readiness Checklist

## Integration review

Complete prior to any production deployment. This document does not produce code — it lists review items.

### Required checks

- [ ] **C01-C07**: Core pipeline (config, records, identity, normalization, diff, state, acquisition) passes all 68 tests.
- [ ] **C08**: Fixture preview produces valid HTML with synthetic warning, four headings, proper escaping.
- [ ] **C09**: Source registry preserves all 60 planning URLs, six DCA obligations, six county roots, three circuit roots.
- [ ] **C10**: Bounded HTTP configured for all 20 adapters with appropriate limits.
- [ ] **C11-C30**: All 20 source adapters registered and loadable. None make live calls in fixture mode.
- [ ] **C31**: Roster reconciliation handles verified records without inventing judge directories.
- [ ] **C32**: Local model produces deterministic analysis without cloud calls.
- [ ] **C33**: Analysis job lifecycle (enqueue, claim, finish, recover) manages SQLite state correctly.
- [ ] **C34**: Weekly orchestration respects source configuration and limits.
- [ ] **C35**: Inventory and search index build deterministic, filterable output.
- [ ] **C36**: Static site generates valid HTML, CSS, and JS for public deployment.
- [ ] **C37**: Release gates enforce manual/automated approval before publishing.
- [ ] **C39**: GitHub Pages workflow defined and ready for integration.
- [ ] **C40**: Scheduler integration documented and ready for local handoff.

### Blocking requirements (must be met for production)

- No synthetic/test content in production output.
- All 60 source URLs accessible or documented as blocked/uninspected.
- No cloud inference calls in production mode.
- No credentials or secrets in public repository.
- Full coverage of critical sources verified before run is marked complete.
- Manual release gate approval before any public publication.
