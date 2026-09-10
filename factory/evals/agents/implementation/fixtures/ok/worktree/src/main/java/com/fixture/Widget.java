package com.fixture;

import java.util.List;

public class Widget {
    public int compute(int n) {
        if (n < 0) {
            throw new IllegalArgumentException("n must not be negative");
        }
        return n * 2;
    }
}
