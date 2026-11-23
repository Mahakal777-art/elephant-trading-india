# Phase 0 — one-time human gates

1. GitHub: the connected account `Mahakal777-art` is authenticated, but its GitHub App installations and visible repositories are empty. Install/authorize GitHub integration for your account and grant repository Contents + Actions write access. No repo can be created/pushed by this connection yet.
2. Neon: sign in to Neon, create a project in a suitable nearby region, create a role and database, copy the pooled `postgresql://` connection string. Put it in Render's `DATABASE_URL` secret, not in chat.
3. Hosting: choose a paid always-on service for a public business service, or accept that free preview hosting sleeps. Create provider account and complete its human-only email/phone/card/legal gates. Then create an API token with deploy/service/environment permissions and store it as an encrypted deployment secret.
4. Cloudflare: create a Turnstile widget for the deployed hostname; place Site Key and Secret Key in hosting secrets. For R2 create a private bucket and scoped S3 API token (Object Read/Write limited to that bucket). Store endpoint, access key and secret key in hosting secrets.
5. Email: create Resend account, verify a sending domain, publish SPF/DKIM/DMARC DNS records, create API key with send-only permissions, store as `RESEND_API_KEY` and verified `EMAIL_FROM` secret. No need to expose the secret in chat.
6. Domain: registration and payment are human-only. Until purchased, use provider-issued HTTPS subdomain. After domain purchase, provide DNS UI access or apply the supplied records yourself.
7. Legal: review and accept vendor terms, and have an Indian lawyer approve privacy, commission and non-circumvention agreements.

Never send tokens, passwords, OTPs, API keys or bank credentials in chat. Use provider secret managers.
