// JavaScript declarations
export function greet(name) { return `hello ${name}`; }
export class Greeter {
  constructor(name) { this.name = name; }
  say() { return this.name; }
}
export const normalize = (value) => value.trim();
const values = [1].map((item) => item + 1);
