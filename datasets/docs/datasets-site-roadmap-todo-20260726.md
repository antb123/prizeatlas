# TODO — Student-focused awards website

Small product roadmap. Each item needs a brief approved specification before implementation.

- [ ] Rework the site's text and styling for a high-school audience: plain language, clear explanations, strong visual hierarchy, and accessible mobile presentation.
- [ ] Get structured feedback from high-school teachers on clarity, usefulness, classroom fit, accessibility, and missing
  context. Recruit through appropriate educator networks or communities such as Reddit, obtain consent, avoid collecting
  unnecessary personal data, and record findings and resulting roadmap changes.
- [ ] Add Spanish, French, and German translations. Follow
  [`datasets-multilingual-20260726.md`](datasets-multilingual-20260726.md) and its execution TODO; extend both to specify
  German before implementation.
- [ ] Add Japanese and Chinese support after the Latin-language rollout. Specify translation scope, locale metadata,
  language navigation, search behavior, and appropriate CJK typography and line breaking before implementation.
- [x] Integrate the map MVP into the static website. Completed in
  [`website-map-integration-20260726.md`](website-map-integration-20260726.md), merged into `master` at `ef61d52`;
  the standalone MVP remains available for comparison.
- [ ] Add an “About this site” page covering its purpose, audience, data sources, methodology, limitations, and update process.
- [ ] Show the dataset’s last-updated date in the shared footer, sourced automatically from the published database snapshot
  or build metadata so it cannot drift from the deployed data.
- [ ] Add a clearly labelled “Fix this data” action for missing or incorrect information. Open a submission form prefilled
  with the page URL and stable record ID; request the proposed correction and supporting source, make contact details
  optional, protect against spam, and queue submissions for human review without writing directly to the database.
- [ ] Add a “Learn more” page with short descriptions and curated links to reliable introductory material, including the Feynman Lectures and suitable books.
- [ ] Add a “Will AI change research?” page based on clearly attributed primary material from Demis Hassabis and other research leaders; separate sourced claims from editorial explanation.
- [ ] Add an optional “Explain this” action beside selected award text. It should give a high-school-level explanation without replacing or altering the source text, and clearly identify AI-generated output.
- [ ] Prepare the repository for public release: choose appropriate code, data, and content licensing; audit third-party
  assets and attribution; remove secrets, private data, backups, and generated files from tracked history; and add
  public-facing README, contribution, security, and governance guidance.
- [ ] Generate a concise `/llms.txt` at build time with the site’s purpose, audience, update date, limitations, and links to
  the About, methodology, licensing, explorer, map, prize, and dataset entry points; treat it as optional agent guidance,
  not as a replacement for accessible HTML, structured data, the sitemap, or `robots.txt`.
- [ ] Choose the site’s public name and domain, then prepare production launch infrastructure: static hosting, DNS, HTTPS,
  canonical URLs and redirects, automated deployment, basic availability monitoring, and a documented rollback path.
- [ ] Evaluate and select a CDN-backed static deployment platform, such as Cloudflare Pages/CDN or an equivalent. Compare
  custom-domain and HTTPS support, caching and invalidation, preview deployments, CI integration, logs, cost, portability,
  and rollback before documenting the production deployment workflow.
- [ ] Add privacy-preserving visitor analytics for aggregate country, popular-page, referral-source, device-class, and
  traffic-trend reporting. Prefer a cookieless approach; specify consent requirements, IP handling, data retention, bot
  filtering, access controls, and public privacy disclosures before deployment.
- [ ] Add a weekly update agent that checks official award sources for newly announced winners, prepares reviewed and
  guarded database updates, backs up and validates `awards.sqlite3`, rebuilds and tests the website, redeploys only after
  every check passes, and records an auditable update report with rollback details.
