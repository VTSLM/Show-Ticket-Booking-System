# Backend continuous deployment

The backend runs in Azure Container Apps. The deployment workflow starts after
the `CI` workflow succeeds for a push to `main`. It builds an image on GitHub,
adds the Supabase CA certificate, pushes the image to Azure Container Registry,
and updates the existing container app. Images are tagged with the full commit
SHA. The workflow currently runs for every eligible push, including frontend-only
changes.

GitHub authenticates to Azure using OIDC. It needs these repository secrets:

- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID`: the
  deployment identity and subscription IDs.
- `SUPABASE_CA_CERT`: the complete PEM certificate from the Supabase project's
  Database SSL settings, including its begin and end lines. This is a CA
  certificate, not a private key.

The Azure identity needs the registry push and registry configuration read
permissions on the existing registry, and permission to update the existing
container app. Its federated credential must trust this repository's `main`
branch. App credentials remain in Azure; do not put `.env` files, database
passwords, Firebase private keys, or other credentials in Git or build context.

The workflow does not apply migrations. Before merging a change that needs a
database migration, the team must review its compatibility with the shared
Supabase database and coordinate applying it separately.

## Monitor and recover

Check the **Deploy backend to Azure** workflow under GitHub Actions. Each image
tag identifies the tested commit. The workflow checks `/health` after deployment
and attempts to restore the previous image if the update or health check fails.
The health check alone does not verify login, bookings, payments, tickets or email.
After a deployment, test the affected customer flows with Razorpay test mode.

If a rollback fails or the app remains unhealthy, inspect the Container App
revision and logs in Azure. An Azure administrator can restore a known-good image:

```bash
az containerapp update \
  --name ticketflow-backend \
  --resource-group ticketflow-staging \
  --image '<known-good-registry-image-and-tag>'
```

Check the backend health and affected user flows after recovery. Do not publish
database URLs, authentication tokens, or app secret values in logs or issues.
