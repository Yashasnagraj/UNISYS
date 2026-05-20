/**
 * Auto-generated clinical summary narrative — mirrors
 * engine/clinical_metrics.py:generate_clinical_summary.
 */

import type { ClinicalMetrics } from "./scan";

export function generateClinicalSummary(args: {
  bone: string;
  fractureType: string;
  week: number;
  m: ClinicalMetrics;
  patientName?: string;
}): string {
  const { bone, fractureType, week, m, patientName } = args;
  const patient = patientName ? `${patientName}` : "Patient";

  let body: string;
  if (m.classification === "Implant Failure") {
    body = `Secondary resonance peak detected — characteristic of loose surgical hardware. ` +
      `Primary f₀ is ${m.fn.toFixed(0)} Hz with TSI ${m.tsi.toFixed(1)}%, but the spectrum has two peaks. ` +
      `Recommendation: ${m.recommendation}`;
  } else if (m.tsi >= 80) {
    body = `${patient} (${bone} ${fractureType} fracture, week ${week}) has reached TSI ${m.tsi.toFixed(1)}%, ` +
      `with a sharp resonance at ${m.fn.toFixed(0)} Hz (Q = ${m.qFactor.toFixed(1)}). ` +
      `Damping ratio ζ = ${m.zeta.toFixed(3)} indicates a consolidated bone retaining vibrational energy well. ` +
      `Recommendation: ${m.recommendation}`;
  } else if (m.tsi >= 60) {
    body = `${patient} (${bone} ${fractureType} fracture, week ${week}) shows TSI of ${m.tsi.toFixed(1)}%, ` +
      `indicating advancing consolidation. ` +
      `Resonant frequency at ${m.fn.toFixed(0)} Hz with Q-factor ${m.qFactor.toFixed(1)} suggests moderate callus formation ` +
      `with residual flexibility. Damping ratio ζ = ${m.zeta.toFixed(4)}. ` +
      `Recommendation: ${m.recommendation}`;
  } else if (m.tsi >= 35) {
    body = `${patient} (${bone} ${fractureType} fracture, week ${week}) is showing slow but progressing healing — TSI ${m.tsi.toFixed(1)}%. ` +
      `Resonance is at ${m.fn.toFixed(0)} Hz with broad bandwidth (${m.bandwidthHz.toFixed(0)} Hz), reflecting soft callus tissue. ` +
      `Damping ζ = ${m.zeta.toFixed(3)} remains elevated. ` +
      `Recommendation: ${m.recommendation}`;
  } else {
    body = `${patient} (${bone} ${fractureType} fracture, week ${week}) shows TSI of only ${m.tsi.toFixed(1)}%, with low resonant frequency (${m.fn.toFixed(0)} Hz) ` +
      `and high damping (ζ = ${m.zeta.toFixed(3)}). Healing has not progressed as expected at this stage. ` +
      `Recommendation: ${m.recommendation}`;
  }
  return body;
}
