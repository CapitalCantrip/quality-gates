// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "Grades",
    targets: [
        .target(name: "Grades"),
        .target(name: "Ledger"),
        .testTarget(name: "GradesTests", dependencies: ["Grades", "Ledger"]),
    ]
)
