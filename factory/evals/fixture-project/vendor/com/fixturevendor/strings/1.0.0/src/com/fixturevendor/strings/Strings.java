package com.fixturevendor.strings;

import com.fixturevendor.util.Util;

/** A tiny vendored library that itself depends on the vendored util library. */
public class Strings {
    public static String shout(String value) {
        Util.requireNonBlank(value);
        return value.toUpperCase() + "!!!";
    }
}
