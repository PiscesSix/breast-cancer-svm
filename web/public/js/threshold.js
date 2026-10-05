// Decision threshold on P(malignant) shared by the diagnosis and the analysis pages. The default is
// the threshold locked at training time (out-of-fold CV probabilities, sensitivity target), read from
// GET /analysis/test-scores; the slider value lives for the browser session so both pages agree.
import { modelApi } from "./api.js";

const KEY = "bc-threshold";
let scoresPromise = null;

/** Test-split scores of the deployed model: {threshold, target_sensitivity, items: [{id, label, proba_malignant}]}. */
export function testScores() {
  if (!scoresPromise) {
    scoresPromise = modelApi("/analysis/test-scores").catch(err => {
      scoresPromise = null;  // retry on the next call
      throw err;
    });
  }
  return scoresPromise;
}

export function currentThreshold(locked) {
  try {
    const v = parseFloat(sessionStorage.getItem(KEY));
    if (Number.isFinite(v) && v > 0 && v < 1) return v;
  } catch (_) { /* storage blocked */ }
  return locked;
}

export function saveThreshold(t, locked) {
  try {
    if (Math.abs(t - locked) < 1e-9) sessionStorage.removeItem(KEY);
    else sessionStorage.setItem(KEY, String(t));
  } catch (_) { /* storage blocked */ }
}

/** Confusion matrix and clinical metrics with malignant as the positive class: P(malignant) >= t. */
export function confusion(items, t) {
  let tp = 0, fn = 0, fp = 0, tn = 0;
  items.forEach(s => {
    const pos = s.proba_malignant >= t;
    if (s.label === "malignant") pos ? tp++ : fn++;
    else pos ? fp++ : tn++;
  });
  const sens = tp + fn ? tp / (tp + fn) : 0;
  const spec = tn + fp ? tn / (tn + fp) : 0;
  const prec = tp + fp ? tp / (tp + fp) : 0;
  const f1 = prec + sens ? (2 * prec * sens) / (prec + sens) : 0;
  return { tp, fn, fp, tn, sens, spec, prec, f1 };
}

export const labelAt = (probaMalignant, t) => (probaMalignant >= t ? "malignant" : "benign");
