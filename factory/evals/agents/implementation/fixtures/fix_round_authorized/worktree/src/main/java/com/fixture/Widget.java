package com.fixture;

public class Widget {
    // Guard clause added by the fix round.
    public int compute(int x) {
        if (x < 0) {
            throw new IllegalArgumentException("x must not be negative");
        }
        return x * 2;
    }
}
