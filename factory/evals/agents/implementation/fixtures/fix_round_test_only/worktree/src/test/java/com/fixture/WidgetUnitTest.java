package com.fixture;

public class WidgetUnitTest {
    public static void main(String[] args) {
        Widget w = new Widget();
        if (w.compute(2) != 4) {
            System.out.println("compute(2) should be 4");
            System.exit(1);
        }
        // A comment-only touch: this round changes no production file at
        // all, exercising the diff-touches-only-test-files refusal.
        System.out.println("ran: com.fixture.WidgetUnitTest#test");
    }
}
