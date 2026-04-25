# Deployment

Run Manifold behind same-origin frontend + backend routing.

For production:

- terminate TLS at reverse proxy
- keep `APP_ENV=production`
- set secure cookie flags automatically
