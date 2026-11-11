# Runbook: restoring the Postgres database

Applies to the managed Postgres server `psql-clinical-case-har` (Azure
Database for PostgreSQL Flexible Server), provisioned by
`infra/terraform/postgres.tf`.

## Backup configuration

| Setting | Value | Where |
|---|---|---|
| Automated backups | Daily full backups plus continuous WAL backups (Azure managed) | built in to Flexible Server |
| Retention | 30 days (`backup_retention_days`, validated as 30–35) | `infra/terraform/postgres.tf` |
| Point-in-time recovery | Any point inside the 30-day retention window | built in to Flexible Server |
| Off-region copy | Geo-redundant backup storage in the Azure paired region (`geo_redundant_backup_enabled = true`) | `infra/terraform/postgres.tf` |

Note: `geo_redundant_backup_enabled` can only be set when the server is
created. If you change it, Terraform will replace the server.

Check the live settings:

```sh
az postgres flexible-server show \
  --resource-group rg-clinical-case-har \
  --name psql-clinical-case-har \
  --query "{retention:backup.backupRetentionDays, geo:backup.geoRedundantBackup, earliest:backup.earliestRestoreDate}"
```

## Scope: Postgres and Qdrant

Postgres is the source of truth for all relational data (`User`, `Patient`,
`Encounter`). Qdrant holds only embeddings derived from Postgres, so this
runbook does not restore Qdrant. After any Postgres restore, rebuild Qdrant
from the restored data (step 5).

## Procedure A: point-in-time restore (same region)

Use this for accidental deletes, a bad migration, or data corruption.

1. **Choose the restore time.** Pick a UTC timestamp just before the
   incident. It must be later than `earliestRestoreDate` (see above).
2. **Restore to a new server.** PITR always creates a new server and
   leaves the source untouched:

   ```sh
   az postgres flexible-server restore \
     --resource-group rg-clinical-case-har \
     --name psql-clinical-case-har-restore \
     --source-server psql-clinical-case-har \
     --restore-time "YYYY-MM-DDTHH:MM:SSZ"
   ```

3. **Check the restored data.** Connect to the new server and confirm the
   expected rows are there, for example:

   ```sh
   psql "host=psql-clinical-case-har-restore.postgres.database.azure.com dbname=clinical_case_finder user=<admin> sslmode=require" \
     -c "select count(*) from encounters_encounter;"
   ```

4. **Point the backend at the restored server.** Set `POSTGRES_HOST` (and
   `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` /
   `POSTGRES_PORT` if they changed) in the backend environment to the
   restored server's FQDN, then restart the backend. Update
   `postgres_server_name` in Terraform and bring the restored server
   under management (`terraform import`) so state matches reality.
5. **Rebuild Qdrant from Postgres:**

   ```sh
   python manage.py sync_vectors
   ```

6. **Run smoke checks.** Log in, list encounters, and run "Find similar
   cases" on one encounter.
7. **Clean up.** Once the restored server is confirmed as the new
   primary, check that it has the same backup settings (30-day retention,
   geo-redundant). Then decommission the old server.

## Procedure B: geo-restore (primary region lost)

Use this when the primary region is unavailable. It restores from the
geo-redundant backup copy in the paired region. The recovery point is
the latest geo-replicated backup, which can lag the primary.

```sh
az postgres flexible-server geo-restore \
  --resource-group rg-clinical-case-har \
  --name psql-clinical-case-har-geo \
  --source-server <full resource ID of psql-clinical-case-har> \
  --location <paired region>
```

Then follow steps 3–7 of Procedure A.

## Restore test (required before go-live, then at least yearly)

1. Run Procedure A against production (or a pre-production server with
   the same configuration). Use a restore time of about 1 hour ago and
   restore into a temporary server name.
2. Record the following in the table below: the timestamp, how long the
   restore took (RTO), the gap between the restore point and the incident
   time (RPO), and the row-count checks.
3. Delete the temporary server.

| Date (UTC) | Performed by | Procedure | Restore point | Duration | Result / notes |
|---|---|---|---|---|---|
| _pending – must be completed before go-live_ | | | | | |
