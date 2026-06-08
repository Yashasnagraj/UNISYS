/**
 * Maps API responses to the ScanShape/ClinicalMetrics types that the existing
 * presentational components expect. The components don't know or care whether
 * data came from the backend or lib/scan.ts — they always receive a ScanShape.
 */

import {
  buildScan,
  callusToFrequency,
  type ScanShape,
  type ScanParams,
} from "./scan";
import type { ApiScanDetail } from "./api";

/** Reverse f_peak → callus_pct using the inverse of callusToFrequency. */
function callusFromFrequency(fHz: number, fHealthy = 850): number {
  const t = (fHz - 300) / (fHealthy - 300);
  return Math.max(0, Math.min(100, t * t * 100));
}

/**
 * Convert a raw API scan response into a ScanShape.
 *
 * The time-domain signal and spectrogram are re-generated from the derived
 * callus_pct so all existing chart components keep working. The key clinical
 * numbers (TSI, traffic_light, label, recommendation) are overridden with the
 * exact API values so the display is accurate.
 */
export function adaptApiScan(s: ApiScanDetail): ScanShape {
  const fHealthy = s.fHealthyHz ?? 850;
  const fPeak = s.fPeakHz ?? callusToFrequency(50, fHealthy);

  const callusPct = callusFromFrequency(fPeak, fHealthy);

  const params: ScanParams = {
    callusPct,
    pressureN: 3.5,
    implantLoose: s.predictedLabel === "Implant Failure",
    week: s.week,
    fHealthy,
  };

  const shape = buildScan(params);

  // Override computed values with exact API values so numbers are accurate.
  if (s.tsiPct != null) shape.metrics.tsi = s.tsiPct;
  if (s.trafficLight) {
    shape.metrics.trafficLight = s.trafficLight as "green" | "amber" | "red";
  }
  if (s.predictedLabel) {
    shape.metrics.classification =
      s.predictedLabel as "Stable" | "Delayed Union" | "Non-Union" | "Implant Failure";
  }
  if (s.recommendation) {
    shape.metrics.recommendation = s.recommendation;
  }
  if (s.zeta != null) shape.metrics.zeta = s.zeta;
  if (s.qFactor != null) shape.metrics.qFactor = s.qFactor;
  if (s.bandwidthHz != null) shape.metrics.bandwidthHz = s.bandwidthHz;
  shape.peakHz = fPeak;

  return shape;
}
