/** Shared verdict styling — maps module decisions to a colour band. */

export type Band = 'allow' | 'hold' | 'block' | 'neutral';

export function band(decision: string): Band {
  const d = decision.toUpperCase();
  if (['AUTHORIZED', 'SUPPORTED', 'CLEAR', 'ADMITTED', 'RECORDED'].includes(d)) return 'allow';
  if (['AUTHORIZED_WITH_CONSTRAINTS', 'CONSTRAINED', 'HOLD'].includes(d)) return 'hold';
  if (['DENIED', 'UNSUPPORTED', 'EXPIRED', 'INDETERMINATE'].includes(d)) return 'block';
  return 'neutral';
}

export const BAND_CLASS: Record<Band, string> = {
  allow: 'bg-verdict-allow/15 text-verdict-allow border-verdict-allow/30',
  hold: 'bg-verdict-hold/15 text-verdict-hold border-verdict-hold/30',
  block: 'bg-verdict-block/15 text-verdict-block border-verdict-block/30',
  neutral: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
};
