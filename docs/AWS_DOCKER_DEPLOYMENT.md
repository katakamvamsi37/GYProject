# Deploy the GYProject backend with Docker and AWS

This guide starts on your Windows PC and ends with an HTTPS Django API on ECS
Fargate, backed by private RDS PostgreSQL. Run commands in **PowerShell from the
GYProject root**, unless a step explicitly says AWS Console. You deploy the
resources yourself; the repository contains the application and templates.

## 1. What the files do

| File | Purpose |
| --- | --- |
| `backend/Dockerfile` | Builds a Python 3.12 image, collects static files and runs Gunicorn as a non-root user |
| `backend/.dockerignore` | Excludes secrets, local databases, virtual environments and tests from the build context |
| `backend/requirements.txt` | Declares the application's supported dependency ranges |
| `backend/requirements.lock.txt` | Pins the exact versions installed in the image; keep using this file for deployments |
| `backend/gunicorn.conf.py` | Listens on port 8000 with two workers and console logs |
| `compose.yaml` | Runs a separate local PostgreSQL database, migration task and backend |
| `backend/docker/release.sh` | Checks production settings, applies migrations and creates the shared cache table |
| `backend/docker/provision_database.py` | One-time task that creates the restricted PostgreSQL application login |
| `deploy/aws/task-definition.example.json` | ECS configuration to copy and fill in |

The dependencies already include everything needed for this Docker setup. Docker
uses the lockfile; you do not need another requirements file or an AWS SDK.
WhiteNoise serves Django's static assets. Avatars currently live in the database;
receipt evidence is referenced by URL. This deployment does not require S3 media
storage. Add a durable storage integration if you later add document uploads.

## 2. Test Docker on your PC first

Install/open [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
with the WSL 2 backend and Linux containers. In PowerShell, check:

```powershell
docker version
docker compose version
```

`docker version` must show both Client and Server. If access is denied or the
engine is unavailable, start Docker Desktop and check its Windows permissions.

Start the local stack:

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps -a
docker compose logs --tail 100 migrate backend
Invoke-RestMethod http://localhost:8000/health/
```

Expected: `db` and `backend` are running/healthy, `migrate` exited with code 0,
and health returns `status: ok`. Image downloads take time on the first run.
Compose waits for PostgreSQL before running migrations, then starts the backend.
[Docker startup-order documentation](https://docs.docker.com/compose/how-tos/startup-order/).

Create your local administrator interactively:

```powershell
docker compose exec backend python manage.py createsuperuser
```

Open `http://localhost:8000/admin/`. For your separate frontend checkout, set
`VITE_API_URL=http://localhost:8000/api` and restart its development server.
The API allows the local frontend origins on port 5173.

If port 8000 is already occupied, stop the old development server, or run
`$env:GY_BACKEND_PORT = '8001'` before `docker compose up`. Then use port 8001
in the health URL and frontend configuration.

Local Compose deliberately enables debug, uses HTTP and contains development-only
database credentials. It binds the API to your PC's loopback interface and does
not publish PostgreSQL's port. **Use the ECS template for AWS production.**
Compose does not use `backend/.env` or your existing `backend/db.sqlite3`.

Useful commands:

```powershell
docker compose logs -f backend
docker compose exec backend python manage.py showmigrations
docker compose down
```

Press Ctrl+C to stop following logs. `docker compose down` retains the named
database volume. `docker compose down --volumes` deletes that local database;
do not use it when you want to retain local records.

After changing code, stop and rebuild to ensure the migration task runs again:

```powershell
docker compose down
docker compose up --build -d
```

## 3. AWS prerequisites and naming

You need an AWS account, an API domain you control (for example
`api.yourdomain.com`), its DNS access, and your frontend's exact HTTPS origin.
The frontend can stay on its current host.

Choose one region for all resources. The examples use Mumbai (`ap-south-1`);
change it if your users are elsewhere. Create an AWS Budget alert before starting.
Fargate, ALB, RDS, NAT, public IPv4 addresses, logs and secrets can incur charges
even when traffic is low. Check the [AWS Pricing Calculator](https://calculator.aws/).
Two tasks, Multi-AZ RDS and one NAT gateway per AZ prioritize availability.

Install [AWS CLI v2 for Windows](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
Open a new terminal and configure a short-lived authenticated profile using your
account's sign-in method. For an organization using IAM Identity Center:

```powershell
aws --version
aws configure sso --profile gyproject
aws sso login --profile gyproject
$env:AWS_PROFILE = 'gyproject'
$AwsRegion = 'ap-south-1'
aws sts get-caller-identity
```

If your account does not use Identity Center, follow the
[AWS CLI authentication guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-authentication.html)
for your account's method. Do not use root access keys. The deployment identity
needs permission to create the resources below and pass the specific ECS roles.
This identity is different from the two roles used by the containers.

## 4. Create the network in AWS Console

Open VPC -> Create VPC -> **VPC and more**:

1. Name: `gyproject`; IPv4 CIDR: `10.20.0.0/16`.
2. Select two Availability Zones, two public subnets and two private subnets.
3. Select one NAT gateway per AZ for availability. A single NAT costs less but
   makes outbound access dependent on one AZ; estimate that tradeoff first.
4. Enable DNS resolution and DNS hostnames.
5. Verify public routes go to an internet gateway, and each private subnet's
   outbound default route goes to its NAT gateway.

Create these security groups in that VPC:

| Name | Inbound rule |
| --- | --- |
| `gyproject-alb` | TCP 443 and TCP 80 from `0.0.0.0/0` |
| `gyproject-backend` | TCP 8000 from the **gyproject-alb security group** |
| `gyproject-db` | TCP 5432 from the **gyproject-backend security group** |

Use security group IDs as the sources for the last two rules. Keep the default
outbound rules initially. The ALB lives in the public subnets; ECS tasks and RDS
use private subnets. Assign no public IP to ECS tasks or RDS.

NAT allows image downloads, secret retrieval, logging and external SMTP/API
connections. VPC endpoints can replace some NAT use, but require all relevant
endpoints and do not provide general internet access.
[Fargate networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html).

## 5. Create RDS PostgreSQL

In RDS -> Subnet groups, create `gyproject-db-subnets` containing the two private
subnets. Then Create database -> Standard create -> PostgreSQL:

| Setting | Value |
| --- | --- |
| Identifier | `gyproject-db` |
| Version | A currently supported stable version; match the local major where available |
| Availability | Multi-AZ DB instance deployment for production |
| Instance size | Start with a small compatible instance after reviewing the console estimate; monitor and resize |
| Storage | gp3, initially 20 GiB if the selected configuration allows it; set a storage autoscaling cap |
| Initial database name | **`gyproject`** under Additional configuration; this is different from the identifier |
| Master username | `gyproject_owner` |
| Master password | Manage in AWS Secrets Manager |
| VPC/subnet group | The VPC and DB subnet group from above |
| Public access | No |
| Security group | `gyproject-db` |
| Encryption | Enabled; use an appropriate customer-managed KMS key |
| Backups | At least 7 days retention |
| Deletion protection | Enabled |
| Monitoring | Database Insights Standard; enable the available DB performance monitoring |
| Log exports | PostgreSQL logs to CloudWatch; configure retention and KMS encryption |

Confirm current engine versions before selection if needed:

```powershell
aws rds describe-db-engine-versions --engine postgres --region $AwsRegion --query 'DBEngineVersions[].EngineVersion' --output table
```

The local database uses PostgreSQL 18. If you select another supported major,
adjust the local image and validate against it before migrating data. Do not
reuse a PostgreSQL data volume across major versions without an upgrade process.

Add project/environment tags to resources. Require TLS using `rds.force_ssl=1`
in the matching PostgreSQL parameter group (already the default for newer
versions; verify the effective setting). Wait until the database is Available.
Record its **endpoint hostname**, port, and the **master secret ARN** from RDS.
You do not need to copy the master password to your computer.
[RDS TLS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html),
[Database Insights](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DatabaseInsights.html).

The template uses `POSTGRES_SSLMODE=require`, which encrypts database traffic.
For certificate and hostname verification, include the current RDS CA bundle in
the image, set `PGSSLROOTCERT` to its path and use `POSTGRES_SSLMODE=verify-full`.

## 6. Create application secrets and ECS roles

In Secrets Manager -> Store a new secret -> Other type, create
`gyproject/production/app` with these key/value pairs:

| Key | Value you generate privately |
| --- | --- |
| `DJANGO_SECRET_KEY` | A stable random value with at least 64 characters |
| `POSTGRES_PASSWORD` | A different strong random password for `gyproject_app` |

Use a password manager to generate/store the values. Copy only the full secret
ARN into the task template. Credentials belong in Secrets Manager, not in Git,
Docker build arguments, the frontend, or normal ECS environment values.

Create two IAM roles with trusted service **Elastic Container Service Task**
(`ecs-tasks.amazonaws.com`):

1. `gyprojectExecutionRole`: attach `AmazonECSTaskExecutionRolePolicy`. Add an
   inline policy allowing `secretsmanager:GetSecretValue` on the exact app
   secret ARN. If it uses a customer-managed KMS key, also grant `kms:Decrypt`
   on that key and ensure its key policy allows the role.
2. `gyprojectTaskRole`: no permission policies initially. Your application does
   not call AWS APIs directly. Add narrowly scoped policies only when needed.

Example execution-role inline policy for an app secret using the default
Secrets Manager key (replace the entire example ARN):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "secretsmanager:GetSecretValue",
    "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:gyproject/production/app-SUFFIX"
  }]
}
```

For the first database setup, create a separate `gyprojectBootstrapExecutionRole`
with the same managed execution policy plus access to **both** the app secret
and RDS master secret (and their customer-managed KMS keys). Use this role only
for the one-time setup task. The normal web task cannot read the master secret.
[ECS execution-role permissions](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html).

## 7. Push the Docker image to ECR

In ECR create a private repository named `gyproject-backend`, enable immutable
tags and configure image vulnerability scanning. Use a new tag for each release.
From your authenticated PowerShell terminal:

```powershell
$AwsAccountId = aws sts get-caller-identity --query Account --output text
$Registry = "$AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"
$ImageTag = Get-Date -Format 'yyyyMMdd-HHmmss'
$ImageUri = "$Registry/gyproject-backend:$ImageTag"
aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin $Registry
docker build --pull --platform linux/amd64 -t $ImageUri ./backend
docker push $ImageUri
```

Check that each command succeeded before continuing. Copy `$ImageUri` into your
task definition. This builds Linux AMD64 to match the template's X86_64 runtime.
Review scan findings and retain the previous release image for rollback.

## 8. Register the task definition and create the cluster

Create CloudWatch log group `/ecs/gyproject-backend` in the same region, with a
retention period such as 30 days. Create an ECS cluster named `gyproject`, using
Fargate/serverless infrastructure. Enable Container Insights if its additional
metrics are useful for your budget. Ensure CloudTrail API logging is enabled
through an account trail or the organization's trail.

Make your local working copy:

```powershell
Copy-Item deploy/aws/task-definition.example.json deploy/aws/task-definition.json
```

Edit the copy and replace every placeholder:

| Placeholder/setting | Your value |
| --- | --- |
| `ACCOUNT_ID` | The 12-digit AWS account ID |
| `REGION` | For example `ap-south-1` |
| `IMAGE_TAG` / image field | The exact ECR image URI from step 7 |
| `RDS_ENDPOINT` | RDS hostname without a scheme or port |
| `APP_SECRET_ARN` | Full app secret ARN including its generated suffix |
| `api.example.com` | Your actual backend domain |
| `CORS_ALLOWED_ORIGINS` | Exact frontend HTTPS origin and backend HTTPS origin, comma-separated |

`DJANGO_ALLOWED_HOSTS` contains hostnames only. CORS origins include `https://`
and no path. The backend origin also permits same-origin Django admin CSRF
checks because this project derives `CSRF_TRUSTED_ORIGINS` from that list.
Leave the trailing `:DJANGO_SECRET_KEY::` and `:POSTGRES_PASSWORD::` on secret
references. These select individual JSON keys.
[ECS secret injection](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html).

Do not also set `DATABASE_URL`: it takes precedence over the split `POSTGRES_*`
settings. Two Gunicorn workers use a shared database cache for throttling. This
adds database queries; move to a dedicated cache if traffic warrants it. DRF
throttles are approximate and are not a complete brute-force defense.
[Django database cache](https://docs.djangoproject.com/en/5.2/topics/cache/#database-caching),
[DRF throttling](https://www.django-rest-framework.org/api-guide/throttling/).

Register the normal web definition:

```powershell
aws ecs register-task-definition --cli-input-json file://deploy/aws/task-definition.json --region $AwsRegion
```

The initial allocation is 0.5 vCPU / 1 GiB per task. Measure before increasing it.
Fargate requires `awsvpc`; retain the template's networking mode.

## 9. Run the one-time database setup

This step is for a **new empty RDS database**. It creates a dedicated app role
with schema creation privileges so Django can run migrations, without granting
PostgreSQL superuser, database creation or role creation privileges.

Copy `task-definition.json` to `bootstrap-task-definition.json`. In the copy:

1. Change `family` to `gyproject-db-bootstrap`.
2. Change `executionRoleArn` to the `gyprojectBootstrapExecutionRole` ARN.
3. Remove the `healthCheck` field from the backend container.
4. Add `"command": ["python", "docker/provision_database.py"]` to that container.
5. Append two entries to its `secrets` array:

```json
{"name": "DB_ADMIN_USER", "valueFrom": "RDS_MASTER_SECRET_ARN:username::"},
{"name": "DB_ADMIN_PASSWORD", "valueFrom": "RDS_MASTER_SECRET_ARN:password::"}
```

Replace `RDS_MASTER_SECRET_ARN` with the full RDS-managed master secret ARN.
Keep the existing application secret entries: the script needs both accounts.
Register the copy:

```powershell
aws ecs register-task-definition --cli-input-json file://deploy/aws/bootstrap-task-definition.json --region $AwsRegion
```

In ECS -> cluster `gyproject` -> Tasks -> Run new task:

- Launch type Fargate, platform version **LATEST**, desired tasks **1**.
- Task family `gyproject-db-bootstrap`, latest revision.
- Your VPC, the two private subnets, security group `gyproject-backend`.
- Public IP **disabled**. No load balancer is needed for a one-time task.

Wait for STOPPED and check the **backend container exit code is 0**, plus the
log message `Application database role created.` STOPPED alone is not success.
The script rejects an existing role without changing its password. Do not rerun
it for every release. Deregister the bootstrap definition and remove its dedicated
execution role's secret access after successful setup.

## 10. Migrate and create your first administrator

From ECS Tasks -> Run new task, select the **normal** `gyproject-backend` task
definition, the same private network settings, and one task. Under container
overrides for `backend`, override the command with this array (the console may
display it as comma-separated arguments):

```json
["sh", "docker/release.sh"]
```

This runs production checks, migrations and cache-table creation. Wait for exit
code 0. If it fails, fix the log-reported error before starting the web service.
One-time commands do not start an HTTP server; judge these tasks by their exit
code and logs, rather than the inherited web health-check badge.
Do not run `backend/build.sh` in AWS: that script is for the existing Render flow.
Building a Docker image never needs access to your production database.

For the first administrator, create a separate Secrets Manager secret named
`gyproject/production/bootstrap-admin`, with these keys:

- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_EMAIL`
- `DJANGO_SUPERUSER_PASSWORD` (a unique password of at least 10 characters)

Create a temporary task-definition family `gyproject-admin-bootstrap` by copying
the normal definition in the ECS JSON editor. Remove its health check, set its
command to `["python", "manage.py", "bootstrap_admin"]`, and add secret references
for these three keys, using `SECRET_ARN:key::` syntax. Use a separate temporary
execution role with access to the normal app secret and this administrator
secret. Run one task with the same private network settings; require exit code 0.
After login works, remove that temporary role's access and deregister the
temporary task definition. Keep bootstrap credentials out of the web service.

## 11. HTTPS load balancer, domain and web service

1. In ACM in the **same region**, request a public certificate for your API
   domain. Add its DNS validation record at your DNS provider. Wait for Issued.
2. In EC2 -> Target groups, create `gyproject-backend`: target type **IP**, HTTP,
   port **8000**, your VPC. Health path **`/health/`**, success code **200**,
   interval 30 seconds, timeout 5 seconds. Leave target registration to ECS.
   Set deregistration delay to **90 seconds** to allow requests to drain.
3. Create an internet-facing Application Load Balancer in the two public
   subnets with security group `gyproject-alb`.
4. Add HTTPS listener 443, your ACM certificate, and forward to the target group.
   Add HTTP listener 80 with a redirect to HTTPS 443.
5. Add a Route 53 alias A record for your API domain to the ALB. With another
   DNS provider, use a CNAME for the API subdomain pointing to the ALB hostname.
6. ECS -> cluster `gyproject` -> Create service: normal `gyproject-backend` task
   definition, launch type Fargate, platform **LATEST**, service name
   `gyproject-backend`, desired tasks **2**. Use both private subnets, the backend
   security group, and disable public IP assignment.
7. Select the existing ALB, HTTPS listener and target group. Map container
   `backend` port 8000. Set health check grace period **60 seconds**.
8. Use rolling deployment, minimum healthy percent **100**, maximum **200**,
   and enable the deployment circuit breaker with rollback.

The container handles the ALB's private-IP Host header only for the fixed health
response. Other routes still validate hosts and require HTTPS. Proxy header
trust is safe only while task access is restricted to the trusted ALB.
[ALB health checks](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-troubleshooting.html).

The task filesystem is writable because Gunicorn needs temporary worker files;
the process runs as UID 10001. Local Compose demonstrates a read-only root with
a writable `/tmp`. Do not switch ECS to read-only without configuring a writable
temporary volume. ECS Exec also requires separate configuration and permissions.

## 12. Verify and connect the frontend

```powershell
Invoke-RestMethod https://api.yourdomain.com/health/
```

Then verify all of these through your real frontend:

- Sign in and refresh the session; change a password and sign out.
- Create a test budget/collection and have another authorized user review it.
- Upload an avatar, then load it after a new deployment.
- Export CSV/XLSX and confirm expected totals and permissions.
- Open `/admin/` and verify its CSS and login work.

In the frontend hosting settings use
`VITE_API_URL=https://api.yourdomain.com/api`, then rebuild/redeploy the frontend.
Your frontend may live in a separate checkout; no frontend build is included here.

`/health/` is a liveness check and intentionally does not query PostgreSQL.
A healthy target does not prove login, migrations or database connectivity work.
Monitor actual API failures too. Configure CloudWatch alarms for unhealthy
targets, API 5xx responses, ECS CPU/memory and RDS free storage/connections.
Add an AWS WAF rate-based rule for login traffic and tune it to avoid blocking
legitimate shared-IP users. Avoid logging passwords, tokens and uploaded content.

## 13. Existing records and later releases

**Migrations do not copy your old data.** If Render PostgreSQL or local SQLite
contains valuable records, first back it up and identify the authoritative source.
Rehearse import into a separate RDS database and compare users, record counts,
review history, totals and avatars before switching the frontend. PostgreSQL
dump/restore and SQLite-to-PostgreSQL import require different procedures.
Do not load demonstration data or replace the old database during cutover.

For later code releases:

1. Run the backend tests and migration checks locally.
2. Build/push a new unique ECR image tag, update the normal task definition's
   image and register a new revision.
3. Take an RDS snapshot before risky schema changes; keep regular automated
   backups and periodically test a restore into a separate database.
4. Run exactly one release task using the **new revision**; wait for exit code 0.
5. Update the ECS web service to that revision; wait for a stable deployment and
   repeat the smoke checks from step 12.

Local checks before release:

```powershell
.\.venv\Scripts\python.exe backend/manage.py test core.tests
.\.venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run
```

For a first deployment, migrations run before the service exists. For rolling
updates, schema changes must remain compatible with both the old and new images.
Use staged/additive migrations or schedule maintenance for incompatible changes.
Rolling back an image does **not** reverse database migrations. Retain old task
revisions and images; do not automatically run reverse migrations against live data.

ECS injects secrets only when tasks start. Updating Secrets Manager alone does
not refresh running workers. Coordinate database password changes with the actual
database role and a service deployment. Rotating Django's key invalidates existing
signed tokens/sessions. RDS master-password rotation does not rotate the separate
application role created by this guide.

## 14. Troubleshooting

| Symptom | Check |
| --- | --- |
| Docker engine unavailable | Start Docker Desktop, select Linux containers, verify `docker version` shows Server |
| Dependency installation fails | Check network/proxy and the exact pip error; preserve the lockfile unless deliberately updating dependencies |
| Local backend did not start | `docker compose logs migrate db`; the migration job must exit 0 |
| ECS cannot pull image | ECR URI/tag, execution-role permissions, private subnet NAT/DNS |
| ECS cannot retrieve a secret | Full ARN and JSON-key suffix, execution-role access and KMS key policy |
| Database timeout | RDS status/hostname, same VPC, DB security group source = backend security group |
| Database authentication fails | App role created successfully, matching app secret, no conflicting `DATABASE_URL` |
| `permission denied for schema public` | App-user provisioning grants and the selected database name |
| Missing `auth_user` or cache table | Successful release task against this same RDS endpoint/database |
| ALB unhealthy | Port 8000, `/health/` with trailing slash, HTTP health flag true, security groups and startup logs |
| Repeated HTTPS redirects | ALB HTTPS listener, trusted forwarded headers and `DJANGO_TRUST_PROXY_HEADERS=true` |
| Django 400 | `DJANGO_ALLOWED_HOSTS` must match the API hostname, without scheme/path |
| Browser CORS/CSRF error | Exact frontend/backend origins, frontend rebuilt with the new API URL |
| Admin has no CSS | Image build must complete `collectstatic`; use the image's default Gunicorn command |
| Exit code 137 | Review ECS memory usage; increase allocation if the task was killed for exceeding its limit |

When no longer needed, stopping the local Compose stack does not stop AWS
charges. Review ECS services, ALB, RDS, NAT gateways, public IPs, logs and retained
snapshots separately. Preserve required data and backups before deleting resources.

## Verification of these files

Verified locally with Docker Desktop's Linux engine: image build and dependency
check, PostgreSQL 18 Compose startup, all migrations, application-role provisioning,
production Django checks, HTTP login/profile access, static CSS, shared cache
access from two processes, and execution as a non-root user. All 72 Django tests
passed on both local SQLite and PostgreSQL inside Docker. The isolated test stack
and its temporary database were removed afterward.

AWS networking, IAM permissions, RDS TLS and the public HTTPS domain still need
verification in your account using the steps above. Local PostgreSQL tests used
local-only credentials and disabled database TLS; they do not validate RDS TLS.
