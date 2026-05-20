import { PATIENTS } from "../lib/patients";
import { predict } from "../lib/prediction";

for (const p of PATIENTS) {
  const r = predict(p);
  console.log(`${p.id}  ${p.name.padEnd(16)}  scans=${p.scans.length}`);
  console.log(`  k=${r.fittedK.toFixed(3)}  t0=${r.fittedT0.toFixed(2)}  currentTsi=${r.currentTsi.toFixed(1)}%`);
  if (r.daysRemaining === null) {
    console.log(`  -> NON-UNION RISK`);
  } else if (r.daysRemaining === 0) {
    console.log(`  -> CLEARED today`);
  } else {
    console.log(`  -> ${r.daysRemaining}d to clearance (${r.targetDateIso}, ${r.pace}, ${r.paceDeltaDays >= 0 ? "+" : ""}${r.paceDeltaDays}d)`);
  }
  console.log();
}
