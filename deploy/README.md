# Troopers Hill eclipse sightline model

Static single-page site. One HTML file, one CDN dependency (three.js r128 from cdnjs).
No build step, no framework, no server-side anything.

## Deploy to Netlify — pick one

**A. Netlify Drop (30 seconds, no account needed to start)**
1. Go to https://app.netlify.com/drop
2. Drag this whole `deploy` folder onto the page
3. Live immediately on a `*.netlify.app` URL. Claim it to your account to keep it.

**B. CLI**
```sh
cd deploy
npx netlify-cli deploy          # draft URL, opens browser to log in first time
npx netlify-cli deploy --prod   # promote to production
```

**C. Git**
```sh
cd deploy && git init && git add -A && git commit -m "eclipse model"
gh repo create troopers-hill-eclipse --public --source=. --push
```
Then "Add new site → Import an existing project" at https://app.netlify.com —
every push redeploys. `netlify.toml` already sets publish dir and an empty build
command, so there's nothing to configure.

## Notes

- `netlify.toml` sets `must-revalidate` so edits show up immediately rather than
  sitting behind a CDN cache. Fine for a page this small.
- Nothing here calls an API at runtime. All terrain and ephemeris data is baked
  into the HTML as literals, so it works offline and can't break when
  OpenTopoData rate-limits you.
- If you want zero external dependencies, download three.min.js from
  https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js into this
  folder and change the `<script src>` to `three.min.js`.
