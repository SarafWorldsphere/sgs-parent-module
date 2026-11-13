# Parent SaaS test deployment fix

The Parent frontend calls `/api/parent`; the backend on port 4107 registers
unprefixed paths. Replace the existing Nginx location with the supplied snippet
so its trailing slash removes `/api/parent/` before forwarding. Keep the shared
SGS/SSS server's Host headers and all unrelated routes. Back up the site, validate
with `nginx -t`, then reload only after validation succeeds.

`UsersMaster` and `ClassMaster` no longer map legacy `school_id` columns, which do
not exist in the canonical SaaS tables. School isolation still uses the existing
tenant-kit middleware, transaction-bound RLS and parent ownership checks. No
database columns or policies are added or removed. Restart only
`demo-parent-api` after deploying the reviewed backend source.

The tenant-kit dependency is pinned to the commit already verified on the test
server. Do not update it to a schema-incompatible floating version during deploy.
Preserve backend `.env`, SSO/JWT secrets and the login portal's matching shared
secret; none belong in Git. Frontend `NEXT_PUBLIC_API_URL` remains `/api/parent`.

Verified on SGS test: email/phone SSO, identity, linked-child list, dashboard and
notifications. Missing-token `/auth/me` still returns 401. Student/Headmaster
health checks remain successful. Actual browser OTP entry is verified by the
operator, not by these API checks. No frontend rebuild is needed for this fix.

Local ORM regression tests use `PARENT_SCHEMA_TEST_DATABASE_URL` pointing only to
a disposable local `saraswati_sample` with the canonical kit schema. Run
`python -m unittest discover -s backend/tests -p test_saas_models_postgres.py -v`
from the repo root, with a local `DATABASE_URL` configured for model imports.
Queries are read-only. Account creation/child mapping performed separately with
user approval is tenant data, not a migration or hardcoded test account in Git.
