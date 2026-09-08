package com.fixture;

import com.fixture.auth.TokenChecker;

/** Integration-level test crossing Greeter and TokenChecker together. */
public class GreeterIntegrationTest {
    private static boolean failed = false;

    public static void main(String[] args) {
        run("testGreetOnlyRunsForAHolderOfAValidToken", GreeterIntegrationTest::testGreetOnlyRunsForAHolderOfAValidToken);
        if (failed) {
            System.exit(1);
        }
    }

    private static void run(String method, Runnable test) {
        System.out.println("ran: com.fixture.GreeterIntegrationTest#" + method);
        try {
            test.run();
        } catch (Throwable t) {
            failed = true;
            System.out.println("FAILED: " + method + ": " + t);
        }
    }

    private static void testGreetOnlyRunsForAHolderOfAValidToken() {
        TokenChecker tokenChecker = new TokenChecker();
        Greeter greeter = new Greeter();
        String token = "tok_abcdef123";
        if (!tokenChecker.isValid(token)) {
            throw new AssertionError("expected the fixture token to be valid");
        }
        String greeting = greeter.greet("ada");
        if (!greeting.endsWith("!!!")) {
            throw new AssertionError("expected the greeting to end with !!!, got: " + greeting);
        }
    }
}
