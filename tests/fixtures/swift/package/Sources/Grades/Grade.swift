public enum Grade {
    case pass, merit, fail
}

public func grade(_ score: Int) -> Grade {
    if score >= 70 {
        return .merit
    }
    if score >= 40 {
        return .pass
    }
    return .fail
}

public func clamp(_ value: Int) -> Int {
    min(max(value, 0), 100)
}

public func clamp(_ value: Int, to limit: Int) -> Int {
    if value < 0 {
        return 0
    }
    if value > limit {
        return limit
    }
    return value
}

@discardableResult
public func describe(_ grade: Grade, verbose: Bool) -> String {
    if verbose && grade == .merit {
        return "merit with distinction"
    } else if verbose {
        return "graded"
    }
    return "ok"
}

public func largest<T: Comparable>(_ items: [T]) -> T? {
    var best: T? = nil
    for item in items {
        if let current = best, current >= item {
            continue
        }
        best = item
    }
    return best
}

public func summary(_ scores: [Int]) -> String {
    func label(_ score: Int) -> String {
        score >= 40 ? "pass" : "fail"
    }
    if scores.isEmpty {
        return "none"
    }
    return scores.map(label).joined(separator: ",")
}

public func weighted(
    _ score: Int,
    by weight: Int
) -> Int {
    if weight <= 0 || score <= 0 {
        return 0
    }
    return score * weight
}
