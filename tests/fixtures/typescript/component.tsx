export function V({a}: {a: boolean}) {
  if (a) { return <div>{a && <b/>}</div>; }
  return null;
}
