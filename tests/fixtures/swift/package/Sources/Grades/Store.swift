public struct Store {
    public private(set) var scores: [Int] = []

    public init() {}

    public mutating func add(_ score: Int) -> Bool {
        guard score >= 0 else {
            return false
        }
        if score > 100 {
            scores.append(100)
            return true
        }
        scores.append(score)
        return true
    }

    public func passing() -> [Int] {
        scores.filter { score in
            score >= 40 && score <= 100
        }
    }
}
