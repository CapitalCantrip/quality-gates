import { test, expect } from "vitest";
import { grade, Cart, pick } from "./sample";
test("grade", () => { expect(grade(95, true)).toBe("A"); expect(grade(50, true)).toBe("C"); });
test("cart", () => { const c = new Cart(); c.items = [1, 2]; expect(c.total()).toBe(3); });
test("pick", () => { expect(pick(["abc", "x"])).toEqual(["abc"]); });
