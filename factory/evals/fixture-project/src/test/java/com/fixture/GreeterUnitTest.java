package com.fixture;

/** Unit-level tests of Greeter alone, run as a plain main-method class. */
public class GreeterUnitTest {
    private static boolean failed = false;

    public static void main(String[] args) {
        run("testGreetIncludesUppercasedName", GreeterUnitTest::testGreetIncludesUppercasedName);
        run("testGreetRejectsEmptyName", GreeterUnitTest::testGreetRejectsEmptyName);
        if (failed) {
            System.exit(1);
        }
    }

    private static void run(String method, Runnable test) {
        System.out.println("ran: com.fixture.GreeterUnitTest#" + method);
        try {
            test.run();
        } catch (Throwable t) {
            failed = true;
            System.out.println("FAILED: " + method + ": " + t);
        }
    }

    private static void testGreetIncludesUppercasedName() {
        String result = new Greeter().greet("ada");
        if (!result.contains("ADA")) {
            throw new AssertionError("expected greeting to contain ADA, got: " + result);
        }
    }

    private static void testGreetRejectsEmptyName() {
        try {
            new Greeter().greet("");
            throw new AssertionError("expected IllegalArgumentException");
        } catch (IllegalArgumentException expected) {
            // expected: an empty name is invalid input
        }
    }
}
