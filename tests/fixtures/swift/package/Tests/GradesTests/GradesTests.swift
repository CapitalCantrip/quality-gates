import XCTest
import Grades
import Ledger

final class GradesTests: XCTestCase {
    func testGrade() {
        XCTAssertEqual(grade(80), .merit)
        XCTAssertEqual(grade(10), .fail)
    }

    func testClamp() {
        XCTAssertEqual(clamp(5), 5)
        XCTAssertEqual(clamp(5, to: 10), 5)
    }

    func testDescribe() {
        XCTAssertEqual(describe(.merit, verbose: true), "merit with distinction")
    }

    func testLargest() {
        XCTAssertEqual(largest([1, 3, 2]), 3)
        XCTAssertEqual(largest(["a"]), "a")
    }

    func testSummary() {
        XCTAssertEqual(summary([50]), "pass")
    }

    func testWeighted() {
        XCTAssertEqual(weighted(3, by: 2), 6)
    }

    func testStore() {
        var store = Grades.Store()
        XCTAssertTrue(store.add(50))
        XCTAssertFalse(store.add(-1))
        XCTAssertEqual(store.passing(), [50])
    }

    func testLedgerExists() {
        XCTAssertEqual(Ledger.Store().entries.count, 0)
    }
}
