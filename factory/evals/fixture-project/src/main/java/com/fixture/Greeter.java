package com.fixture;

import com.fixturevendor.strings.Strings;

/** Builds a greeting for a name, via the vendored strings library. */
public class Greeter {
    public String greet(String name) {
        if (name == null || name.isEmpty()) {
            throw new IllegalArgumentException("name must not be empty");
        }
        return Strings.shout("hello, " + name);
    }
}
