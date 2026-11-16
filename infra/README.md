# Infrastructure

Infrastructure as code for deploying TicketFlow to **Microsoft Azure** with **Terraform** (`azurerm` provider).

> Status: planned. The Azure deployment is tracked in the Sprint 3 milestone. Nothing here creates resources yet.

## Layout

```text
infra/
└── terraform/
    ├── bootstrap/        # One-time: resource group + storage account for remote state
    ├── modules/          # Reusable building blocks (one folder per concern)
    │   ├── network/
    │   ├── database/     # PostgreSQL
    │   ├── backend/      # FastAPI container hosting
    │   ├── frontend/     # Next.js hosting
    │   ├── secrets/      # Key Vault
    │   └── monitoring/   # Log Analytics, Application Insights
    └── envs/
        ├── staging/      # main.tf, variables.tf, backend.tf, terraform.tfvars.example
        └── prod/
```

Which Azure services back each module (Container Apps or App Service, Static Web Apps or a container for Next.js, and so on) is decided in the deployment issue, not here.

## Rules

- **No secrets in this folder.** Real `*.tfvars` files are gitignored. Commit `terraform.tfvars.example` with placeholders only. Secrets go in Key Vault or GitHub environment secrets.
- **Remote state only.** State lives in an Azure Storage account created by `bootstrap/`. Never commit `*.tfstate`.
- **GitHub Actions authenticates with OIDC** (workload identity federation), not with stored client secrets.
- **Plan on PR, apply on approval.** CI runs `terraform fmt -check`, `validate` and `plan` on every PR that touches `infra/`. `apply` runs only from `main` through a GitHub environment that needs a reviewer.
- **Every resource is tagged** with `project = "ticketflow"`, `environment` and `managed_by = "terraform"`.
- **Tear down what you spin up.** Staging resources created for testing are destroyed with `terraform destroy` when no longer needed, to protect the student credit.

## Local use

```bash
cd infra/terraform/envs/staging
az login
terraform init
terraform plan -var-file=terraform.tfvars
```
