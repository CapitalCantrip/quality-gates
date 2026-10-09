export function a1(x: number): number { return x ? 1 : 2; } export function a2(x: number): number {
  if (x) {
    return 3;
  }
  return 4;
}

export interface Shape {
  size: number;
}
