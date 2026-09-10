# Deploy through the AWS Console: Elastic Beanstalk and optional Amplify

Use this guide for the browser workflow. The earlier ECS/Fargate guide describes
a different deployment; do not mix its task definitions or security groups with
these steps. You do not need to install AWS CLI or EB CLI on your PC.

## What you upload

The prepared backend bundle is **`deploy/gyproject-beanstalk.zip`**. Upload that
ZIP as-is. It contains the Dockerfile, application source, pinned requirements,
Beanstalk configuration and startup script, at the correct archive paths. It
excludes local databases, .env files, development keys, virtual environments and
tests. It does not contain the frontend.

Beanstalk builds the image from this ZIP on its EC2 instances. This route does
not require ECR. ECR supports Docker image pushes, not a direct console file
upload. If you later use ECR, AWS CloudShell can build/push from the browser.
[Beanstalk Docker source bundles](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/single-container-docker-configuration.html),
[CloudShell Docker tutorial](https://docs.aws.amazon.com/cloudshell/latest/userguide/tutorial-docker-cli.html).

After changing backend code, regenerate the ZIP from the project root. This
command works in your current **CMD** terminal as well as PowerShell:

```cmd
.venv\Scripts\python.exe scripts\package_beanstalk.py
```

The package's startup command optionally creates the database login, then runs
production checks, migrations, cache-table setup and optional administrator
creation before starting Gunicorn. PostgreSQL advisory locks serialize setup
across concurrently starting instances. This prevents simultaneous migration
commands; it does not make incompatible schema changes safe for older web workers.

## 1. Prepare your account, region and API domain

Sign into the AWS Console using your normal authorized account identity. Select
one region for the VPC, RDS, Beanstalk, Secrets Manager and ACM certificate.
Mumbai (`ap-south-1`) is an example if it suits your users.

Create a Budget alert and review the estimate before launching: EC2, load
balancer, RDS, NAT gateways, public IPs, secrets and logs incur ongoing charges.
Beanstalk manages these services; it does not make the infrastructure free.

Have an API subdomain you control, such as `api.yourdomain.com`, and access to its
DNS records. Open Certificate Manager (ACM) in the selected region -> Request
public certificate -> enter that domain -> DNS validation. Add the supplied
validation CNAME at your DNS provider and wait for the certificate to be Issued.
You need this certificate for public HTTPS. The default Beanstalk environment
hostname is useful for diagnostics, but is not automatically your custom HTTPS API.

## 2. Create the VPC and security groups

VPC Console -> Create VPC -> VPC and more:

- Name `gyproject`, CIDR `10.20.0.0/16`.
- Two Availability Zones; two public subnets and two private subnets.
- NAT gateways for outbound access from the private instances. One per AZ
  supports availability; using one reduces cost but introduces an AZ dependency.
- Enable DNS hostnames/resolution and inspect the generated routes.

The internet-facing load balancer uses public subnets. Beanstalk EC2 instances
and RDS use private subnets. The instances need NAT to download the Python base
image and packages, fetch secrets and send logs.

Create `gyproject-eb-instance` and `gyproject-db` security groups in this VPC.
Give `gyproject-db` an inbound rule: PostgreSQL TCP **5432**, source security
group **gyproject-eb-instance**. Keep default outbound rules initially.

When the Beanstalk load balancer exists, verify the effective rules:

| Destination | Inbound access |
| --- | --- |
| Load balancer | TCP 443 and 80 from internet clients |
| Beanstalk instances | TCP **80** from the load balancer security group only |
| RDS | TCP 5432 from `gyproject-eb-instance` only |

Beanstalk's nginx proxy receives port 80 and forwards to Docker port 8000.
Do not copy the ECS backend port-8000 security group rule here. Do not open
instance or database ports to the internet. If Beanstalk creates extra security
groups, inspect their combined rules too.

## 3. Create an independent RDS PostgreSQL database

RDS Console -> Subnet groups: create `gyproject-db-subnets` using your private
subnets. Then Databases -> Create database -> Standard create -> PostgreSQL.

| Setting | Select/enter |
| --- | --- |
| DB instance identifier | `gyproject-db` |
| Engine version | A currently supported stable PostgreSQL version; local tests use PostgreSQL 18 |
| Master username | `gyproject_owner` |
| Credentials management | Managed in AWS Secrets Manager |
| Initial database name | **`gyproject`**, under Additional configuration |
| VPC/subnets | Your VPC and private DB subnet group |
| Public access | No |
| Security group | `gyproject-db` |
| Availability | Multi-AZ DB instance for production availability |
| Instance/storage | A compatible small instance and gp3 storage; review the estimate and autoscaling cap |
| Encryption | Enabled, with an appropriate customer-managed KMS key |
| Backups | At least 7 days retention |
| Deletion protection | Enabled |
| Monitoring | Database Insights Standard and CloudWatch PostgreSQL log export |

Verify TLS is required (`rds.force_ssl=1`), set log retention/encryption, and add
project/environment tags. Wait for Available. Record the RDS endpoint hostname
and the full ARN of its managed master secret. Do not copy its password locally.
The initial database name is essential: the instance identifier does not create
a database with the same name.

Use a separate RDS database rather than coupling its lifetime to a disposable
Beanstalk environment. The old local/Render records are not automatically copied.
Back up and rehearse data import separately if those records must be retained.

## 4. Create the application secret

Secrets Manager -> Store a new secret -> Other type -> Key/value pairs. Create
`gyproject/production/app` with these keys:

| Key | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | A random, stable secret of at least 64 characters |
| `POSTGRES_PASSWORD` | A different strong random password for the app's database login |
| `DJANGO_SUPERUSER_USERNAME` | Your first Django administrator's username |
| `DJANGO_SUPERUSER_EMAIL` | Your administrator email |
| `DJANGO_SUPERUSER_PASSWORD` | A unique strong password of at least 10 characters |

Generate the passwords privately using a password manager. The app's database
login and Django administrator are different accounts. Record this secret's full
ARN, including the generated suffix, for the next steps.

## 5. Set up Beanstalk IAM roles

Beanstalk needs a **service role** to manage its environment and an **EC2 instance
profile** for the servers. These are different from the earlier ECS roles.

In the Beanstalk creation wizard, allow it to create the service role if offered.
For the EC2 role, open IAM -> Roles -> Create role -> AWS service -> EC2, name it
`gyprojectBeanstalkInstanceRole`, and attach `AWSElasticBeanstalkWebTier`.
Creating an EC2 role through IAM also creates its instance profile.

Add an inline policy allowing `secretsmanager:GetSecretValue` on the exact app
secret ARN and, for initial setup only, the exact RDS master secret ARN:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "secretsmanager:GetSecretValue",
    "Resource": ["APP_SECRET_ARN", "RDS_MASTER_SECRET_ARN"]
  }]
}
```

Replace both strings with real ARNs. For customer-managed secret encryption
keys, grant `kms:Decrypt` on those specific keys and allow the role in their key
policies. Access to the RDS master secret is removed after initial setup.
[Beanstalk instance profiles](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/iam-instanceprofile.html),
[service roles](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/iam-servicerole.html).

## 6. Create the Beanstalk environment and upload the ZIP

Elastic Beanstalk Console -> Create application/environment:

| Setting | Value |
| --- | --- |
| Environment tier | Web server environment |
| Application name | `gyproject` |
| Environment name | `gyproject-backend` |
| Platform | **Docker** |
| Platform branch | **Docker running on 64bit Amazon Linux 2023** |
| Platform version | Current supported release; January 13, 2026 or newer for JSON secret-key extraction |
| Application code | Upload your code -> Local file -> `deploy/gyproject-beanstalk.zip` |
| Version label | A new unique label, e.g. `gyproject-20260910-01` |
| Environment type/preset | Custom, load balanced |
| Service role | The Beanstalk service role |
| EC2 instance profile | `gyprojectBeanstalkInstanceRole` |

Select ordinary Docker on AL2023, not the ECS-managed Docker platform and not
the Python platform. The ZIP's Dockerfile installs Python itself.

Continue through the configuration pages **before submitting**:

- VPC: `gyproject`; instance subnets: the two private subnets; instance public IP: disabled.
- Attach `gyproject-eb-instance` to the EC2 instances.
- Capacity: x86_64 architecture, a compatible instance with at least 2 GiB RAM
  as a starting point, minimum/maximum **1/1** for initial verification.
- Environment remains **load balanced** even with one EC2 instance, so it can
  use the ALB HTTPS listener. One instance has no application redundancy.
- Load balancer: Application Load Balancer, internet-facing, public subnets.
- Default process: HTTP **80**, health-check path **`/health/`**, success code 200.
- HTTPS listener: port 443, your issued ACM certificate, forward to the default
  process. Keep HTTP 80 for redirect/diagnostics; Django redirects API HTTP to HTTPS.
- Enable health reporting and log streaming; choose a retention period.

After verification, use at least two instances across AZs if application
availability matters. Allow sufficient deployment time for building the image
and running migrations. Console labels can vary slightly by platform version.

## 7. Enter runtime environment variables

In the creation wizard's software/updates/monitoring settings, find **Runtime
environment variables**. For an existing environment: Configuration -> Updates,
monitoring and logging -> Edit -> Runtime environment variables.

Add these with source **Plain text**:

| Name | Value |
| --- | --- |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | Your API hostname, e.g. `api.yourdomain.com` |
| `CORS_ALLOWED_ORIGINS` | `https://YOUR_FRONTEND_HOST,https://api.yourdomain.com` |
| `DJANGO_TRUST_PROXY_HEADERS` | `true` |
| `DJANGO_HTTP_HEALTHCHECK` | `true` |
| `DJANGO_CACHE_TABLE` | `gyproject_cache` |
| `POSTGRES_HOST` | RDS endpoint hostname, without protocol or port |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_DB` | `gyproject` |
| `POSTGRES_USER` | `gyproject_app` |
| `POSTGRES_SSLMODE` | `require` |
| `WEB_CONCURRENCY` | `2` |
| `DJANGO_PROVISION_DATABASE` | `true` for the initial deployment only |

Replace the frontend placeholder with your actual frontend origin. If it is
not known yet, start with only your API HTTPS origin and add the Amplify origin
after deploying the frontend. Do not use wildcard allowed hosts or CORS origins.

Add these with source **Secrets Manager**; enter references, not password values:

| Environment variable | Secret reference |
| --- | --- |
| `DJANGO_SECRET_KEY` | `APP_SECRET_ARN:DJANGO_SECRET_KEY` |
| `POSTGRES_PASSWORD` | `APP_SECRET_ARN:POSTGRES_PASSWORD` |
| `DJANGO_SUPERUSER_USERNAME` | `APP_SECRET_ARN:DJANGO_SUPERUSER_USERNAME` |
| `DJANGO_SUPERUSER_EMAIL` | `APP_SECRET_ARN:DJANGO_SUPERUSER_EMAIL` |
| `DJANGO_SUPERUSER_PASSWORD` | `APP_SECRET_ARN:DJANGO_SUPERUSER_PASSWORD` |
| `DB_ADMIN_USER` | `RDS_MASTER_SECRET_ARN:username` |
| `DB_ADMIN_PASSWORD` | `RDS_MASTER_SECRET_ARN:password` |

Replace the `*_ARN` portions with full real ARNs. **Beanstalk's JSON-key syntax
here ends in `:key`, without ECS's trailing `::`.** Use a recent AL2023 platform
release supporting this feature. Do not set `DATABASE_URL` at the same time;
it overrides the split PostgreSQL settings.
[Beanstalk console secret configuration](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/AWSHowTo.secrets.env-vars.html).

`require` encrypts PostgreSQL traffic. For certificate/hostname verification,
include the RDS CA bundle, configure `PGSSLROOTCERT`, and use `verify-full`.

Review all settings, the resource estimate and selected region, then Submit.
AWS will create EC2/ALB infrastructure, build the image, initialize the app
database role, run migrations, create the administrator and start Gunicorn.

## 8. Connect DNS, verify, and remove bootstrap access

Use Route 53 to create an alias record for your API subdomain pointing to the
Beanstalk environment. With another DNS provider, create a CNAME for the API
subdomain pointing to the environment hostname. Keep the ACM validation record.

Open these plain URLs in your browser:

```text
https://api.yourdomain.com/health/
https://api.yourdomain.com/admin/
```

Health should show `{"status":"ok"}`. Sign into admin using the credentials
you configured. Test actual application login and records too; health does not
check the database. The default environment HTTP URL can be used for `/health/`,
but use your custom HTTPS domain for real login.

After successful setup, in Runtime environment variables:

1. Set `DJANGO_PROVISION_DATABASE=false`.
2. Remove `DB_ADMIN_USER`, `DB_ADMIN_PASSWORD`, and the three `DJANGO_SUPERUSER_*`
   variables. Keep `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`.
3. Apply the changes and verify login still works.
4. Remove RDS-master-secret access from the EC2 instance role, then remove the
   three administrator keys from the app secret. Keep credentials privately in
   your password manager. The created accounts persist in PostgreSQL.

Startup never changes an existing role's or administrator's password. It uses
database locking for repeat starts, and drops bootstrap variables before
launching Gunicorn. Removing the instance role's master-secret access is still
necessary; environment variables are not a substitute for IAM permissions.

## 9. Optional: deploy the React frontend to Amplify

The frontend is in a separate checkout and is not included in the backend ZIP.
You can leave it on its current hosting provider if only the backend is moving.

For a browser-managed build: Amplify -> Deploy an app -> choose your Git provider
-> connect the **frontend repository** -> select its branch. Specify the app root
if the frontend is in a subfolder. Configure the build to install dependencies
with `npm ci`, build with `npm run build`, and publish `dist` for this Vite app.
Set `VITE_API_URL=https://api.yourdomain.com/api` before building. Review detected
settings against the actual frontend repository. Do not upload the backend ZIP.

For a manual upload: build the frontend locally, zip the **contents of `dist`**
so `index.html` is at the archive root, then Amplify -> Deploy without Git ->
upload the ZIP. A manual upload serves already built files; it does not run
`npm install` or substitute Vite environment variables afterward.
[Amplify manual deployments](https://docs.aws.amazon.com/amplify/latest/userguide/manual-deploys.html).

Copy the resulting `https://...amplifyapp.com` origin into the backend's
`CORS_ALLOWED_ORIGINS`, retaining the backend HTTPS origin. Apply. For React
client-side routing, configure Amplify's documented SPA rewrite to `index.html`
with status **200**, preserving real static asset requests. Verify refreshing a
page such as `/signin` works.
[Amplify SPA rewrites](https://docs.aws.amazon.com/amplify/latest/userguide/redirect-rewrite-examples.html#redirects-for-single-page-web-apps-spa).

## 10. Updates and troubleshooting

After a code change, run tests, regenerate the ZIP, then Beanstalk -> your
environment -> **Upload and deploy** -> select the ZIP -> new version label.
Take a database snapshot before risky migrations. For incompatible schema
changes, schedule maintenance or use staged migrations. Image/application
rollback does not undo database changes.

Use Beanstalk -> Events and Logs -> Request logs to diagnose failures. Expected
startup messages include successful production checks, applied migrations and
administrator creation/skipping. Never paste secret values into support messages.

| Failure | Check |
| --- | --- |
| Can't fetch secret | EC2 instance role, full ARN/key, supported platform version, KMS policy |
| Database timeout | Private subnet routing, RDS status, port 5432 source = instance security group |
| Authentication failed | App secret password matches role; no conflicting `DATABASE_URL` |
| Docker build fails | Logs, NAT/internet access, Docker Hub limits, instance RAM/disk |
| Unhealthy / 502 | Logs, release completed, container port 8000, ALB process port 80, `/health/` |
| 400 response | Actual API hostname is in `DJANGO_ALLOWED_HOSTS` |
| HTTPS redirect loop | HTTPS listener and correct forwarded protocol through the trusted proxy |
| Avatar 413 | Confirm the bundle's `.platform/nginx/conf.d/uploads.conf` was deployed |
| Browser blocked API | Exact frontend origin in CORS; rebuilt frontend using HTTPS API URL |

Enable alarms for unhealthy targets, 5xx responses, instance CPU/memory and RDS
storage/connections. Keep backups and test restores. The shared database throttle
cache coordinates workers but is approximate; add edge rate limits for login.
Secret rotation requires a coordinated environment refresh. Creating AWS
resources, attaching HTTPS, IAM access and RDS TLS must be verified in your own
account; local Docker tests cannot validate those settings.
