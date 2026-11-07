export enum Color { Red, Blue }
export abstract class Base {
  abstract run(): void;
}
export namespace Tools {
  export function go(value: number): number { return value; }
}
export interface Shape { width: number }
export type Point = { x: number; y: number };
