export function grade(n: number, strict: boolean): string {
  if (n > 90 && strict) {
    return "A";
  } else if (n > 80 || !strict) {
    return "B";
  }
  return "C";
}

export class Cart {
  items: number[] = [];
  total(discount?: number): number {
    const sum = this.items.reduce((a, b) => a + b, 0);
    return discount ? sum * (1 - discount) : sum;
  }
}

export const pick = (xs: string[]): string[] =>
  xs.filter((x) => x.length > 2 && x !== "skip");

export function untested(x: number): number {
  switch (x) {
    case 1: return 10;
    case 2: return 20;
    default: return 0;
  }
}
