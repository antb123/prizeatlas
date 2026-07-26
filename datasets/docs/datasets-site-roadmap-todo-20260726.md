# TODO — Student-focused awards website

Small product roadmap. Each item needs a brief approved specification before implementation.

- [ ] Rework the site's text and styling for a high-school audience: plain language, clear explanations, strong visual hierarchy, and accessible mobile presentation.
- [ ] Add Spanish, French, and German translations. Follow
  [`datasets-multilingual-20260726.md`](datasets-multilingual-20260726.md) and its execution TODO; extend both to specify
  German before implementation.
- [ ] Add Japanese and Chinese support after the Latin-language rollout. Specify translation scope, locale metadata,
  language navigation, search behavior, and appropriate CJK typography and line breaking before implementation.
- [x] Integrate the map MVP into the static website. Completed in
  [`website-map-integration-20260726.md`](website-map-integration-20260726.md), merged into `master` at `ef61d52`;
  the standalone MVP remains available for comparison.
- [ ] Add an “About this site” page covering its purpose, audience, data sources, methodology, limitations, and update process.
- [ ] Add a “Learn more” page with short descriptions and curated links to reliable introductory material, including the Feynman Lectures and suitable books.
- [ ] Add a “Will AI change research?” page based on clearly attributed primary material from Demis Hassabis and other research leaders; separate sourced claims from editorial explanation.
- [ ] Add an optional “Explain this” action beside selected award text. It should give a high-school-level explanation without replacing or altering the source text, and clearly identify AI-generated output.
- [ ] Prepare the repository for public release: choose appropriate code, data, and content licensing; audit third-party
  assets and attribution; remove secrets, private data, backups, and generated files from tracked history; and add
  public-facing README, contribution, security, and governance guidance.
- [ ] Choose the site’s public name and domain, then prepare production launch infrastructure: static hosting, DNS, HTTPS,
  canonical URLs and redirects, automated deployment, basic availability monitoring, and a documented rollback path.
- [ ] Add a weekly update agent that checks official award sources for newly announced winners, prepares reviewed and
  guarded database updates, backs up and validates `awards.sqlite3`, rebuilds and tests the website, redeploys only after
  every check passes, and records an auditable update report with rollback details.
