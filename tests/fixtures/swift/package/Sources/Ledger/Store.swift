public struct Store {
    public private(set) var entries: [String: Int] = [:]

    public init() {}

    public mutating func add(_ name: String, _ amount: Int) -> Int {
        if amount == 0 {
            return entries[name, default: 0]
        }
        if amount < 0 && entries[name, default: 0] < -amount {
            return -1
        }
        entries[name, default: 0] += amount
        return entries[name, default: 0]
    }
}
