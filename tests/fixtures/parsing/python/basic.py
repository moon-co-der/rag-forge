"""Small Python golden fixture."""

from math import sqrt


def hypotenuse(a, b):
    """Calculate the hypotenuse."""
    return sqrt(a * a + b * b)


class Vector:
    """Two-dimensional vector."""

    def magnitude(self):
        return sqrt(self.x * self.x + self.y * self.y)
