/**
 * Plain-English explanations for every term shown on the dashboard.
 *
 * Each entry: a short, jargon-free sentence anyone (patient, judge, clinician)
 * can understand. Used by the <InfoTip> component so a "?" sits next to every
 * metric and explains what it means and why it matters.
 */

export interface GlossaryEntry {
  term: string;        // human label
  plain: string;       // one-line plain-English meaning
  why?: string;        // optional: why it matters / how to read it
}

export const GLOSSARY: Record<string, GlossaryEntry> = {
  // ── Headline clinical numbers ──
  tsi: {
    term: "TSI — Tibial Stiffness Index",
    plain: "A 0–100 score of how stiff (healed) the bone is compared to a healthy bone.",
    why: "Higher = stronger, more healed. We tap the bone, listen to how it vibrates, and turn the pitch into this score. 100 = fully healed.",
  },
  tsiLinear: {
    term: "TSI (linear form)",
    plain: "The same stiffness score using a simpler straight-line formula instead of the squared one.",
    why: "Shown for comparison. The squared form (the main TSI) matches published research more closely.",
  },
  healingScore: {
    term: "Healing score",
    plain: "How far along the bone is in healing, as a percentage.",
    why: "This is the TSI shown big and simple. Green ≈ healed, amber ≈ getting there, red ≈ concern.",
  },
  daysToWalk: {
    term: "Days to walk",
    plain: "Our AI's estimate of how many more days until the patient can safely put full weight on the leg.",
    why: "Predicted from the healing curve. 0 days = cleared today. A dash means healing has stalled and needs a surgeon.",
  },
  trafficLight: {
    term: "Traffic light",
    plain: "A simple green / amber / red verdict on whether the bone can bear weight.",
    why: "Green = safe for full weight. Amber = partial weight, keep monitoring. Red = do not bear weight, see a surgeon.",
  },

  // ── Resonance physics ──
  fPeak: {
    term: "f_peak — resonant frequency",
    plain: "The exact pitch (in Hz) the bone vibrates at when tapped.",
    why: "A healing bone gets stiffer and rings at a higher pitch — like tightening a guitar string. This is the core measurement everything is built on.",
  },
  fHealthy: {
    term: "f_healthy — healthy reference",
    plain: "The pitch a fully-healthy version of this bone would ring at.",
    why: "We compare the injured bone's pitch to this. Ideally measured from the patient's other (uninjured) leg.",
  },
  qFactor: {
    term: "Q-factor",
    plain: "How 'pure' or sharp the bone's ringing tone is.",
    why: "A high Q means a clean, clear resonance (healthy, solid bone). A low Q means a dull, muddy response (soft callus or noise).",
  },
  zeta: {
    term: "ζ — damping ratio",
    plain: "How quickly the bone's vibration dies away after a tap.",
    why: "Soft, unhealed bone soaks up vibration fast (high damping). Stiff, healed bone rings longer (low damping). Lower is better.",
  },
  bandwidth: {
    term: "Bandwidth (−3 dB)",
    plain: "How wide the range of vibrating pitches is around the main one.",
    why: "A narrow bandwidth = a sharp, confident resonance. A wide one = a fuzzy, uncertain signal.",
  },
  mdf: {
    term: "MDF — modal damping factor",
    plain: "Another measure of how fast the vibration fades, from the decay of the tap.",
    why: "Backs up the damping reading. Lower means the bone holds its vibration — a sign of stiffness.",
  },

  // ── Signal quality / normalization ──
  snr: {
    term: "SNR — signal-to-noise ratio",
    plain: "How much louder the real bone signal is than the background noise, in decibels (dB).",
    why: "Higher = cleaner reading. Cheap sensors have low SNR; our averaging boosts it.",
  },
  snrGain: {
    term: "SNR gain (averaging)",
    plain: "How much cleaner the signal got by averaging several taps together.",
    why: "Averaging N taps cuts random noise by roughly √N. 8 taps ≈ +9 dB — about 3× cleaner. (Welch, 1967)",
  },
  jitter: {
    term: "Jitter (TSI ±%)",
    plain: "How much the stiffness score wobbles between repeated taps.",
    why: "Small jitter = a trustworthy, repeatable number. Big jitter = a noisy reading you can't rely on. Normalization shrinks this.",
  },
  improvement: {
    term: "Stability improvement (Nx)",
    plain: "How many times more stable the score becomes after normalization.",
    why: "We compare the wobble before vs after cleaning. 30× means the cleaned reading is 30 times steadier than the raw one — the whole point of the device.",
  },
  normalization: {
    term: "Normalization",
    plain: "The cleaning process that turns a noisy cheap-sensor reading into a stable, reliable number.",
    why: "Average taps → remove drift → filter out mains hum → standardise → find the exact peak. Each step is from peer-reviewed signal processing.",
  },

  // ── Pipeline stages ──
  averaging: {
    term: "Coherent averaging",
    plain: "Combining several taps so random noise cancels out and the real signal stays.",
    why: "The single biggest noise reducer. More taps = cleaner result (√N rule).",
  },
  detrend: {
    term: "Detrend",
    plain: "Removing slow drift so the signal sits flat around zero.",
    why: "Cheap sensors drift with gravity and temperature. This strips that out.",
  },
  bandpass: {
    term: "Band-pass filter",
    plain: "Keeping only the frequencies where bone resonance lives, throwing away the rest.",
    why: "Cuts 50 Hz mains hum, body movement, and high-frequency hiss so only the bone's tone remains.",
  },
  zscore: {
    term: "Z-score normalize",
    plain: "Rescaling the signal so how hard you pressed doesn't change the result.",
    why: "Two people pressing with different force still get the same reading.",
  },
  welch: {
    term: "Welch PSD",
    plain: "A smoothed picture of how much energy sits at each pitch.",
    why: "A low-noise way to find the bone's resonant peak. (Welch, 1967)",
  },
  subbin: {
    term: "Sub-bin interpolation",
    plain: "Pinpointing the exact peak pitch, finer than the raw measurement grid.",
    why: "Gets sub-1-Hz precision on the resonant frequency. (Smith & Serra, 1987)",
  },

  // ── Charts ──
  psd: {
    term: "PSD — frequency response",
    plain: "A graph showing which pitches the bone vibrated at and how strongly.",
    why: "The tall peak is the bone's resonance. A healthy bone's peak sits further right (higher pitch).",
  },
  waveform: {
    term: "Time-domain waveform",
    plain: "The raw vibration over time — how the bone shook right after the tap.",
    why: "You can see it ring and fade. A longer ring = stiffer bone.",
  },
  spectrogram: {
    term: "Spectrogram",
    plain: "A heat-map of pitch over time as the tap sweeps through frequencies.",
    why: "The bright band lights up where the bone resonated. Its shape shifts as bone heals.",
  },

  // ── ML ──
  predictedLabel: {
    term: "AI classification",
    plain: "The machine-learning model's verdict: Stable, Delayed Union, Non-Union, or Implant Failure.",
    why: "Trained on 25 signal features. It can flag trouble weeks before an X-ray would show it.",
  },
  confidence: {
    term: "Model confidence",
    plain: "How sure the AI is about its verdict, as a percentage.",
    why: "Higher = more certain. We show the real number, not a fake 100%.",
  },
  rust: {
    term: "RUST score",
    plain: "A standard 4–12 radiology score for how much new bone (callus) has bridged the fracture.",
    why: "Doctors already use RUST on X-rays. We estimate it from vibration so it's familiar to clinicians.",
  },

  // ── Misc ──
  week: {
    term: "Week",
    plain: "How many weeks since the fracture happened.",
    why: "Healing is judged against time — being at 60% in week 4 is good; in week 16 it's a concern.",
  },
  source: {
    term: "Source",
    plain: "Where this reading came from: the real device, a simulation, or an uploaded file.",
    why: "'device' = live ADXL345 hardware. 'sim' = generated test data through the same maths.",
  },
  callus: {
    term: "Callus / stiffness %",
    plain: "How much healing tissue has formed and hardened at the fracture.",
    why: "0% = fresh break, 100% = fully bridged and solid. Drives the resonant pitch.",
  },

  // ── Trend view ──
  healingCurve: {
    term: "Healing curve (Gompertz)",
    plain: "The S-shaped curve that bone healing naturally follows over time.",
    why: "Slow at first, fast in the middle, levelling off near full strength. We fit this curve to a patient's scans to project the future.",
  },
  personalCurve: {
    term: "Personalised curve",
    plain: "The healing curve fitted to THIS patient's own scan history.",
    why: "Compared against the population average, it shows if they're ahead, on pace, or behind.",
  },
  populationCurve: {
    term: "Population average",
    plain: "The typical healing curve for an average patient.",
    why: "The dashed grey line. We compare the patient's own curve to this benchmark.",
  },
  pace: {
    term: "Healing pace",
    plain: "Whether the patient is healing faster or slower than an average person.",
    why: "Ahead = great. Behind = may need intervention. Driven by age, smoking, diabetes, and the actual scans.",
  },
  predictionConfidence: {
    term: "Prediction confidence",
    plain: "How trustworthy the days-to-walk estimate is, based on how many scans we have.",
    why: "More scans = a tighter curve fit = higher confidence. 4+ scans = high, 2–3 = moderate, 1 = low.",
  },
  safeToWalk: {
    term: "Safe-to-walk threshold (80% TSI)",
    plain: "The stiffness level at which the bone is strong enough for full weight.",
    why: "When the healing curve crosses this line, the patient is cleared. We project the date it'll happen.",
  },
  projectedClearance: {
    term: "Projected clearance",
    plain: "The week we predict the bone will be strong enough to walk on.",
    why: "Where the patient's fitted curve crosses the 80% safe-to-walk line.",
  },

  // ── Model view ──
  accuracy: {
    term: "Accuracy",
    plain: "Out of all cases, the percentage the AI got right.",
    why: "Tested on cases it never saw during training. Higher = more reliable.",
  },
  precision: {
    term: "Precision",
    plain: "When the AI says a verdict, how often it's actually correct.",
    why: "High precision = few false alarms. E.g. 95% precision on 'Non-Union' = when it flags non-union, it's right 95% of the time.",
  },
  recall: {
    term: "Recall (sensitivity)",
    plain: "Of all the real cases of a verdict, how many the AI caught.",
    why: "High recall = it rarely misses. Critical for 'Non-Union' — you don't want to miss a failing bone.",
  },
  f1: {
    term: "F1 score",
    plain: "A single balanced score combining precision and recall.",
    why: "Closer to 1.0 is better. Useful when one outcome is rarer than others.",
  },
  confusionMatrix: {
    term: "Confusion matrix",
    plain: "A grid showing the real verdict (rows) vs what the AI said (columns).",
    why: "Numbers on the diagonal = correct. Anything off the diagonal = a mistake. Lets you see exactly which outcomes get mixed up.",
  },
  holdout: {
    term: "Holdout test",
    plain: "Cases set aside and never shown to the AI during training.",
    why: "The fairest test — like a final exam on unseen questions. Proves it generalises, not memorises.",
  },
  crossValidation: {
    term: "Cross-validation",
    plain: "Testing the AI five times on five different slices of data, then averaging.",
    why: "Guards against a lucky or unlucky single test. The ± shows how much the score wobbles.",
  },
  featureImportance: {
    term: "Feature importance",
    plain: "How much each of the 25 measurements influenced the AI's decisions.",
    why: "Shows the model leans on real physics (frequency, sharpness, damping) — not a black box.",
  },
};

export function lookup(key: string): GlossaryEntry | undefined {
  return GLOSSARY[key];
}
