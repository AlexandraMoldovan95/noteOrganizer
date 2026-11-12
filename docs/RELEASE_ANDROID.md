# Android Release Reference

**Reference material for the Android app's release on Google Play.** The app is built in a
repository of its own, which keeps its own release notes; this repository's work stays on the
desktop app (`CLAUDE.md`'s "Project focus", and "An Android version" under
[ROADMAP's "Under consideration"](ROADMAP.md#under-consideration)). What the two share is the
notes file's format and the privacy policy, which covers both apps.

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

## Rolling out, and stopping a release

Written down before the first release, so that a bad one is met with steps rather than a
scramble (2026-11-12).

1. **The bundle is tried as Play hands it out.** The internal testing track installs the APKs
   Google Play makes from the `.aab`, which are not the APK the emulator walked; the closed test
   that new accounts need (12 people, 14 days) is that trial at length. The testing tracks'
   pre-launch report runs the app on real devices of several Android versions.
2. **Production goes out as a staged rollout**: a share of people first, raised after a few quiet
   days, while Android vitals (crashes, "isn't responding") are watched.
3. **When something is wrong, the rollout is halted first**, in the Play Console: nobody new
   receives the version while the fix is made. Android never puts an older version back over a
   newer one; the way out is a newer version, its `versionCode` higher.
4. **The fix is a release like any other**, in the app's own repository: its branch, the
   version a patch higher, the unit tests, the gates and the walk, the release build, then the
   upload. A crash's trace in the console is read through the R8 mapping the bundle carries;
   each release's `mapping.txt` is kept beside its build as well.
5. **What a person sees is read before anything is guessed**: the reviews, and the console's
   crashes and "isn't responding" reports (the app sends nothing itself).
