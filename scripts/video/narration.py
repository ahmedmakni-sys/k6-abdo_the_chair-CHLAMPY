"""Generate the demo narration as WAV files with Windows' built-in speech, and write their timings.

Usage: python scripts/video/narration.py <work dir>
"""

import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Spoken text uses "A I" and "A I for Brain" so the synthetic voice pronounces them properly.
SEGMENTS = [
    ("title", "A I for Brain is a cognitive growth agent. It assesses ten thinking skills, turns performance into percentages with honest uncertainty, coaches in plain language, and builds a plan that keeps adapting. It makes no health judgements."),
    ("consent", "Nothing is stored until you agree, and consent is split by purpose. Claude-written coaching and voice are both off by default. There is no camera and no biometric data, so the mandatory non-biometric mode is simply how the assessment works."),
    ("practice", "A new twin knows nothing, so every range is as wide as it can be. A check-in measures where you are. Practising picks a level you would get right about eight times in ten. Saying how you feel changes pacing, never a score."),
    ("attention", "Here is a check-in on attention. Each task records score, response time, errors, and behaviour such as lost window focus. Each item is chosen to be the most informative one at the current estimate. Watch the live range narrow as evidence builds."),
    ("reasoning", "Reasoning items also ask how sure you are, which feeds the self-monitoring skill. Answers given too fast to have been read, or while the window lost focus, count for less, so careless evidence moves the estimate less."),
    ("summary", "Every session ends with what changed and why: the range before and after, the items that moved the estimate most, and how your plan changed in response."),
    ("twin", "This is the Brain Twin of a simulated learner after six weeks. The line is the estimate, and the band is the ninety percent range. The percentage is the share of a balanced practice set you would be expected to solve, not a comparison with other people. Dragging the timeline replays the profile from its history."),
    ("insights", "The coach speaks from evidence. Rules applied to your own results produce each note, and opening it shows the facts behind it. When a skill goes out of date, the range widens, because older evidence tells us less about you today."),
    ("curves", "Progress curves carry the same ribbon of uncertainty. The orange fan is the projection: a plausible range if practice continues in a similar way. It widens with time, refuses to appear with too little history, and is never stated as a certainty."),
    ("skill", "Each skill page shows which items moved the estimate most, then documents the definition, tasks, scoring, uncertainty, and known biases."),
    ("heat", "Heatmaps show the estimate by week and success by difficulty. A goal counts as reached when there is at least an eighty percent chance of being at or above the target."),
    ("plan", "The plan is explainable arithmetic. Each session says why it is there and how you will know it worked. Priority is a weighted sum of goal gap, uncertainty, time since practice, and plateau, and each new version records what changed."),
    ("coach", "In the chat, the coach answers from your results. Asked for a health judgement, it gives a fixed reply pointing to a qualified professional. A safety filter blocks clinical language, claims of certainty, and numbers not in the evidence. The coach runs offline, Claude can phrase replies if you opt in, and replies can be read aloud."),
    ("lab", "The A I collaboration lab measures habits through behaviour. The helper is sometimes wrong on purpose. Flagging a planted flaw counts for you, and flagging a sound step counts against you, so blanket suspicion earns nothing."),
    ("score", "The score uses the proposed weights, with a likely range and a check of how far it moves if the weights shift, because the weights are a design proposal and are not validated."),
    ("data", "You control your data: choose how long it is kept, download everything, or delete it all permanently. There is no name, no email, and no account."),
    ("eval", "We tested the engine on simulated learners. True values fell inside the ninety percent range {cov} percent of the time, with an average error of {rmse} points. Under careless responding, evidence weighting cut the error from {dirty_raw} to {dirty_weighted} points. This has not been validated with people yet, and that study is our first next step. Thank you."),
]


def fill(text):
    path = ROOT / "docs" / "evaluation_results.json"
    r = json.loads(path.read_text(encoding="utf-8"))
    s = r["summary"]
    return text.format(
        cov=round(s["clean"]["coverage_90"] * 100),
        rmse=round(s["clean"]["rmse_points"]),
        dirty_raw=round(s["contaminated_unweighted"]["rmse_points"]),
        dirty_weighted=round(s["contaminated_weighted"]["rmse_points"]),
    )


PS = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Zira Desktop')
$s.Rate = 1
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(22050, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$items = Get-Content -Raw -Encoding UTF8 $args[0] | ConvertFrom-Json
foreach ($it in $items) {
  $s.SetOutputToWaveFile($it.wav, $fmt)
  $s.Speak($it.text)
  $s.SetOutputToNull()
}
$s.Dispose()
"""


def main():
    work = Path(sys.argv[1]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    items = [dict(id=i, text=fill(t), wav=str(work / f"{i}.wav")) for i, t in SEGMENTS]
    (work / "items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    ps1 = work / "tts.ps1"
    ps1.write_text(PS, encoding="utf-8")
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), str(work / "items.json")], check=True)
    total = 0.0
    out = []
    for it in items:
        with wave.open(it["wav"], "rb") as w:
            dur = w.getnframes() / w.getframerate()
        total += dur
        # Captions read properly even though the spoken text spells out A I.
        caption = it["text"].replace("A I for Brain", "AI4Brain").replace("A I", "AI")
        out.append(dict(id=it["id"], text=caption, wav=it["wav"], seconds=round(dur, 2)))
    (work / "segments.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} segments, {total:.1f} s of narration")


if __name__ == "__main__":
    main()
