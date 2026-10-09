# Safe Browser and Rate Limiting Design

## Goal

Make paperSearch reliable for personal batches of about 100 papers while minimizing provider rate limits and keeping institutional login data out of the repository.

The tool cannot guarantee that Google Scholar, IEEE, or ACM will never rate limit a user. It must reduce request frequency, stop when a provider signals a limit, preserve completed work, and resume without repeating successful requests.

## Scope

- Use one dedicated real Google Chrome profile for Scholar, IEEE, and ACM.
- Guide the user through separate IEEE and ACM institutional login checks.
- Search and download serially with conservative randomized delays.
- Classify authentication, rate limit, and ordinary network failures separately.
- Save progress immediately and resume completed downloads safely.
- Keep browser data, papers, results, state logs, and build output out of Git and release archives.
- Preserve the existing CLI structure and dependencies.

The release will not add parallel downloads, proxy rotation, CAPTCHA bypass, automatic credential entry, or background scheduling.

## Browser and Login

Chrome uses a dedicated profile below the user's application data directory. The project directory is rejected as a profile location so browser state cannot be packaged accidentally.

All browser commands connect through Chrome DevTools Protocol on `127.0.0.1`. If the configured local port is unavailable, the tool starts Chrome with the dedicated profile. It never exposes the debugging port to the LAN.

The `login` command opens IEEE first and ACM second. For each provider, it waits for the user to finish SUSTech CARSI, CAPTCHA, and MFA steps and confirm access. The tool does not read credentials or inspect Cookie values. Scholar search and downloads reuse the same profile and browser session.

## Conservative Request Control

Scholar requests run one page at a time with a default random delay of 20–40 seconds. One invocation accepts at most five pages. Cached results avoid repeat visits unless the user explicitly requests a refresh.

IEEE and ACM downloads run serially with a default random delay of 15–30 seconds between papers. Each provider tracks its own request timing.

HTTP 403, HTTP 429, CAPTCHA, unusual traffic pages, and known provider limit pages are rate limit events. The current result and state are saved immediately. Automatic cooldowns are 60, 120, 300, and 600 seconds. If the provider is still limited after the final cooldown, the command stops without issuing more requests.

Ordinary transient failures retry at most three times after 10, 30, and 60 seconds. Authentication redirects, CARSI pages, and MFA pages stop immediately for manual action and do not consume ordinary retries.

CLI validation rejects negative delays, a minimum greater than a maximum, more than five Scholar pages, and retry counts outside 1–3.

## Download Safety and Resume

The DOI input is normalized and deduplicated once. Unsupported providers are recorded without a network request.

Every result is appended to the state file immediately. State records contain the DOI, status, timestamp, byte count when applicable, and a short error category. They do not contain redirect URLs, SSO query strings, tokens, Cookie values, or raw exception text that may include sensitive data.

PDF data is written to a `.part` file, checked for the `%PDF-` signature and minimum size, then atomically moved to its final filename. `--resume` skips only an existing valid PDF. Interrupted or invalid partial files are never treated as completed downloads.

## Repository and Release Safety

The repository ignores virtual environments, Python caches, browser profiles, downloads, PDFs, search results, state logs, temporary files, and build artifacts. Release archives are built from tracked files so ignored local data cannot be included.

No password, Cookie, browser profile, downloaded paper, or institutional session is committed or uploaded.

## Errors and User Messages

Messages distinguish four actions:

- `auth_required`: finish institutional login in Chrome, then resume;
- `rate_limited`: wait for the displayed cooldown or resume later;
- `failed`: an ordinary error exhausted its retries;
- `success` or `skipped`: the paper is safely present.

Partial Scholar results and completed downloads remain usable after any stop.

## Verification

Automated tests cover:

- Chrome starts on loopback with the dedicated profile;
- login opens both IEEE and ACM;
- CLI delay, page, and retry validation;
- 403, 429, CAPTCHA, authentication, and ordinary error classification;
- cooldown and retry timing without real waits;
- state log redaction and resume behavior;
- atomic PDF validation;
- packaging excludes ignored and generated files.

Final manual checks use a two-page Scholar search. After the user completes SUSTech CARSI and MFA, one authorized IEEE paper and one authorized ACM paper are downloaded and verified as PDFs.

## Compatibility and Limits

The primary supported environment is Windows with Google Chrome installed. Existing commands remain recognizable, but conservative defaults are slower. Provider HTML and authentication flows can change; the manual provider checks are required before calling a release stable.
