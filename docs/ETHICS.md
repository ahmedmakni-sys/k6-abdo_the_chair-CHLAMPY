# Ethics and data

AI4Brain is a practice tool. It is not a medical or psychological instrument, it does not assess health, and its results should not be used to make decisions about anyone.

## Consent

Consent is requested on the first screen, before anything is stored, and is split by purpose.

| Purpose | Default | Can it be refused? |
|---|---|---|
| Save results on this device | Off until ticked | Refusing means no profile is created. The sample data remains available |
| Claude writes coaching messages | Off | Yes. The built-in coach is used instead |
| Voice coaching | Off | Yes. Voice controls stay disabled |

Each choice is stored with a timestamp and a version, and can be changed at any time on the **My data** page.

## What is collected

| Collected | Purpose |
|---|---|
| Answers, response times, window-focus events | Estimating skills and weighting evidence |
| Confidence ratings and session estimates | Self-monitoring |
| Optional one-tap mood | Pacing only |
| Goals, plans and coach messages | Coaching. Personal details are removed from messages before storage |

**Never collected:** names, email addresses, accounts, camera images, audio recordings, voice prints, face data or location. Profiles are identified only by a random ID.

## Where it goes

- Results stay in a local SQLite database on the machine running the server.
- Nothing is sent anywhere by default.
- With opt-in and an API key, Claude receives a summary of numbers plus the user's question, with personal details removed and no identifier. Results from a safety response are never sent, and those messages do not reach the model at all.
- Voice uses the browser's speech services. In some browsers these send audio to the browser vendor to transcribe it, which is why voice is off by default and is named on the consent screen. The audio never reaches this app's server.

## Retention

The user chooses a period from 30 days to one year, 180 days by default. Inactive profiles past their period are deleted automatically each time the server starts. Sample profiles use 30 days.

## Deletion and export

- **My data, Delete my data** permanently removes every row belonging to the profile, after a confirmation. No identifying record is kept. Tested in `test_delete_removes_every_row`.
- **My data, Download my data** exports everything held about the profile as JSON.

## No sensitive decisions on face or voice

The app uses no face or voice data for any decision, sensitive or otherwise. Voice carries words only. The state proxy reads response patterns and self-report, may change pacing and tone, and never changes a score.

## Non-clinical language

The coach cannot use clinical terms. `guard.py` blocks a list of clinical vocabulary in every message, and tests scan generated output across many simulated profiles, along with the dimension documentation and collaboration scenarios.

Requests for health judgements get a fixed reply pointing to a qualified professional. Statements suggesting serious distress get a fixed supportive message pointing to emergency and crisis support, and coaching stops for that message.

## Fairness and known limits

- **No validation with people.** Difficulty levels are design values, and all evaluation so far uses simulated learners.
- **No norm group.** The percentage is deliberately not a comparison with other people.
- **Language.** Verbal reasoning and word link depend on English and disadvantage non-native speakers. The interface says so, and the brief's official language is English, but this is a real limitation for a Tunisian audience. Translated, locally reviewed item banks are the first priority after this phase.
- **Device and input.** Response times depend on hardware, and the app does not correct for device latency. The evaluation includes a slow-device condition, and the coach never compares people.
- **Education and experience.** Maths, statistics and gaming experience affect several tasks. Each dimension's documented biases say how.
- **Accessibility.** Keyboard and pointer input both work, and colours are chosen to stay usable with common colour-vision differences. Speeded tasks are harder for people with motor differences, and no alternative timing mode exists yet.
- **Authentication.** A profile ID in the browser is the only credential, which suits a local single-user tool. A hosted deployment would need real authentication and encryption at rest.

## Oversight

Trials are an append-only event log, so every estimate can be replayed and audited. Item selection is seeded. Each coach message records whether it came from Claude, the built-in writer or a safety response, along with any guard findings.
