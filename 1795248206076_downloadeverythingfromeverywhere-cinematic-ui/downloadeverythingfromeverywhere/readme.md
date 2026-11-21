# Download Everything From Everywhere

`web/` is the frontend, `api/` is the FastAPI backend, and `scrapers/` contains the source integrations.

## Run locally

Install Python 3.12+ and Node.js 22.12+ with npm. Get a [TMDB API Read Access Token](https://developer.themoviedb.org/docs/authentication-application).

From the extracted folder, start the API:

```sh
python3 -m venv .venv
.venv/bin/pip install -r api/requirements.txt
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8080
```

In a second terminal, start the frontend:

```sh
cd web
echo 'NEXT_PUBLIC_TMDB_TOKEN=your_tmdb_read_access_token' > .env.local
npm ci
npm run build
npm start -- --hostname 127.0.0.1
```

Open [http://localhost:3000](http://localhost:3000). The TMDB token is used by the browser, so it is visible to visitors.

## Host on a server

Point your site and API hostnames at the server. Use your domains in place of the examples below.

- In `web/.env.local`, set `SITE_URL=https://example.com` and `NEXT_PUBLIC_SCRAPE_API=https://api.example.com`, then rebuild and restart the frontend.
- Set `FRONTEND_ORIGIN=https://example.com` when starting the API.
- Run both processes under a service manager. Put them behind an HTTPS reverse proxy that streams API responses. For example, use this [Caddyfile](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy):

```caddyfile
example.com {
    reverse_proxy 127.0.0.1:3000
}
api.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Optional settings:

- To enable Turnstile, set `NEXT_PUBLIC_TURNSTILE_SITE_KEY` before building and `TURNSTILE_SECRET` on the API.
- To enable suggestions, set the server-side `SUGGEST_WEBHOOK_URL` in `web/.env.local`.

Licensed under the [MIT License](LICENSE).
