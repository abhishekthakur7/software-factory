package com.fixturevendor.util;

/** A tiny vendored utility with no further dependency. */
public class Util {
    public static void requireNonBlank(String value) {
        if (value == null || value.trim().isEmpty()) {
            throw new IllegalArgumentException("value must not be blank");
        }
    }
}
