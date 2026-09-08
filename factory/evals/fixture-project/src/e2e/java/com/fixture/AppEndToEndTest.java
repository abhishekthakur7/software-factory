package com.fixture;

import com.fixture.auth.TokenChecker;

/** End-to-end test walking the fixture project's whole small flow. */
public class AppEndToEndTest {
    private static boolean failed = false;

    public static void main(String[] args) {
        run("testFullFlowForEveryFixtureUser", AppEndToEndTest::testFullFlowForEveryFixtureUser);
        if (failed) {
            System.exit(1);
        }
    }

    private static void run(String method, Runnable test) {
        System.out.println("ran: com.fixture.AppEndToEndTest#" + method);
        try {
            test.run();
        } catch (Throwable t) {
            failed = true;
            System.out.println("FAILED: " + method + ": " + t);
        }
    }

    private static void testFullFlowForEveryFixtureUser() {
        TokenChecker tokenChecker = new TokenChecker();
        Greeter greeter = new Greeter();
        String[] names = {"ada", "grace"};
        String[] tokens = {"tok_abcdef123", "tok_ghijkl456"};
        for (int i = 0; i < names.length; i++) {
            if (!tokenChecker.isValid(tokens[i])) {
                throw new AssertionError("expected token for " + names[i] + " to be valid");
            }
            String greeting = greeter.greet(names[i]);
            if (!greeting.contains(names[i].toUpperCase())) {
                throw new AssertionError("expected greeting to contain " + names[i].toUpperCase());
            }
        }
    }
}
