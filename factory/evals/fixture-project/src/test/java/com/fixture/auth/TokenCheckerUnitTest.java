package com.fixture.auth;

/** Unit-level tests of TokenChecker alone, run as a plain main-method class. */
public class TokenCheckerUnitTest {
    private static boolean failed = false;

    public static void main(String[] args) {
        run("testAcceptsWellFormedToken", TokenCheckerUnitTest::testAcceptsWellFormedToken);
        run("testRejectsMissingPrefix", TokenCheckerUnitTest::testRejectsMissingPrefix);
        run("testRejectsShortToken", TokenCheckerUnitTest::testRejectsShortToken);
        if (failed) {
            System.exit(1);
        }
    }

    private static void run(String method, Runnable test) {
        System.out.println("ran: com.fixture.auth.TokenCheckerUnitTest#" + method);
        try {
            test.run();
        } catch (Throwable t) {
            failed = true;
            System.out.println("FAILED: " + method + ": " + t);
        }
    }

    private static void testAcceptsWellFormedToken() {
        if (!new TokenChecker().isValid("tok_abcdef123")) {
            throw new AssertionError("expected a well-formed token to be valid");
        }
    }

    private static void testRejectsMissingPrefix() {
        if (new TokenChecker().isValid("abcdef123456")) {
            throw new AssertionError("expected a token without the prefix to be rejected");
        }
    }

    private static void testRejectsShortToken() {
        if (new TokenChecker().isValid("tok_1")) {
            throw new AssertionError("expected a too-short token to be rejected");
        }
    }
}
