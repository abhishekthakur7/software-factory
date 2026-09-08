package com.fixture.auth;

/** Checks that a token has the fixture project's expected shape. */
public class TokenChecker {
    private static final String PREFIX = "tok_";
    private static final int MIN_LENGTH = 12;

    public boolean isValid(String token) {
        return token != null && token.startsWith(PREFIX) && token.length() >= MIN_LENGTH;
    }
}
