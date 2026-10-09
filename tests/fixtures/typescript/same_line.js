const doubled = (xs) => xs.map(x => x ? 1 : 2);

const bounded = (xs, hi) => xs.map(x => x > hi ? hi : x)
  .filter(x => x !== 0 && x !== hi);

function first(x) { return x ? 1 : 2; } function second(x) {
  if (x) {
    return 3;
  }
  return 4;
}

module.exports = { doubled, bounded, first, second };
