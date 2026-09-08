package com.fixture;

public class WidgetUnitTest {
    public static void main(String[] args) {
        Widget w = new Widget();
        if (w.compute(2) != 4) {
            System.out.println("compute(2) should be 4");
            System.exit(1);
        }
        try {
            w.compute(-1);
            System.out.println("compute(-1) should have thrown");
            System.exit(1);
        } catch (IllegalArgumentException expected) {
            // the fix round's own guard clause, exercised by this authorized test change
        }
        System.out.println("ran: com.fixture.WidgetUnitTest#test");
    }
}
