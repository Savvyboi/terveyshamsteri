import { defineConfig } from 'astro/config';

// GitHub Pages serves the project at https://<user>.github.io/<repo>/.
// Override with SITE_URL / SITE_BASE for a custom domain.
export default defineConfig({
  site: process.env.SITE_URL || 'https://savvyboi.github.io',
  base: process.env.SITE_BASE ?? '/terveyshamsteri',
  trailingSlash: 'always',
  build: { format: 'directory' },
});
