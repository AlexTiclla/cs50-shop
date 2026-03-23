# Deployment Plan — Cloudinary + Supabase + Vercel

## Overview

Three-phase deployment for the CS50 Shop app:
1. **Cloudinary** — migrate image storage (Vercel has no writable disk)
2. **Supabase** — managed PostgreSQL in the cloud
3. **Vercel** — serverless deployment with analytics

---

## Phase 1 — Cloudinary (image storage)

### Why
Vercel serverless functions run in ephemeral containers; `static/uploads/` cannot be written to.

### What changed in code
| File | Change |
|---|---|
| `requirements.txt` | Added `cloudinary==1.36.0` |
| `.env` | Added `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_SECRET` |
| `config.py` | Added `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` |
| `models.py` | `image_filename (String 255)` → `image_url (String 500)` |
| `blueprints/seller.py` | `save_image()` / `delete_image()` now use Cloudinary SDK |
| All image templates | `url_for('static', 'uploads/'+filename)` → `product.image_url` |

### Cloudinary account setup
1. Sign up at https://cloudinary.com
2. Dashboard → API Keys → copy Cloud Name, API Key, API Secret
3. Add to `.env`:
   ```
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=your_api_key
   CLOUDINARY_API_SECRET=your_api_secret
   ```

### Notes
- Images are uploaded to the `cs50shop/` folder in Cloudinary
- `image_url` stores the full `https://res.cloudinary.com/...` URL
- Old products with local file references will show broken images until re-uploaded
- Vercel body size limit: 4.5 MB — keep product images under ~4 MB

---

## Phase 2 — Supabase (cloud PostgreSQL)

### Why
Vercel needs an external database. Supabase provides managed PostgreSQL with a free tier.

### Setup steps
```bash
# Install Supabase CLI
npm install -g supabase

# Login (opens browser)
supabase login

# Get org ID
supabase orgs list

# Create project
supabase projects create cs50shop --org-id <org-id> --region us-east-1 --db-password <strong-password>
```

### Connection strings (from Supabase Dashboard → Settings → Database)
- **Direct** (for init/seed): `postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres`
- **Transaction pooler** (for Vercel): `postgresql://postgres.<ref>:<password>@aws-0-us-east-1.pooler.supabase.com:6543/postgres`

### Initialize the database
```bash
DATABASE_URL="<direct-url>" flask init-db
DATABASE_URL="<direct-url>" flask seed-db
```

### Local testing against Supabase
Update `.env`:
```
DATABASE_URL=postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres
```

---

## Phase 3 — Vercel (deployment)

### Why
Vercel is the simplest serverless host for Python/Flask apps with zero-config CI/CD from GitHub.

### vercel.json
```json
{
  "version": 2,
  "builds": [{ "src": "app.py", "use": "@vercel/python" }],
  "routes": [{ "src": "/(.*)", "dest": "app.py" }]
}
```

### Environment variables to set in Vercel dashboard
```
FLASK_ENV=production
SECRET_KEY=<long-random-string>
DATABASE_URL=<supabase-pooler-url>
SELLER_WHATSAPP=<number>
GEMINI_API_KEY=<key>
CLOUDINARY_CLOUD_NAME=<name>
CLOUDINARY_API_KEY=<key>
CLOUDINARY_API_SECRET=<secret>
```

### Deploy
```bash
npx vercel --prod
```

### Analytics
Vercel Web Analytics and Speed Insights scripts are injected in `base.html`.
They are no-ops in local dev and activate automatically on Vercel.

---

## Verification checklist

- [ ] Upload a product image → DB row has `https://res.cloudinary.com/...` in `image_url`
- [ ] Cloudinary dashboard shows the file under `cs50shop/`
- [ ] `psql <direct-url>` → `\dt` shows `users`, `categories`, `products` tables
- [ ] Deployed URL: catalog loads, seller login works, image upload works, PDF export works
- [ ] Vercel dashboard → Analytics tab shows page views after a few visits
