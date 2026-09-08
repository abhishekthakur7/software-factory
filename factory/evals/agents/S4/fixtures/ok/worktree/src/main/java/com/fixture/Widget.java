package com.fixture;

/** Rejects negative input with a typed error instead of silently returning a wrong answer. */
public class Widget {
    public int compute(int x) {
        if (x < 0) {
            throw new IllegalArgumentException("x must not be negative");
        }
        return x * 2;
    }
}
