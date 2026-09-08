package com.example;

/** Unit-level test of Calculator alone, run as a plain main-method class. */
public class CalculatorUnitTest {
    private static boolean failed = false;

    public static void main(String[] args) {
        run("testAddSumsTwoNumbers", CalculatorUnitTest::testAddSumsTwoNumbers);
        if (failed) {
            System.exit(1);
        }
    }

    private static void run(String method, Runnable test) {
        System.out.println("ran: com.example.CalculatorUnitTest#" + method);
        try {
            test.run();
        } catch (Throwable t) {
            failed = true;
            System.out.println("FAILED: " + method + ": " + t);
        }
    }

    private static void testAddSumsTwoNumbers() {
        int result = new Calculator().add(2, 3);
        if (result != 5) {
            throw new AssertionError("expected 5, got: " + result);
        }
    }
}
