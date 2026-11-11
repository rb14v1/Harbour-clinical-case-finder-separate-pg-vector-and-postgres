# Runbook: PostgreSQL database restore

This runbook covers restoring the application database for `clinc_similar_har`.

## Backup configuration (source of truth: `infra/main.tf`)

| Setting | Value |
| --- | --- |
| Server | `psql-clinical-case` (Azure Database for PostgreSQL Flexible Server, v16) |
| Resource group | `clinical-case` |
| Primary region | `uksouth` |
| Automated backups | Enabled (Azure-managed, daily snapshot + continuous WAL archiving) |
| Retention | 35 days (`backup_retention_days = 35`) |
| Geo-redundant backup | Enabled (`geo_redundant_backup_enabled = true`); backups replicated to the paired region `ukwest` |
| Point-in-time recovery | Supported for any point within the 35-day retention window |

Backups are managed entirely by Azure; there is no in-repo backup job to run or monitor.
Do **not** reduce `backup_retention_days` below 30 or disable `geo_redundant_backup_enabled`
in `infra/main.tf` — doing so breaks the `rel.backup_configured` requirement. Note that the
geo-redundant setting can only be chosen at server creation time; changing it forces a new server.

## Important behaviour to know before restoring

- A restore **always creates a new server**. It never overwrites `psql-clinical-case` in place.
- The restored server does not inherit firewall/private-endpoint/private-DNS configuration.
  Networking must be recreated (or the app pointed at the new server) after restore.
- The admin login (`psqladmin`) and its password are carried over from the source server at the
  time of the restore point. The current password is the Terraform-managed
  `random_password.postgresql_admin` value.
- The restored server is **not** managed by Terraform until it is imported or the state is
  updated. Record any manual steps in the incident ticket.

## Prerequisites

- Azure CLI (`az`) logged in with Contributor (or higher) on resource group `clinical-case`.
- `psql` client available on a host with network access to the private endpoint subnet
  (the server has `public_network_access_enabled = false`).
- Agreed target restore time (UTC) from the incident lead.

## Procedure A — Point-in-time restore (same region)

Use this for logical corruption, bad migrations, accidental deletes, etc.

1. Choose the restore point (UTC, ISO-8601) — must be within the last 35 days and not in the future.
   Confirm the earliest restore point:

   ```bash
   az postgres flexible-server show \
     --resource-group clinical-case \
     --name psql-clinical-case \
     --query "backup.earliestRestoreDate"
   ```

2. Restore to a new server:

   ```bash
   az postgres flexible-server restore \
     --resource-group clinical-case \
     --name psql-clinical-case-restore-<yyyymmddhhmm> \
     --source-server psql-clinical-case \
     --restore-time "<YYYY-MM-DDTHH:MM:SSZ>"
   ```

   (Portal alternative: server `psql-clinical-case` → **Overview** → **Restore** →
   *Select a custom restore point*.)

3. Wait for provisioning to complete (`az postgres flexible-server show ... --query state` returns
   `Ready`).

4. Recreate private networking for the new server (private endpoint into `var.subnet_id` and a
   record in the `privatelink.postgres.database.azure.com` zone in the hub resource group), mirroring
   `azurerm_private_endpoint.postgresql_pe` in `infra/main.tf`.

5. Verify the data (see **Verification** below).

6. Cut over: either
   - point the backend's database connection settings at the restored server and restart the
     `backend-api` Container App, **or**
   - `pg_dump` the required tables/rows from the restored server and load them into the primary.

7. Once stable, decide whether to keep the restored server as the new primary (and bring it under
   Terraform via `terraform import`) or delete it.

## Procedure B — Geo-restore (regional outage of `uksouth`)

Use this only when the primary region is unavailable.

1. Restore from the geo-redundant backup into the paired region:

   ```bash
   az postgres flexible-server geo-restore \
     --resource-group clinical-case \
     --name psql-clinical-case-geo-<yyyymmddhhmm> \
     --source-server /subscriptions/<subscription-id>/resourceGroups/clinical-case/providers/Microsoft.DBforPostgreSQL/flexibleServers/psql-clinical-case \
     --location ukwest
   ```

   Geo-restore recovers to the latest available geo-replicated backup (RPO is typically up to
   1 hour); a custom restore time cannot be chosen.

2. Provision networking in `ukwest` (VNet/subnet, private endpoint, private DNS link) and redeploy
   the `backend-api` Container App so that it can reach the restored server.

3. Verify the data (see **Verification**) and cut the application over.

## Verification

Run against the restored server before cutover:

```bash
psql "host=<restored-host> port=5432 dbname=<db-name> user=psqladmin sslmode=require" <<'SQL'
SELECT now();
SELECT count(*) FROM django_migrations;
SELECT app, name FROM django_migrations ORDER BY id DESC LIMIT 5;
SQL
```

- The latest migrations match the version currently deployed.
- Row counts for key tables (users, patients, encounters) are plausible for the chosen restore point.
- Spot-check a record known to exist at the restore point.
- After cutover, the backend starts cleanly and a login + patient lookup succeed.

## Restore test log

A restore test (Procedure A, followed by Verification) must be performed and recorded here
**before go-live**, and repeated at least annually or after any change to the backup
configuration. Delete the restored test server afterwards.

| Date (UTC) | Performed by | Procedure | Restore point used | Time to restore | Verification result | Notes / ticket |
| --- | --- | --- | --- | --- | --- | --- |
| _pending — to be completed before go-live_ | | A (PITR) | | | | |
