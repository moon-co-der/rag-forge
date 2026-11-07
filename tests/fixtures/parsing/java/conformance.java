/** Public API for conformance. */
public class Outer {
  /** Construct an outer value. */
  public Outer() {}
  /** Execute with an integer. */
  public void run(int value) {}
  public void run(String value) {}
  class Inner {}
}
enum Shade { LIGHT, DARK }
record Point(int x, int y) {}
