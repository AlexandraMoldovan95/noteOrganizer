# Android Release Reference (exploratory — not current work)

**Reference material only, kept ready for if/when an Android release is ever scoped — nothing here
is a plan or a commitment.** Android work stays out of scope until an explicit decision says
otherwise: see `CLAUDE.md`'s "Project focus" and "An Android version" under
[ROADMAP's "Under consideration"](ROADMAP.md#under-consideration) — an exploration in a
repository of its own.

## Two separate version numbers

Google Play tracks two distinct values per release, not one:

- **`versionName`** — the user-facing string shown in the Play Store listing (e.g. `"2.3.1"`). Free-form; commonly follows semantic versioning for clarity, but Google doesn't require any particular format.
- **`versionCode`** — an internal integer that **must strictly increase with every single submission**. The Play Store rejects an update whose `versionCode` isn't greater than the current live version's. Capped at 2,100,000,000.

A common way to derive `versionCode` from a semver `versionName` is `MAJOR × 10000 + MINOR × 100 + PATCH` — keeps it monotonically increasing as long as the semver itself only moves forward, and assumes the post-1.0 reset-at-each-level scheme from [ROADMAP's Versioning](ROADMAP.md#versioning), not today's pre-1.0 cumulative numbers.

Source: [Android Developers — Version your app](https://developer.android.com/studio/publish/versioning)

## Publishing basics (for context, not action)

- New apps must be submitted as an **Android App Bundle (`.aab`)**, signed with Play App Signing — plain `.apk` uploads are no longer accepted for new apps.
- Builds must be in release mode (not debug) — debug builds are rejected outright.
- New personal developer accounts can't publish straight to Production: a Closed Test first requires at least 12 real testers to install and keep the app for 14 consecutive days.
- Apps must target a recent Android API level (the specific minimum shifts over time — check current requirements when this actually becomes relevant, rather than trusting a number written down today).

Sources: [Android Developers — App Bundle FAQ](https://developer.android.com/guide/app-bundle/faq), [Android App Bundle — Wikipedia](https://en.wikipedia.org/wiki/Android_App_Bundle)
